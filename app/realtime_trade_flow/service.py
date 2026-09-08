"""Bu modulun disariya actigi tek arayuz. Ana mimari (matriks_provider.py,
institutional_flow_service.py vb.) bilerek buna dokunmuyor - ileride bu
modulu tamamen sokup baska bir Matriks entegrasyonuyla degistirmek
istersen, tek yapman gereken bu dosyanin fonksiyonlarini baska bir
implementasyonla degistirmek olacak.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass

from app.realtime_trade_flow.client import MatriksTradeFlowClient
from app.realtime_trade_flow.trade_message import TradeTick

_MAX_TRADES_PER_TICKER = 500


@dataclass
class _ReceivedTrade:
    tick: TradeTick
    received_at: float


_store: dict[str, deque[_ReceivedTrade]] = {}
_store_lock = threading.Lock()
_client: MatriksTradeFlowClient | None = None


def _handle_message(tick: TradeTick) -> None:
    with _store_lock:
        symbol = tick.symbol.upper()
        bucket = _store.get(symbol)
        if bucket is None:
            bucket = deque(maxlen=_MAX_TRADES_PER_TICKER)
            _store[symbol] = bucket
        bucket.append(_ReceivedTrade(tick=tick, received_at=time.time()))


def start_trade_flow_stream(tickers: list[str]) -> None:
    global _client
    if _client is None:
        _client = MatriksTradeFlowClient(on_message=_handle_message)
    _client.start(tickers)


def subscribe_ticker(ticker: str) -> None:
    if _client is None:
        start_trade_flow_stream([ticker])
    else:
        _client.subscribe(ticker)


def stop_trade_flow_stream() -> None:
    global _client
    if _client is not None:
        _client.stop()
        _client = None


def get_recent_trades(ticker: str, max_age_seconds: float = 300.0) -> list[TradeTick]:
    with _store_lock:
        bucket = _store.get(ticker.upper())
        if not bucket:
            return []
        now = time.time()
        return [entry.tick for entry in bucket if now - entry.received_at <= max_age_seconds]
