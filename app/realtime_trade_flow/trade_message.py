"""Matriks "Pay Islem Tarafi Esanli" (uye bazli eslesen islem) PUBLISH
mesajlarini yorumlar.

Alan haritasi, gercek WebSocket trafigi byte byte incelenerek cikarildi
(depth ile ayni yontemle, bkz. realtime_depth/depth_message.py):
  field 1 (string)  -> sembol, orn. "GARAN"
  field 2 (string)  -> eslesen islem sira no (rakamlardan olusan string)
  field 3 (fixed32) -> fiyat
  field 4 (varint)  -> miktar (lot)
  field 5 (string)  -> taraf bayragi (tek karakter, orn. "a"); anlami tam
                        dogrulanmadigi icin analizde kullanilmiyor - alici/
                        satici uye kodlari (field 7/8) zaten yeterli
  field 6 (varint)  -> zaman damgasi (birim dogrulanmadi)
  field 7 (string)  -> alici uye kodu, orn. "IYF"
  field 8 (string)  -> satici uye kodu, orn. "YKR"
"""
from __future__ import annotations

from dataclasses import dataclass

from app.realtime_depth.protobuf_decoder import decode_fields


def _as_text(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return str(value) if value is not None else ""


@dataclass
class TradeTick:
    symbol: str
    trade_id: str
    price: float
    quantity: int
    side_flag: str
    timestamp_raw: int
    buyer_member_code: str
    seller_member_code: str


def parse_trade_message(payload: bytes) -> TradeTick | None:
    values: dict[int, object] = {}
    for field_number, _wire_type, value in decode_fields(payload):
        values[field_number] = value

    symbol = _as_text(values.get(1))
    if not symbol:
        return None

    return TradeTick(
        symbol=symbol,
        trade_id=_as_text(values.get(2)),
        price=float(values.get(3, 0.0)),
        quantity=int(values.get(4, 0)),
        side_flag=_as_text(values.get(5)),
        timestamp_raw=int(values.get(6, 0)),
        buyer_member_code=_as_text(values.get(7)),
        seller_member_code=_as_text(values.get(8)),
    )
