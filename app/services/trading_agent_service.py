from datetime import datetime

from app.models.schemas import (
    ManualBasketCreateRequest,
    ManualBasketPositionRequest,
    TradingAgentCandidateDecision,
    TradingAgentCycleResponse,
    TradingAgentOpeningPlanRequest,
    TradingAgentPositionDecision,
    TradingAgentReduceResponse,
    TradingAgentStatusResponse,
)
from app.services.trading_agent_decision_service import get_latest_agent_decisions, save_agent_cycle_decisions
from app.services.market_scan_service import scan_opening_candidates
from app.services.paper_trade_simulation_service import (
    create_manual_basket,
    close_fully_realized_trades,
    finalize_open_trades,
    get_daily_paper_trade_report,
    get_paper_trades,
    monitor_open_trades,
    reduce_open_trades,
)
from app.services.trading_agent_learning_weights_service import build_next_session_weight_adjustments
from app.services.trading_agent_signal_service import (
    allocate_capital_by_score,
    detect_regime_from_opening_candidates,
    score_opening_candidate,
)


def _default_strategy_name(prefix: str) -> str:
    return f"{prefix}_{datetime.now().strftime('%Y_%m_%d')}"


def _unrealized_pnl(trade) -> float:
    return round(float(getattr(trade, "open_unrealized_pnl", trade.capital_allocated * (trade.current_return_percent / 100))), 2)


def _realized_pnl(trade) -> float:
    return round(float(getattr(trade, "realized_pnl", 0.0)), 2)


def _total_position_pnl(trade) -> float:
    return round(float(getattr(trade, "total_position_pnl", _realized_pnl(trade) + _unrealized_pnl(trade))), 2)


def _remaining_capital(trade) -> float:
    return round(float(getattr(trade, "remaining_capital", trade.capital_allocated)), 2)


def _distance_to_stop_percent(trade) -> float | None:
    if trade.current_price <= 0 or trade.stop_price <= 0:
        return None
    return round(((trade.current_price - trade.stop_price) / trade.current_price) * 100, 2)


def _build_position_decision(trade) -> TradingAgentPositionDecision:
    distance_to_stop = _distance_to_stop_percent(trade)
    current_return = round(float(trade.current_return_percent), 2)
    max_return = round(float(trade.max_intraday_return_percent), 2)
    min_return = round(float(trade.min_intraday_return_percent), 2)
    realized_percent = round(float(getattr(trade, "realized_percent", 0.0) or 0.0), 2)

    if trade.stop_hit:
        action = "exit"
        priority = 100
        rationale = "Stop seviyesi tetiklenmis; simülasyonda pozisyon kapatma adayi."
    elif realized_percent >= 50.0 and current_return <= -3.0:
        action = "exit"
        priority = 96
        rationale = "Pozisyon zaten kismi azaltildi ve zarar derinlesiyor; kalan pozisyonu kapatma adayi."
    elif realized_percent >= 50.0:
        action = "watch_reduced_position"
        priority = 62
        rationale = "Pozisyon kismi azaltildi; kalan kisim stop veya toparlanma teyidine kadar izlenmeli."
    elif distance_to_stop is not None and distance_to_stop <= 0.35:
        action = "reduce_or_exit"
        priority = 92
        rationale = "Fiyat stop seviyesine cok yakin; riski azaltmak veya cikis planlamak gerekir."
    elif current_return <= -2.0:
        action = "reduce_or_exit"
        priority = 88
        rationale = "Pozisyon %-2 altina indi; momentum beklentisi bozuldugu icin risk azaltma oncelikli."
    elif current_return <= -1.0 and min_return <= -1.0:
        action = "watch_for_reversal"
        priority = 72
        rationale = "Pozisyon zayif acildi; stopa kadar alan var ama toparlanma teyidi beklenmeli."
    elif trade.profit_protected:
        action = "hold_with_protected_profit"
        priority = 55
        rationale = "Kar koruma aktif; pozisyon tasinabilir ama yukseltilmis stop izlenmeli."
    elif current_return >= 1.0 or max_return >= 1.0:
        action = "hold"
        priority = 50
        rationale = "Pozisyon pozitif bolgede; kar hedefleri ve kar koruma seviyeleri izlenmeli."
    elif current_return >= 0:
        action = "hold"
        priority = 40
        rationale = "Pozisyon negatif degil; acele aksiyon gerekmiyor."
    else:
        action = "watch"
        priority = 35
        rationale = "Hafif negatif; stopa uzak oldugu surece izleme yeterli."

    return TradingAgentPositionDecision(
        ticker=trade.ticker,
        action=action,
        priority=priority,
        current_return_percent=current_return,
        max_intraday_return_percent=max_return,
        min_intraday_return_percent=min_return,
        distance_to_stop_percent=distance_to_stop,
        capital_allocated=round(float(trade.capital_allocated), 2),
        realized_percent=realized_percent,
        remaining_capital=_remaining_capital(trade),
        realized_pnl=_realized_pnl(trade),
        open_unrealized_pnl=_unrealized_pnl(trade),
        total_position_pnl=_total_position_pnl(trade),
        rationale=rationale,
    )


