"""Token yenileme icin gece sessizligi (19:00-08:00 TR) penceresine testler.

Kullanici 2026-09-16'da bu saatler arasi Telegram'dan gelen "token onayla"
isteklerinin gereksiz oldugunu bildirdi (piyasa kapaliyken kimseyi
uyandirmaya gerek yok) - bu testler o pencerenin dogru hesaplandigini
garanti eder."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.runtime_scheduler_service import _is_within_token_refresh_quiet_hours

_TR = ZoneInfo("Europe/Istanbul")


def _at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 9, 16, hour, minute, tzinfo=_TR)


def test_quiet_at_19_00_boundary():
    # SINIR DEGERI: tam 19:00 sessizlik icinde sayilmali (>=).
    assert _is_within_token_refresh_quiet_hours(_at(19, 0)) is True


def test_not_quiet_just_before_19_00():
    assert _is_within_token_refresh_quiet_hours(_at(18, 59)) is False


def test_quiet_at_midnight():
    assert _is_within_token_refresh_quiet_hours(_at(0, 0)) is True


def test_quiet_just_before_08_00():
    assert _is_within_token_refresh_quiet_hours(_at(7, 59)) is True


def test_not_quiet_at_08_00_boundary():
    # SINIR DEGERI: tam 08:00'da sessizlik biter, normal akis devam eder (<).
    assert _is_within_token_refresh_quiet_hours(_at(8, 0)) is False


def test_not_quiet_during_trading_hours():
    assert _is_within_token_refresh_quiet_hours(_at(10, 30)) is False
    assert _is_within_token_refresh_quiet_hours(_at(17, 59)) is False


def test_defaults_to_real_now_when_no_argument_given():
    # Parametre verilmeden cagrilinca patlamamali - gercek saatle calisir.
    result = _is_within_token_refresh_quiet_hours()
    assert isinstance(result, bool)
