from app.models.schemas import AnalysisEvidence, RecommendationPolicyResult


def derive_recommendation(evidence_items: list[AnalysisEvidence]) -> RecommendationPolicyResult:
    positive_score = sum(1 for item in evidence_items if item.impact == "positive")
    negative_score = sum(1 for item in evidence_items if item.impact == "negative")
    net_score = positive_score - negative_score
    category_weights = {
        "signal": 1.0,
        "trade_level": 1.15,
        "trade_calibration": 1.35,
        "fundamental": 1.3,
        "institutional_flow": 1.2,
        "event": 1.6,
        "macro_event": 1.8,
    }

    weighted_positive_score = sum(
        category_weights.get(item.category, 1.0)
        for item in evidence_items
        if item.impact == "positive"
    )
    weighted_negative_score = sum(
        category_weights.get(item.category, 1.0)
        for item in evidence_items
        if item.impact == "negative"
    )
    weighted_net_score = round(weighted_positive_score - weighted_negative_score, 2)

    if weighted_net_score > 2.2:
        stance = "bullish"
    elif weighted_net_score < -2.2:
        stance = "bearish"
    else:
        stance = "neutral"

    action_map = {
        "bullish": "buy",
        "neutral": "hold",
        "bearish": "reduce",
    }
    action = action_map[stance]

    summary = (
        f"Positive evidence: {positive_score}, negative evidence: {negative_score}, "
        f"net score: {net_score}. Weighted net score: {weighted_net_score}. "
        f"Policy sonucu {stance} ve action olarak {action} uretildi."
    )

    return RecommendationPolicyResult(
        stance=stance,
        action=action,
        score=net_score,
        weighted_score=weighted_net_score,
        summary=summary,
    )
