import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

logger = logging.getLogger(__name__)

STATE_PATH = Path(__file__).resolve().parents[2] / "data" / "trading_safety_state.json"


class TradingSafetyStatusResponse(BaseModel):
    halted: bool
    reason: str | None = None
    triggered_by: str | None = None
    halted_at: str | None = None


def _load_state() -> dict:
    if not STATE_PATH.exists():
        return {"halted": False}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"halted": False}


def _save_state(state: dict) -> None:
    try:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError:
        logger.warning("Trading safety state yazilamadi", exc_info=True)


def is_trading_halted() -> bool:
    return bool(_load_state().get("halted", False))


def get_safety_status() -> TradingSafetyStatusResponse:
    state = _load_state()
    return TradingSafetyStatusResponse(
        halted=bool(state.get("halted", False)),
        reason=state.get("reason"),
        triggered_by=state.get("triggered_by"),
        halted_at=state.get("halted_at"),
    )


def halt_trading(reason: str, triggered_by: str = "manual") -> TradingSafetyStatusResponse:
    if is_trading_halted():
        return get_safety_status()
    state = {
        "halted": True,
        "reason": reason,
        "triggered_by": triggered_by,
        "halted_at": datetime.now(UTC).isoformat(),
    }
    _save_state(state)
    logger.warning("Trading halted (%s): %s", triggered_by, reason)
    return get_safety_status()


def resume_trading() -> TradingSafetyStatusResponse:
    _save_state({"halted": False})
    logger.info("Trading resumed manually")
    return get_safety_status()
