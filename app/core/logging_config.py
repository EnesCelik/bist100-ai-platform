import logging
import re
import sys

from app.core.config import settings

# Bu proje gercek broker kimlik bilgilerini (.env'de token/sifre/session key)
# tutuyor. Loglama eklendiginde bu degerlerin yanlislikla log satirlarina
# sizmasini onlemek icin JWT benzeri degerleri ve bilinen hassas alan
# isimlerinin degerlerini maskeliyoruz.
_JWT_PATTERN = re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")
_SENSITIVE_FIELD_PATTERN = re.compile(
    r"(?i)(password|token|api[_-]?key|session[_-]?key|secret|customer_no|account_id)"
    r"(\"?\s*[:=]\s*\"?)([^\"'\s,}]+)"
)


class RedactSensitiveDataFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        original_message = record.getMessage()
        redacted_message = _JWT_PATTERN.sub("<redacted-jwt>", original_message)
        redacted_message = _SENSITIVE_FIELD_PATTERN.sub(r"\1\2<redacted>", redacted_message)
        if redacted_message != original_message:
            record.msg = redacted_message
            record.args = ()
        return True


def configure_logging() -> None:
    resolved_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    handler.addFilter(RedactSensitiveDataFilter())

    root_logger = logging.getLogger()
    root_logger.setLevel(resolved_level)
    root_logger.handlers = [handler]
