"""MQTT v3.1 ("MQIsdp") paket kodlama/cozme - Matriks'in gercek zamanli
derinlik akisinda kullandigi eski protokol suru. Genel amacli bir MQTT
kutuphanesi yerine, sadece bu akis icin gereken minimum paket tipleri
(CONNECT/CONNACK/SUBSCRIBE/SUBACK/PUBLISH/PINGREQ/PINGRESP) elle
kodlanmistir - boylece WebSocket alt-protokolu ("mqttv3.1") ve CONNECT
bayraklari uzerinde tam kontrol elimizde kalir.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass

MSG_CONNACK = 2
MSG_PUBLISH = 3
MSG_SUBACK = 9
MSG_PINGRESP = 13


def _encode_varint(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            break
    return bytes(out)


def _decode_varint(data: bytes, offset: int) -> tuple[int, int]:
    result = 0
    shift = 0
    while True:
        byte = data[offset]
        result |= (byte & 0x7F) << shift
        offset += 1
        if not (byte & 0x80):
            return result, offset
        shift += 7


def _encode_string(value: str) -> bytes:
    raw = value.encode("utf-8")
    return struct.pack(">H", len(raw)) + raw


def build_connect_packet(client_id: str, username: str, password: str, keepalive: int = 60) -> bytes:
    # Connect flags 0xC2: username(1) + password(1) + will(0) + clean-session(1)
    variable_header = _encode_string("MQIsdp") + bytes([0x03, 0xC2]) + struct.pack(">H", keepalive)
    payload = _encode_string(client_id) + _encode_string(username) + _encode_string(password)
    body = variable_header + payload
    return bytes([0x10]) + _encode_varint(len(body)) + body


def build_subscribe_packet(packet_id: int, topic: str, qos: int = 0) -> bytes:
    body = struct.pack(">H", packet_id) + _encode_string(topic) + bytes([qos])
    return bytes([0x82]) + _encode_varint(len(body)) + body


def build_unsubscribe_packet(packet_id: int, topic: str) -> bytes:
    body = struct.pack(">H", packet_id) + _encode_string(topic)
    return bytes([0xA2]) + _encode_varint(len(body)) + body


def build_pingreq_packet() -> bytes:
    return bytes([0xC0, 0x00])


def build_disconnect_packet() -> bytes:
    return bytes([0xE0, 0x00])


@dataclass
class DecodedPacket:
    msg_type: int
    flags: int
    body: bytes


def decode_packet(frame: bytes) -> DecodedPacket:
    first = frame[0]
    msg_type = first >> 4
    flags = first & 0x0F
    remaining_length, offset = _decode_varint(frame, 1)
    body = frame[offset : offset + remaining_length]
    return DecodedPacket(msg_type=msg_type, flags=flags, body=body)


@dataclass
class PublishPacket:
    topic: str
    payload: bytes


def decode_publish(body: bytes) -> PublishPacket:
    topic_len = struct.unpack_from(">H", body, 0)[0]
    topic = body[2 : 2 + topic_len].decode("utf-8", "replace")
    payload = body[2 + topic_len :]
    return PublishPacket(topic=topic, payload=payload)
