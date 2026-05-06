from __future__ import annotations

import random
import re
import threading
import time
from datetime import UTC, datetime, timedelta
from urllib import parse, request

from app.core.config import settings
from app.models.schemas import GarantiSsoCompleteResponse, GarantiSsoStartResponse
from app.data_sources.market_data.matriks_provider import (
    decode_market_data_token_expiry,
    login_with_bridge_credentials,
)

_SSO_SESSIONS: dict[str, datetime] = {}
_SESSION_LOCK = threading.Lock()
_DATE_PATTERN = re.compile(r"^UTC(?P<date>\d{8}) (?P<time>\d{2}:\d{2}:\d{2}\.\d{3})$")


def _cleanup_sessions() -> None:
    cutoff = datetime.now(UTC) - timedelta(minutes=15)
    with _SESSION_LOCK:
        expired = [key for key, created_at in _SSO_SESSIONS.items() if created_at < cutoff]
        for key in expired:
            _SSO_SESSIONS.pop(key, None)


def _register_session(client_state: str) -> None:
    _cleanup_sessions()
    with _SESSION_LOCK:
        _SSO_SESSIONS[client_state] = datetime.now(UTC)


def _parse_utc_date(raw_value: str) -> datetime:
    match = _DATE_PATTERN.match(raw_value.strip())
    if match is None:
        raise ValueError(f"Unexpected UTCDate.aspx response: {raw_value!r}")
    date_part = match.group("date")
    time_part = match.group("time")
    return datetime.strptime(f"{date_part} {time_part}", "%Y%m%d %H:%M:%S.%f").replace(tzinfo=UTC)


def _crc16_reverse(data: bytes) -> int:
    crc = 0
    for value in data:
        crc ^= value
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0x8408
            else:
                crc >>= 1
    return crc & 0xFFFF


def _fixed_length(value: str, width: int) -> str:
    return (("0" * (width + 1)) + value)[-width:]


def _random_component(digits: int) -> int:
    return round(random.random() * (10**digits))


def _generate_client_state(utc_date: datetime) -> str:
    date_component = _fixed_length(f"{utc_date.year * 10000 + utc_date.month * 100 + utc_date.day:x}", 10)
    time_numeric = (
        utc_date.hour * 10_000_000
        + utc_date.minute * 100_000
        + utc_date.second * 1_000
        + int(utc_date.microsecond / 1_000)
    )
    time_component = _fixed_length(f"{time_numeric:x}", 10)
    seconds_since_2013 = round((datetime.now() - datetime(2013, 1, 1)).total_seconds())
    diff_component = _fixed_length(str(seconds_since_2013), 9)
    random4 = _fixed_length(str(_random_component(4)), 4)
    mask_seed = _random_component(5)
    masked_component = (
        _fixed_length(str(_random_component(5) + mask_seed), 5)
        + _fixed_length(str(_random_component(6) + mask_seed), 6)
        + _fixed_length(str(mask_seed), 5)
    )
    random10_a = _fixed_length(str(_random_component(10)), 10)
    random10_b = _fixed_length(str(_random_component(10)), 10)
    partial = date_component + time_component + diff_component + random4 + masked_component + random10_a + random10_b
    crc_component = _fixed_length(f"{_crc16_reverse(partial.encode('ascii')):x}", 5)
    return partial + crc_component


def _post_form(url: str, body: str, timeout_seconds: float) -> str:
    req = request.Request(
        url,
        data=body.encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with request.urlopen(req, timeout=timeout_seconds) as response:
        return response.read().decode("utf-8")


def _download_sso_utc_date() -> datetime:
    raw_value = _post_form(
        settings.matriks_sso_date_service.strip(),
        f"mtxTime{int(time.time() * 1000)}",
        timeout_seconds=settings.matriks_timeout_seconds,
    )
    return _parse_utc_date(raw_value)


def _build_login_query(client_state: str) -> str:
    query_params = {
        "client_state": client_state,
        "r": "1",
        "Language": settings.matriks_language.strip() or "tr",
        "SourceID": settings.matriks_source_id.strip() or "40",
        "tid": settings.matriks_sso_tid.strip() or "prodTr",
    }
    return parse.urlencode(query_params)


def _parse_hashkey_response(raw_value: str) -> dict[str, str]:
    parsed = {"state": "FAIL", "MSG": "", "URT": "", "HAS": ""}
    for index, line in enumerate(raw_value.strip().splitlines()):
        normalized = line.strip()
        if index == 0:
            parsed["state"] = normalized.upper()
            continue
        if ":" not in normalized:
            continue
        key, value = normalized.split(":", 1)
        parsed[key.strip()] = value.strip()
    return parsed


def _fetch_hashkey_credentials(client_state: str) -> dict[str, str]:
    body = parse.urlencode(
        {
            "client_state": client_state,
            "SourceID": settings.matriks_source_id.strip() or "40",
            "mtxTime": str(int(time.time() * 1000)),
        }
    )
    raw_value = _post_form(
        settings.matriks_sso_hashkey_service.strip(),
        body,
        timeout_seconds=settings.matriks_timeout_seconds,
    )
    return _parse_hashkey_response(raw_value)


def start_garanti_sso_login() -> GarantiSsoStartResponse:
    utc_date = _download_sso_utc_date()
    client_state = _generate_client_state(utc_date)
    _register_session(client_state)
    login_url = f"{settings.matriks_sso_login_service.strip()}?{_build_login_query(client_state)}"
    return GarantiSsoStartResponse(
        status="pending_approval",
        client_state=client_state,
        login_url=login_url,
        next_step="Open login_url in the browser, complete Garanti mobile approval, then call the complete endpoint with the same client_state.",
    )


def complete_garanti_sso_login(
    client_state: str,
    wait_seconds: int = 60,
    poll_interval_seconds: float = 2.0,
) -> GarantiSsoCompleteResponse:
    deadline = time.time() + max(wait_seconds, 0)
    last_message = "Garanti mobile approval is still pending."

    while True:
        credentials = _fetch_hashkey_credentials(client_state)
        if credentials.get("state") == "OK" and credentials.get("URT") and credentials.get("HAS"):
            token = login_with_bridge_credentials(
                username=credentials["URT"],
                password=credentials["HAS"],
            )
            expiry = decode_market_data_token_expiry(token)
            if token:
                return GarantiSsoCompleteResponse(
                    status="token_acquired",
                    token_acquired=True,
                    expires_at=expiry.isoformat() if expiry is not None else None,
                    message="Garanti SSO flow completed and MarketDataToken was refreshed.",
                )
            return GarantiSsoCompleteResponse(
                status="login_failed",
                token_acquired=False,
                expires_at=None,
                message="Garanti hashkey succeeded but Integration.aspx did not return a MarketDataToken.",
            )

        if credentials.get("MSG"):
            last_message = credentials["MSG"]

        if time.time() >= deadline:
            return GarantiSsoCompleteResponse(
                status="pending_approval",
                token_acquired=False,
                expires_at=None,
                message=last_message,
            )

        time.sleep(poll_interval_seconds)