def _portfolio_risk_level(position_decisions: list[TradingAgentPositionDecision]) -> str:
    if not position_decisions:
        return "none"
    urgent_count = sum(1 for item in position_decisions if item.action in {"exit", "reduce_or_exit"})
    weak_count = sum(1 for item in position_decisions if item.current_return_percent < 0)
    if urgent_count >= 2:
        return "high"
    if urgent_count == 1 or weak_count >= max(3, len(position_decisions) // 2 + 1):
        return "medium"
    return "low"


def _cash_decision(position_decisions: list[TradingAgentPositionDecision], total_unrealized_pnl: float) -> tuple[str, str]:
    urgent = [item for item in position_decisions if item.action in {"exit", "reduce_or_exit"}]
    strong = [item for item in position_decisions if item.action.startswith("hold") and item.current_return_percent > 0]
    if urgent:
        tickers = ", ".join(item.ticker for item in urgent[:3])
        return "hold_cash", f"{tickers} risk azaltma adayi; nakit yeni alim yerine tampon olarak tutulmali."
    if total_unrealized_pnl < 0:
        return "hold_cash", "Sepet toplamda ekside; nakit ile ortalama dusurmek yerine teyit beklenmeli."
    if strong and len(strong) >= 2:
        tickers = ", ".join(item.ticker for item in strong[:3])
        return "selective_add_watch", f"{tickers} goreli guclu; ancak ek alim icin 15 dk daha hacim/fiyat teyidi beklenmeli."
    return "hold_cash", "Belirgin ek alim sinyali yok; nakit korunmali."


def evaluate_open_positions(strategy_name: str | None = None, persist: bool = True) -> list[TradingAgentPositionDecision]:
    close_fully_realized_trades(strategy_name=strategy_name)
    open_trades = get_paper_trades(limit=50, status="open", strategy_name=strategy_name)
    decisions = sorted(
        [_build_position_decision(item) for item in open_trades.items],
        key=lambda item: (item.priority, abs(item.current_return_percent)),
        reverse=True,
    )
    if persist and decisions:
        response = TradingAgentCycleResponse(
            phase="position_decision",
            strategy_name=strategy_name or (open_trades.items[0].strategy_name if open_trades.items else "all_open_strategies"),
            generated_at=datetime.utcnow().isoformat(),
            action="evaluated_open_positions",
            decisions=[
                TradingAgentCandidateDecision(
                    ticker=item.ticker,
                    action=item.action,
                    score=float(item.priority),
                    entry_price=None,
                    capital_allocated=item.capital_allocated,
                    rationale=item.rationale,
                )
                for item in decisions
            ],
        )
        save_agent_cycle_decisions(response)
    return decisions


def simulate_reduce_or_exit(strategy_name: str | None = None, reduce_percent: float = 50.0) -> TradingAgentReduceResponse:
    strategy = strategy_name or "all_open_strategies"
    decisions = evaluate_open_positions(strategy_name=strategy_name, persist=False)
    tickers = [item.ticker for item in decisions if item.action in {"reduce_or_exit", "exit"}]
    exit_tickers = [item.ticker for item in decisions if item.action == "exit"]
    reduce_tickers = [item.ticker for item in decisions if item.action == "reduce_or_exit"]
    reduced = reduce_open_trades(tickers=reduce_tickers, strategy_name=strategy_name, reduce_percent=reduce_percent)
    exited = reduce_open_trades(tickers=exit_tickers, strategy_name=strategy_name, reduce_percent=100.0)
    reduced.items.extend(exited.items)
    reduced.reduced_count += exited.reduced_count
    reduced.skipped_count += exited.skipped_count

    response = TradingAgentCycleResponse(
        phase="reduce_or_exit",
        strategy_name=strategy,
        generated_at=datetime.utcnow().isoformat(),
        action="simulated_partial_reduce",
        decisions=[
            TradingAgentCandidateDecision(
                ticker=item.ticker,
                action="simulated_reduce" if item.ticker in tickers else item.action,
                score=float(item.priority),
                entry_price=None,
                capital_allocated=item.capital_allocated,
                rationale=(
                    f"{item.rationale} Simülasyonda %{reduce_percent} realize edildi."
                    if item.ticker in tickers
                    else item.rationale
                ),
            )
            for item in decisions
            if item.ticker in tickers
        ],
    )
    save_agent_cycle_decisions(response)

    return TradingAgentReduceResponse(
        generated_at=datetime.utcnow().isoformat(),
        strategy_name=strategy,
        reduce_percent=reduce_percent,
        reduced=reduced,
        status=get_trading_agent_status(strategy_name=strategy_name),
    )


def run_opening_plan(request: TradingAgentOpeningPlanRequest) -> TradingAgentCycleResponse:
    strategy_name = request.strategy_name or _default_strategy_name("agent_opening_basket")
    generated_at = datetime.utcnow().isoformat()
    scan = scan_opening_candidates(limit=max(request.limit * 2, request.limit))
    regime = detect_regime_from_opening_candidates(scan.items)
    learning_weights = build_next_session_weight_adjustments()
    learning_adjustments = learning_weights.adjustments
    scored_candidates = [
        score_opening_candidate(item, regime=regime, learning_adjustments=learning_adjustments)
        for item in scan.items
    ]
    scored_candidates.sort(key=lambda item: (item.agent_score, -len(item.risks)), reverse=True)
    scored_by_ticker = {item.ticker: item for item in scored_candidates}
    items_by_ticker = {item.ticker: item for item in scan.items}
    min_agent_score = max(request.min_opening_score, 58.0) + learning_adjustments.get("min_agent_score_delta", 0.0)
    effective_cash_buffer = request.cash_buffer * (1 + (learning_adjustments.get("cash_buffer_delta_percent", 0.0) / 100))

    selected = [
        items_by_ticker[item.ticker]
        for item in scored_candidates
        if (
            item.ticker in items_by_ticker
            and items_by_ticker[item.ticker].last_price is not None
            and items_by_ticker[item.ticker].last_price > 0
            and item.agent_score >= min_agent_score
            and item.suggested_action in {"open", "open_small"}
        )
    ][: request.limit]

    selected_scores = [scored_by_ticker[item.ticker] for item in selected]
    allocations = allocate_capital_by_score(
        selected_scores,
        total_capital=request.total_capital,
        cash_buffer=effective_cash_buffer,
        regime=regime,
    )

    decisions: list[TradingAgentCandidateDecision] = []
    positions: list[ManualBasketPositionRequest] = []
    selected_tickers = {item.ticker for item in selected}

    for item in selected:
        entry_price = float(item.last_price)
        signal = scored_by_ticker[item.ticker]
        allocation = allocations.get(item.ticker, 0.0)
        if allocation <= 0:
            continue
        signal.suggested_capital = allocation
        positions.append(
            ManualBasketPositionRequest(
                ticker=item.ticker,
                entry_price=entry_price,
                capital_allocated=allocation,
                scenario=f"agent_{signal.signal_label}",
            )
        )
        decisions.append(
            TradingAgentCandidateDecision(
                ticker=item.ticker,
                action="open",
                score=round(float(item.opening_score), 2),
                agent_score=signal.agent_score,
                risk_label=signal.risk_label,
                entry_price=entry_price,
                capital_allocated=round(allocation, 2),
                rationale=(
                    f"Agent score {signal.agent_score} ({signal.signal_label}) ile esigi gecti. "
                    f"Regime={regime.regime}. "
                    f"Learning={learning_weights.trade_date}. "
                    f"Sebep: {'; '.join(signal.reasons[:2]) if signal.reasons else 'sinyal agirliklari yeterli'}."
                ),
            )
        )

    for signal in scored_candidates:
        item = items_by_ticker[signal.ticker]
        if item.ticker in selected_tickers:
            continue
        decisions.append(
            TradingAgentCandidateDecision(
                ticker=item.ticker,
                action="watch" if signal.agent_score >= min_agent_score else "skip",
                score=round(float(item.opening_score), 2),
                agent_score=signal.agent_score,
                risk_label=signal.risk_label,
                entry_price=float(item.last_price) if item.last_price is not None else None,
                capital_allocated=None,
                rationale=(
                    f"Agent score {signal.agent_score}; secilmedi. "
                    f"Risk={signal.risk_label}. "
                    f"Not: {'; '.join(signal.risks[:2]) if signal.risks else 'rank/limit/sermaye siniri'}."
                ),
            )
        )

    opened = None
    action = "watch_only"
    if positions:
        opened = create_manual_basket(ManualBasketCreateRequest(strategy_name=strategy_name, positions=positions))
        action = "opened_paper_basket"

    response = TradingAgentCycleResponse(
        phase="opening_plan",
        strategy_name=strategy_name,
        generated_at=generated_at,
        action=action,
        cash_buffer=round(effective_cash_buffer, 2),
        decisions=decisions,
        regime=regime,
        signal_scores=scored_candidates,
        opened=opened,
    )
    save_agent_cycle_decisions(response)
    return response


def run_monitor_cycle(strategy_name: str | None = None) -> TradingAgentCycleResponse:
    monitored = monitor_open_trades()
    position_decisions = evaluate_open_positions(strategy_name=strategy_name, persist=True)
    response = TradingAgentCycleResponse(
        phase="monitor",
        strategy_name=strategy_name or "all_open_strategies",
        generated_at=datetime.utcnow().isoformat(),
        action="monitored_open_trades",
        decisions=[
            TradingAgentCandidateDecision(
                ticker=item.ticker,
                action=item.action,
                score=float(item.priority),
                entry_price=None,
                capital_allocated=item.capital_allocated,
                rationale=item.rationale,
            )
            for item in position_decisions
        ],
        monitored=monitored,
    )
    save_agent_cycle_decisions(response)
    return response


def run_finalize_cycle(strategy_name: str | None = None) -> TradingAgentCycleResponse:
    response = TradingAgentCycleResponse(
        phase="finalize",
        strategy_name=strategy_name or "all_open_strategies",
        generated_at=datetime.utcnow().isoformat(),
        action="finalized_open_trades",
        finalized=finalize_open_trades(),
    )
    save_agent_cycle_decisions(response)
    return response


def get_agent_daily_report(trade_date: str | None = None, strategy_name: str | None = None) -> TradingAgentCycleResponse:
    report = get_daily_paper_trade_report(trade_date=trade_date, strategy_name=strategy_name)
    response = TradingAgentCycleResponse(
        phase="report",
        strategy_name=strategy_name or "all_strategies",
        generated_at=datetime.utcnow().isoformat(),
        action="generated_daily_report",
        report=report,
    )
    save_agent_cycle_decisions(response)
    return response


def get_trading_agent_status(strategy_name: str | None = None) -> TradingAgentStatusResponse:
    close_fully_realized_trades(strategy_name=strategy_name)
    active_strategy_name = strategy_name
    latest_decisions = get_latest_agent_decisions(limit=20, strategy_name=strategy_name)
    if active_strategy_name is None and latest_decisions:
        active_strategy_name = latest_decisions[0].strategy_name

    if active_strategy_name is None:
        all_open_trades = get_paper_trades(limit=50, status="open").items
        capital_by_strategy: dict[str, float] = {}
        for item in all_open_trades:
            capital_by_strategy[item.strategy_name] = capital_by_strategy.get(item.strategy_name, 0.0) + float(item.capital_allocated)
        if capital_by_strategy:
            active_strategy_name = max(capital_by_strategy, key=capital_by_strategy.get)
        elif all_open_trades:
            active_strategy_name = all_open_trades[0].strategy_name

    open_trades = get_paper_trades(limit=50, status="open", strategy_name=active_strategy_name) if active_strategy_name else get_paper_trades(limit=50, status="open")
    latest_decisions = get_latest_agent_decisions(limit=20, strategy_name=active_strategy_name) if active_strategy_name else latest_decisions
    closed_trades = get_paper_trades(limit=100, status="closed", strategy_name=active_strategy_name) if active_strategy_name else get_paper_trades(limit=100, status="closed")
    position_decisions = evaluate_open_positions(strategy_name=active_strategy_name, persist=False)

    latest_report = None
    if active_strategy_name:
        latest_report = get_daily_paper_trade_report(strategy_name=active_strategy_name)

    total_capital = round(sum(item.capital_allocated for item in open_trades.items), 2)
    closed_capital = round(sum(item.capital_allocated for item in closed_trades.items), 2)
    deployed_capital = round(total_capital + closed_capital, 2)
    total_remaining_capital = round(sum(_remaining_capital(item) for item in open_trades.items), 2)
    open_realized_pnl = round(sum(_realized_pnl(item) for item in open_trades.items), 2)
    closed_realized_pnl = round(sum(item.total_position_pnl for item in closed_trades.items), 2)
    total_realized_pnl = round(open_realized_pnl + closed_realized_pnl, 2)
    total_open_unrealized_pnl = round(sum(_unrealized_pnl(item) for item in open_trades.items), 2)
    total_position_pnl = round(total_realized_pnl + total_open_unrealized_pnl, 2)
    released_capital = round(sum(item.capital_allocated - item.remaining_capital for item in open_trades.items), 2)
    available_cash = round(closed_capital + released_capital + total_realized_pnl, 2)
    portfolio_equity = round(total_remaining_capital + available_cash + total_open_unrealized_pnl, 2)
    avg_return = None
    if open_trades.items:
        avg_return = round(sum(item.current_return_percent for item in open_trades.items) / len(open_trades.items), 2)
    cash_action, cash_rationale = _cash_decision(position_decisions, total_position_pnl)
    risk_level = _portfolio_risk_level(position_decisions)
    next_check_minutes = 5 if risk_level == "high" else 10 if risk_level == "medium" else 15

    summary = (
        f"Open trades={open_trades.total}, active_strategy={active_strategy_name or 'none'}, "
        f"deployed_capital={deployed_capital}, remaining_capital={total_remaining_capital}, "
        f"available_cash={available_cash}, realized_pnl={total_realized_pnl}, "
        f"open_unrealized_pnl={total_open_unrealized_pnl}, total_pnl={total_position_pnl}, "
        f"portfolio_equity={portfolio_equity}, risk={risk_level}"
    )
    if avg_return is not None:
        summary += f", avg_open_return={avg_return}%"

    return TradingAgentStatusResponse(
        generated_at=datetime.utcnow().isoformat(),
        active_strategy_name=active_strategy_name,
        open_trade_count=open_trades.total,
        open_trades=open_trades.items,
        closed_trade_count=closed_trades.total,
        closed_trades=closed_trades.items,
        position_decisions=position_decisions,
        cash_action=cash_action,
        cash_rationale=cash_rationale,
        open_realized_pnl=open_realized_pnl,
        closed_realized_pnl=closed_realized_pnl,
        total_realized_pnl=total_realized_pnl,
        total_open_unrealized_pnl=total_open_unrealized_pnl,
        total_position_pnl=total_position_pnl,
        total_unrealized_pnl=total_open_unrealized_pnl,
        deployed_capital=deployed_capital,
        total_remaining_capital=total_remaining_capital,
        available_cash=available_cash,
        portfolio_equity=portfolio_equity,
        average_open_return_percent=avg_return,
        portfolio_risk_level=risk_level,
        recommended_next_check_minutes=next_check_minutes,
        latest_decisions=latest_decisions,
        latest_report=latest_report,
        summary=summary,
    )
