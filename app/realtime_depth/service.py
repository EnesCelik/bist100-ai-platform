"""Bu modulun disariya actigi tek arayuz. Ana mimari (matriks_provider.py,
institutional_flow_service.py vb.) bilerek buna dokunmuyor - ileride bu
modulu tamamen sokup baska bir Matriks entegrasyonuyla degistirmek
istersen, tek yapman gereken bu dosyanin fonksiyonlarini baska bir
implementasyonla degistirmek olacak.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from app.realtime_depth.client import MatriksDepthClient
from app.realtime_depth.depth_message import DepthLevel, DepthMessage


@dataclass
class DepthSnapshot:
    symbol: str
    ask_levels: list[DepthLevel]
    bid_levels: list[DepthLevel]
    received_at: float


_store: dict[str, DepthSnapshot] = {}
_store_lock = threading.Lock()
_client: MatriksDepthClient | None = None


def _handle_message(message: DepthMessage) -> None:
    with _store_lock:
        _store[message.symbol.upper()] = DepthSnapshot(
            symbol=message.symbol.upper(),
            ask_levels=message.ask_levels,
            bid_levels=message.bid_levels,
            received_at=time.time(),
        )


def start_depth_stream(tickers: list[str]) -> None:
    global _client
    if _client is None:
        _client = MatriksDepthClient(on_message=_handle_message)
    _client.start(tickers)


def subscribe_ticker(ticker: str) -> None:
    if _client is None:
        start_depth_stream([ticker])
    else:
        _client.subscribe(ticker)


def stop_depth_stream() -> None:
    global _client
    if _client is not None:
        _client.stop()
        _client = None


def get_latest_depth(ticker: str, max_age_seconds: float = 30.0) -> DepthSnapshot | None:
    with _store_lock:
        snapshot = _store.get(ticker.upper())
    if snapshot is None:
        return None
    if time.time() - snapshot.received_at > max_age_seconds:
        return None
    return snapshot
