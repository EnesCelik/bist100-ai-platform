"""Matriks gercek zamanli "Pay Islem Tarafi Esanli" (AKDE) client'i.

Kesfedilen protokol ozeti:
  - wss://rtstream.radix.matriksdata.com/trade, alt-protokol "mqttv3.1"
  - Auth: depth ile ayni (username="JTW", password=<Garanti MarketDataToken JWT>)
  - Abonelik topic'i: "mx/trade/{TICKER}@lvl2" (depth ile ayni kalip)
  - Her PUBLISH tek bir eslesen islemi tasir (alici/satici uye kodlariyla
    birlikte).

Bu modul, realtime_depth gibi, ana mimariden (matriks_provider.py,
institutional_flow_service.py vb.) bilerek izole tutulur.
"""
from __future__ import annotations

import logging
import random
import ssl
import threading
import time
from collections.abc import Callable

import websocket

from app.core.config import settings
from app.realtime_depth.mqtt_wire import (
    MSG_PUBLISH,
    build_connect_packet,
    build_pingreq_packet,
    build_subscribe_packet,
    decode_packet,
    decode_publish,
)
from app.realtime_trade_flow.trade_message import TradeTick, parse_trade_message

logger = logging.getLogger(__name__)

WS_URL = "wss://rtstream.radix.matriksdata.com/trade"
ORIGIN = "https://trader.garantibbva.com.tr"
_PING_INTERVAL_SECONDS = 20.0


def _topic_for(ticker: str) -> str:
    return f"mx/trade/{ticker.upper()}@lvl2"


class MatriksTradeFlowClient:
    """Arka planda tek bir WebSocket baglantisi tutar, verilen sembollere
    abone olur ve her eslesen islemde callback'i cagirir.

    Kullanim:
        client = MatriksTradeFlowClient(on_message=my_callback)
        client.start(["GARAN", "THYAO"])
        ...
        client.stop()
    """

    def __init__(self, on_message: Callable[[TradeTick], None]) -> None:
        self._on_message = on_message
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._ws: websocket.WebSocket | None = None
        self._subscribed: set[str] = set()
        self._lock = threading.Lock()

    def start(self, tickers: list[str]) -> None:
        with self._lock:
            self._subscribed = {t.upper() for t in tickers}
        if self._thread is not None:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_forever, name="matriks-trade-flow-client", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._ws is not None:
            try:
                self._ws.close()
            except Exception:
                pass
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._thread = None

    def subscribe(self, ticker: str) -> None:
        with self._lock:
            self._subscribed.add(ticker.upper())
        if self._ws is not None:
            self._send_subscribe(self._ws, ticker.upper())

    def _send_subscribe(self, ws: websocket.WebSocket, ticker: str) -> None:
        packet_id = random.randint(1, 0xFFFE)
        ws.send_binary(build_subscribe_packet(packet_id=packet_id, topic=_topic_for(ticker)))

    def _run_forever(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._run_once()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Matriks trade-flow baglantisi koptu, yeniden denenecek: %s", exc)
            if not self._stop_event.is_set():
                time.sleep(3)

    def _run_once(self) -> None:
        token = settings.matriks_market_data_token.strip()
        if not token:
            logger.warning("MATRIKS_MARKET_DATA_TOKEN bos, trade-flow baglantisi kurulamiyor")
            time.sleep(30)
            return

        client_id = f"mxt-{random.randint(10**12, 10**13 - 1)}"
        ws = websocket.create_connection(
            WS_URL,
            header=[f"Origin: {ORIGIN}"],
            subprotocols=["mqttv3.1"],
            sslopt={"cert_reqs": ssl.CERT_NONE},
            timeout=10,
        )
        self._ws = ws
        try:
            ws.send_binary(build_connect_packet(client_id=client_id, username="JTW", password=token))
            connack_raw = ws.recv()
            connack = decode_packet(connack_raw if isinstance(connack_raw, bytes) else connack_raw.encode())
            if connack.body != b"\x00\x00":
                logger.warning("Matriks trade-flow CONNACK basarisiz: %s", connack.body.hex())
                return

            with self._lock:
                tickers = set(self._subscribed)
            for ticker in tickers:
                self._send_subscribe(ws, ticker)

            last_ping = time.time()
            ws.settimeout(5)
            while not self._stop_event.is_set():
                if time.time() - last_ping > _PING_INTERVAL_SECONDS:
                    ws.send_binary(build_pingreq_packet())
                    last_ping = time.time()
                try:
                    raw = ws.recv()
                except websocket.WebSocketTimeoutException:
                    continue
                if not raw:
                    continue
                if isinstance(raw, str):
                    raw = raw.encode()
                packet = decode_packet(raw)
                if packet.msg_type != MSG_PUBLISH:
                    continue
                published = decode_publish(packet.body)
                message = parse_trade_message(published.payload)
                if message is not None:
                    try:
                        self._on_message(message)
                    except Exception:
                        logger.exception("Trade-flow on_message callback hata verdi")
        finally:
            self._ws = None
            try:
                ws.close()
            except Exception:
                pass
