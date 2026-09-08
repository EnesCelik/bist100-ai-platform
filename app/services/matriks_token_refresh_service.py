"""MATRIKS_MARKET_DATA_TOKEN'in suresi dolmadan otomatik yenilenmesi.

matriks_provider.py'nin kendi REST cagrilari zaten ayri bir runtime-token
holder'i uzerinden auto-login yapabiliyor, ama bu, `settings.matriks_market_data_token`'i
hic guncellemiyor - dolayisiyla realtime_depth ve realtime_trade_flow
WebSocket client'lari (token'i dogrudan settings'ten okuyor) bundan
faydalanamiyordu. Bu servis, `settings.matriks_market_data_token`'i dogrudan
guncelleyerek REST, depth ve trade-flow'un ayni tek token'da bulusmasini
saglar.

Canli testte dogrudan kullanici adi/sifre login'i her seferinde
Integration.aspx'ten Code=3004 (State=false) donuyor - yani Garanti bu hesap
icin dogrudan login'i her defasinda reddediyor, muhtemelen guvenilir cihaz/IP
esleme veya mobil onay zorunlulugu yuzunden. Bu yuzden dogrudan login'i hic
denemiyoruz (bkz. asagidaki not) ve tek yol olarak SSO/mobil-onay akisina
(garanti_sso_service.py) gidiyoruz: kullaniciya Telegram'dan bir onay linki
gonderilir, kullanici Garanti mobil uygulamasinda onaylar, biz de arka planda
birkac dakika polluyoruz. Bu tam otomatik degil ama DevTools'tan JWT
kopyalamaktan cok daha az zahmetli.

NOT: Daha once bu fonksiyon SSO'dan once gercek kullanici adi/sifreyle bir
"dogrudan login" denemesi de yapiyordu. Hicbir zaman basarili olmadigi
(daima Code=3004) halde her denemede gercek kimlik bilgileriyle Integration.aspx'e
bir login istegi gonderiyordu - bu, kullanicinin kendi aktif tarayici
oturumunun bir suphesiz guvenlik onlemi olarak dusurulmesine yol acmis
olabilir (kullanici, uygulamayi actiginda 1-2 dk icinde oturumun kapandigini
bildirdi). Hicbir zaman ise yaramayan bu denemeyi kaldirdik.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.core.config import settings
from app.data_sources.market_data.matriks_provider import (
    decode_market_data_token_expiry,
    get_runtime_market_data_token,
)
from app.services.garanti_sso_service import complete_garanti_sso_login, start_garanti_sso_login
from app.services.telegram_service import send_telegram_message

logger = logging.getLogger(__name__)

_SSO_APPROVAL_WAIT_SECONDS = 120
_SSO_NOTIFY_COOLDOWN_MINUTES = 20
_last_sso_notify_at: datetime | None = None


@dataclass
class TokenRefreshResult:
    status: str  # "skipped_fresh" | "refreshed" | "pending_approval" | "failed" | "skipped_no_credentials"
    message: str
    expires_at: str | None = None


def _should_notify_sso() -> bool:
    global _last_sso_notify_at
    now = datetime.now(UTC)
    if _last_sso_notify_at is not None and now - _last_sso_notify_at < timedelta(minutes=_SSO_NOTIFY_COOLDOWN_MINUTES):
        return False
    _last_sso_notify_at = now
    return True


def refresh_market_data_token_if_needed(buffer_minutes: int) -> TokenRefreshResult:
    current_token = settings.matriks_market_data_token.strip()
    expiry = decode_market_data_token_expiry(current_token) if current_token else None
    now = datetime.now(UTC)

    if expiry is not None and expiry - now > timedelta(minutes=buffer_minutes):
        return TokenRefreshResult(
            status="skipped_fresh",
            message=f"Token hala gecerli, bitis={expiry.isoformat()}",
            expires_at=expiry.isoformat(),
        )

    try:
        sso_start = start_garanti_sso_login()
    except Exception as exc:  # noqa: BLE001
        return TokenRefreshResult(status="failed", message=f"SSO baslatilamadi: {exc}")

    if _should_notify_sso():
        send_telegram_message(
            "Matriks/Garanti MarketDataToken suresi doluyor, otomatik yenileme icin "
            "mobil onayin gerekiyor.\n\n"
            f"Onaylamak icin: {sso_start.login_url}\n\n"
            "Onayladiktan sonra token birkac dakika icinde otomatik guncellenecek."
        )

    complete = complete_garanti_sso_login(
        client_state=sso_start.client_state,
        wait_seconds=_SSO_APPROVAL_WAIT_SECONDS,
        poll_interval_seconds=2.0,
    )
    if complete.token_acquired:
        refreshed_token = get_runtime_market_data_token()
        if refreshed_token:
            settings.matriks_market_data_token = refreshed_token
        return TokenRefreshResult(
            status="refreshed",
            message="Token Garanti mobil onayi ile yenilendi",
            expires_at=complete.expires_at,
        )
    if complete.status == "pending_approval":
        return TokenRefreshResult(
            status="pending_approval",
            message=f"Mobil onay bekleniyor: {sso_start.login_url}",
        )
    return TokenRefreshResult(status="failed", message=complete.message)
