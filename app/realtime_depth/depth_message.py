"""Matriks derinlik (order book) PUBLISH mesajlarini yorumlar.

Alan haritasi, gercek WebSocket trafigi byte byte incelenerek cikarildi ve
canli REST snapshot'iyla (best_bid/best_ask) karsilastirilarak dogrulandi:
  ust seviye mesaj:
    field 1 (string)  -> sembol, orn. "GARAN"
    field 2 (string)  -> "{YYYYMMDD}_{sembol}" bicimli oturum/gun kimligi
    field 3 (varint)  -> mesaj zaman damgasi
    field 4 (repeated, nested message) -> SATIS (ask) kademeleri, best_ask'tan
                          yukari dogru artan sirada
    field 5 (repeated, nested message) -> ALIS (bid) kademeleri, best_bid'den
                          asagi dogru azalan sirada
  kademe (level) alt-mesaji:
    field 1 (double)  -> fiyat
    field 2 (varint)  -> miktar (lot)
    field 3 (varint)  -> kademe zaman damgasi
    field 4 (varint)  -> emir sayisi
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.realtime_depth.protobuf_decoder import WIRE_LENGTH_DELIMITED, decode_fields


@dataclass
class DepthLevel:
    price: float
    quantity: int
    order_count: int
    updated_at_raw: int


@dataclass
class DepthMessage:
    symbol: str
    session_id: str
    timestamp_raw: int
    ask_levels: list[DepthLevel] = field(default_factory=list)
    bid_levels: list[DepthLevel] = field(default_factory=list)


def _decode_level(raw: bytes) -> DepthLevel:
    values: dict[int, object] = {}
    for field_number, _wire_type, value in decode_fields(raw):
        values[field_number] = value
    return DepthLevel(
        price=float(values.get(1, 0.0)),
        quantity=int(values.get(2, 0)),
        updated_at_raw=int(values.get(3, 0)),
        order_count=int(values.get(4, 0)),
    )


def parse_depth_message(payload: bytes) -> DepthMessage | None:
    symbol = ""
    session_id = ""
    timestamp_raw = 0
    ask_levels: list[DepthLevel] = []
    bid_levels: list[DepthLevel] = []

    for field_number, wire_type, value in decode_fields(payload):
        if field_number == 1 and wire_type == WIRE_LENGTH_DELIMITED:
            symbol = value.decode("utf-8", "replace")
        elif field_number == 2 and wire_type == WIRE_LENGTH_DELIMITED:
            session_id = value.decode("utf-8", "replace")
        elif field_number == 3:
            timestamp_raw = int(value)
        elif field_number == 4 and wire_type == WIRE_LENGTH_DELIMITED:
            ask_levels.append(_decode_level(value))
        elif field_number == 5 and wire_type == WIRE_LENGTH_DELIMITED:
            bid_levels.append(_decode_level(value))

    if not symbol:
        return None
    return DepthMessage(
        symbol=symbol,
        session_id=session_id,
        timestamp_raw=timestamp_raw,
        ask_levels=ask_levels,
        bid_levels=bid_levels,
    )
