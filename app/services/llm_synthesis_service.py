import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path

import anthropic
from pydantic import BaseModel

from app.core.config import settings
from app.models.schemas import AnalysisEvidence, LlmTraceItem, LlmTraceSummaryResponse, RecommendationPolicyResult

logger = logging.getLogger(__name__)

TRACE_LOG_PATH = Path(__file__).resolve().parents[2] / "data" / "llm_traces.jsonl"

# Opus $5/$25, Sonnet $2/$10, Haiku $1/$5 per 1M token (giris/cikis).
_PRICE_PER_MILLION_TOKENS = {
    "claude-opus-5": (5.0, 25.0),
    "claude-sonnet-5": (2.0, 10.0),
    "claude-haiku-4-5": (1.0, 5.0),
}

_SYSTEM_PROMPT = (
    "Sen bir BIST hisse analiz asistanisin. Sana verilen kanit listesindeki (teknik, "
    "fundamental, makro, kurumsal akim vb.) pozitif ve negatif maddeleri dogal, akici "
    "bir Turkce paragrafa donusturuyorsun. Kurallar: sadece verilen kanitlari kullan, "
    "yeni sayi veya olgu uretme; yatirim tavsiyesi verme, sadece kanitlari sentezle; "
    "2-4 cumleyi gecme; spekulatif kesin ifadelerden kacin (\"artacaktir\" degil "
    "\"artis destekleyebilir\" gibi)."
)


class LlmSynthesisResult(BaseModel):
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    estimated_cost_usd: float


def _build_user_message(ticker: str, recommendation: RecommendationPolicyResult, evidence_items: list[AnalysisEvidence]) -> str:
    positive_lines = [f"- ({item.category}) {item.detail}" for item in evidence_items if item.impact == "positive"]
    negative_lines = [f"- ({item.category}) {item.detail}" for item in evidence_items if item.impact == "negative"]
    return (
        f"Ticker: {ticker}\n"
        f"Sistem sonucu: {recommendation.stance} / {recommendation.action}\n\n"
        f"Pozitif kanitlar:\n" + ("\n".join(positive_lines) or "(yok)") + "\n\n"
        f"Negatif kanitlar:\n" + ("\n".join(negative_lines) or "(yok)") + "\n\n"
        "Bu kanitlari sentezleyen kisa bir Turkce analiz paragrafi yaz."
    )


def _estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    input_price, output_price = _PRICE_PER_MILLION_TOKENS.get(model, (0.0, 0.0))
    return (input_tokens / 1_000_000 * input_price) + (output_tokens / 1_000_000 * output_price)


def _write_trace(**fields) -> None:
    try:
        TRACE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with TRACE_LOG_PATH.open("a", encoding="utf-8") as file:
            file.write(json.dumps({"timestamp": datetime.now(UTC).isoformat(), **fields}, ensure_ascii=False) + "\n")
    except OSError:
        logger.warning("LLM trace log yazilamadi", exc_info=True)


def synthesize_analysis_answer(
    ticker: str,
    recommendation: RecommendationPolicyResult,
    evidence_items: list[AnalysisEvidence],
) -> LlmSynthesisResult | None:
    if not settings.anthropic_api_key:
        return None

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key, timeout=settings.llm_timeout_seconds)
    user_message = _build_user_message(ticker, recommendation, evidence_items)

    started_at = time.perf_counter()
    try:
        response = client.messages.create(
            model=settings.llm_model,
            max_tokens=settings.llm_max_tokens,
            system=_SYSTEM_PROMPT,
            output_config={"effort": settings.llm_effort},
            messages=[{"role": "user", "content": user_message}],
        )
    except anthropic.APIError as exc:
        latency_ms = (time.perf_counter() - started_at) * 1000
        logger.warning("LLM synthesis failed for %s: %s", ticker, exc)
        _write_trace(ticker=ticker, model=settings.llm_model, status="error", error=str(exc), latency_ms=round(latency_ms, 1))
        return None

    latency_ms = (time.perf_counter() - started_at) * 1000
    text = "".join(block.text for block in response.content if block.type == "text").strip()
    if not text:
        _write_trace(ticker=ticker, model=settings.llm_model, status="empty_response", latency_ms=round(latency_ms, 1))
        return None

    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens
    estimated_cost_usd = _estimate_cost_usd(settings.llm_model, input_tokens, output_tokens)

    _write_trace(
        ticker=ticker,
        model=settings.llm_model,
        status="ok",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost_usd=round(estimated_cost_usd, 6),
        latency_ms=round(latency_ms, 1),
    )

    return LlmSynthesisResult(
        text=text,
        model=settings.llm_model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        estimated_cost_usd=estimated_cost_usd,
    )


def _load_trace_rows() -> list[dict]:
    if not TRACE_LOG_PATH.exists():
        return []
    rows: list[dict] = []
    with TRACE_LOG_PATH.open(encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def get_llm_trace_summary(limit: int = 20) -> LlmTraceSummaryResponse:
    rows = _load_trace_rows()
    ok_rows = [row for row in rows if row.get("status") == "ok"]
    error_rows = [row for row in rows if row.get("status") != "ok"]

    total_input_tokens = sum(int(row.get("input_tokens") or 0) for row in ok_rows)
    total_output_tokens = sum(int(row.get("output_tokens") or 0) for row in ok_rows)
    total_estimated_cost_usd = round(sum(float(row.get("estimated_cost_usd") or 0.0) for row in ok_rows), 6)
    latencies = [float(row["latency_ms"]) for row in ok_rows if row.get("latency_ms") is not None]
    average_latency_ms = round(sum(latencies) / len(latencies), 1) if latencies else None

    recent_rows = list(reversed(rows))[: max(limit, 1)]
    recent_traces = [
        LlmTraceItem(
            timestamp=row.get("timestamp", ""),
            ticker=row.get("ticker", ""),
            model=row.get("model", ""),
            status=row.get("status", "unknown"),
            input_tokens=row.get("input_tokens"),
            output_tokens=row.get("output_tokens"),
            estimated_cost_usd=row.get("estimated_cost_usd"),
            latency_ms=row.get("latency_ms"),
            error=row.get("error"),
        )
        for row in recent_rows
    ]

    summary = (
        f"Toplam {len(rows)} LLM sentez cagrisi kayitli; {len(ok_rows)} basarili, {len(error_rows)} basarisiz. "
        f"Toplam tahmini maliyet ${total_estimated_cost_usd:.4f}, ortalama gecikme "
        f"{average_latency_ms if average_latency_ms is not None else 'n/a'}ms."
    )

    return LlmTraceSummaryResponse(
        total_calls=len(rows),
        ok_count=len(ok_rows),
        error_count=len(error_rows),
        total_input_tokens=total_input_tokens,
        total_output_tokens=total_output_tokens,
        total_estimated_cost_usd=total_estimated_cost_usd,
        average_latency_ms=average_latency_ms,
        recent_traces=recent_traces,
        summary=summary,
    )
