"""조건에 참조된 소스만 전종목 bulk 로드 → 종목별 TickerMetrics."""

from datetime import date

from src.database.models import StockFundamental
from src.database.stock_financial_ratio_repository import StockFinancialRatioRepository
from src.database.stock_fundamental_repository import StockFundamentalRepository
from src.database.stock_income_statement_repository import StockIncomeStatementRepository
from src.service.rule_screener.conditions import Condition
from src.service.rule_screener.evaluator import TickerMetrics
from src.service.rule_screener.metrics import METRIC_REGISTRY, MetricSource
from src.service.screening_service import ScreeningService


def referenced_sources(conditions: list[Condition], sort_metric: str | None) -> set[MetricSource]:
    """조건 + 정렬 지표가 실제로 참조하는 MetricSource 집합."""
    keys = [c.metric for c in conditions]
    if sort_metric is not None:
        keys.append(sort_metric)
    return {METRIC_REGISTRY[k].source for k in keys if k in METRIC_REGISTRY}


class MetricDataLoader:
    """참조된 소스만 골라 전종목 1회 bulk 로드."""

    def __init__(
            self,
            fundamental_repository: StockFundamentalRepository,
            income_statement_repository: StockIncomeStatementRepository,
            financial_ratio_repository: StockFinancialRatioRepository,
            screening_service: ScreeningService,
    ) -> None:
        self._fundamentals = fundamental_repository
        self._income = income_statement_repository
        self._ratios = financial_ratio_repository
        self._screening = screening_service

    def load(
            self,
            ticker_ids: list[int],
            ticker_code_by_id: dict[int, str],
            sources: set[MetricSource],
            today: date | None,
    ) -> dict[int, TickerMetrics]:
        """ticker_id → TickerMetrics. 참조 안 된 소스는 빈 값으로 둔다."""
        fundamentals: dict[int, StockFundamental] = {}
        if MetricSource.FUNDAMENTAL in sources:
            latest = self._fundamentals.find_latest_date()
            if latest is not None:
                fundamentals = {f.ticker_id: f for f in self._fundamentals.find_by_date(latest)}

        income = (
            self._income.find_annual_series_by_tickers(ticker_ids)
            if MetricSource.INCOME_ANNUAL in sources else {}
        )
        ratios = (
            self._ratios.find_annual_series_by_tickers(ticker_ids)
            if MetricSource.RATIO_ANNUAL in sources else {}
        )

        score_by_code: dict[str, float] = {}
        if MetricSource.SCORE in sources:
            # 전종목 점수 → ticker코드별 total_score. limit 크게 줘 전체 rows 확보.
            # 주의(Phase 1 수용): score_kr_stocks가 내부에서 fundamentals를 다시 조회한다.
            # 따라서 FUNDAMENTAL + SCORE를 함께 참조하는 요청(기본 sort=total_score 포함)은
            # fundamentals를 두 번 읽는다. 2700종목 규모에선 허용 가능. Phase 2에서 단일화 검토.
            res = self._screening.score_kr_stocks(limit=10**9, offset=0, today=today)
            score_by_code = {r.ticker: float(r.total_score) for r in res.rows}

        out: dict[int, TickerMetrics] = {}
        for tid in ticker_ids:
            score = score_by_code.get(ticker_code_by_id.get(tid, ""))
            out[tid] = TickerMetrics(
                fundamental=fundamentals.get(tid),
                income_annual=income.get(tid, []),
                ratio_annual=ratios.get(tid, []),
                total_score=score,
            )
        return out
