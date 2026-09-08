"""Generic Protocol Buffers wire-format decoder.

Matriks'in gercek zamanli derinlik akisi resmi bir .proto semasi
yayinlamiyor; bu modul, yakalanan gercek mesajlari byte byte
inceleyerek cikarilan alan haritasina dayanir (bkz. depth_message.py).
Bu dosyadaki kod semadan bagimsiz, ham protobuf wire format cozucusudur.
"""
from __future__ import annotations

import struct

WIRE_VARINT = 0
WIRE_FIXED64 = 1
WIRE_LENGTH_DELIMITED = 2
WIRE_FIXED32 = 5


def _read_varint(data: bytes, offset: int) -> tuple[int, int]:
    result = 0
    shift = 0
    while True:
        byte = data[offset]
        result |= (byte & 0x7F) << shift
        offset += 1
        if not (byte & 0x80):
            return result, offset
        shift += 7


def decode_fields(data: bytes) -> list[tuple[int, int, object]]:
    """(field_number, wire_type, value) listesi doner. Length-delimited
    alanlar ham bytes olarak doner; cagiran taraf string/nested message
    olarak yorumlar."""
    fields: list[tuple[int, int, object]] = []
    offset = 0
    length = len(data)
    while offset < length:
        tag, offset = _read_varint(data, offset)
        field_number = tag >> 3
        wire_type = tag & 0x07

        if wire_type == WIRE_VARINT:
            value, offset = _read_varint(data, offset)
        elif wire_type == WIRE_FIXED64:
            value = struct.unpack_from("<d", data, offset)[0]
            offset += 8
        elif wire_type == WIRE_LENGTH_DELIMITED:
            field_length, offset = _read_varint(data, offset)
            value = data[offset : offset + field_length]
            offset += field_length
        elif wire_type == WIRE_FIXED32:
            value = struct.unpack_from("<f", data, offset)[0]
            offset += 4
        else:
            raise ValueError(f"Desteklenmeyen protobuf wire_type={wire_type} (offset={offset})")

        fields.append((field_number, wire_type, value))
    return fields
