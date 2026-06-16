"""규칙 기반 조건 필터 스크리너 오케스트레이션."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from src.constants import AssetType
from src.database.stock_financial_ratio_repository import StockFinancialRatioRepository
from src.database.stock_fundamental_repository import StockFundamentalRepository
from src.database.stock_income_statement_repository import StockIncomeStatementRepository
from src.database.ticker_repository import TickerRepository
from src.service.rule_screener.conditions import Condition
from src.service.rule_screener.evaluator import (
    MetricDisplay,
    TickerMetrics,
    evaluate_ticker,
    extract_metric,
)
from src.service.rule_screener.loader import MetricDataLoader, referenced_sources
from src.service.rule_screener.metrics import SCALAR_SORT_KEYS, validate_condition
from src.service.screening_service import ScreeningService

SortOrder = Literal["asc", "desc"]


@dataclass(frozen=True)
class RuleScreeningRow:
    ticker: str
    name: str
    total_score: int | None
    metrics: dict[str, MetricDisplay] = field(default_factory=dict)


@dataclass(frozen=True)
class RuleScreeningResult:
    total: int
    limit: int
    offset: int
    rows: list[RuleScreeningRow]


def _make_sort_key(descending: bool) -> Callable[[tuple[float | None, str, RuleScreeningRow]], tuple[int, float]]:
    def key(item: tuple[float | None, str, RuleScreeningRow]) -> tuple[int, float]:
        v = item[0]
        if v is None:
            return (1, 0.0)
        return (0, float(-v if descending else v))
    return key


class RuleScreeningService:
    """KR_STOCK을 동적 조건(AND) 리스트로 필터링."""

    def __init__(
            self,
            ticker_repository: TickerRepository,
            fundamental_repository: StockFundamentalRepository,
            income_statement_repository: StockIncomeStatementRepository,
            financial_ratio_repository: StockFinancialRatioRepository,
            screening_service: ScreeningService,
    ) -> None:
        self._tickers = ticker_repository
        self._loader = MetricDataLoader(
            fundamental_repository,
            income_statement_repository,
            financial_ratio_repository,
            screening_service,
        )

    def screen(
            self,
            conditions: list[Condition],
            sort_by: str = "total_score",
            order: SortOrder = "desc",
            limit: int = 50,
            offset: int = 0,
            today: date | None = None,
    ) -> RuleScreeningResult:
        """조건 검증 → 참조 소스 bulk 로드 → 종목별 AND 평가 → 정렬·페이지네이션.

        sort_by는 스칼라 지표(per/pbr/total_score 등) 또는 'ticker'/'name'만 허용(시계열 불가).
        데이터 부족·조건 불만족 종목은 결과에서 제외.
        """
        for c in conditions:
            validate_condition(c)

        sort_metric = self._resolve_sort_metric(sort_by)

        tickers = self._tickers.find_by_asset_type(AssetType.KR_STOCK)
        if not tickers:
            return RuleScreeningResult(total=0, limit=limit, offset=offset, rows=[])

        ticker_ids = [t.id for t in tickers]
        code_by_id = {t.id: t.ticker for t in tickers}
        sources = referenced_sources(conditions, sort_metric)
        metrics_by_id = self._loader.load(ticker_ids, code_by_id, sources, today)

        passed: list[tuple[float | None, str, RuleScreeningRow]] = []
        for t in tickers:
            tm = metrics_by_id[t.id]
            res = evaluate_ticker(tm, conditions)
            if not res.passed:
                continue
            score = tm.total_score
            row = RuleScreeningRow(
                ticker=t.ticker,
                name=t.name,
                total_score=int(score) if score is not None else None,
                metrics=res.metrics,
            )
            sort_val = self._sort_value(sort_by, sort_metric, tm, t.ticker, t.name)
            passed.append((sort_val, t.ticker, row))

        passed = self._sort(passed, sort_by, order)
        rows = [row for _, _, row in passed[offset:offset + limit]]
        return RuleScreeningResult(total=len(passed), limit=limit, offset=offset, rows=rows)

    def _resolve_sort_metric(self, sort_by: str) -> str | None:
        """sort_by가 지표면 그 키 반환, ticker/name이면 None. 그 외(시계열 등)는 ValueError."""
        if sort_by in ("ticker", "name"):
            return None
        if sort_by in SCALAR_SORT_KEYS:
            return sort_by
        raise ValueError(f"정렬 불가한 sort_by: {sort_by} (스칼라 지표/ticker/name만 허용)")

    def _sort_value(self, sort_by: str, sort_metric: str | None, tm: TickerMetrics,
                    ticker: str, name: str) -> float | None:
        if sort_metric is None:
            return None  # ticker/name 정렬은 _sort에서 문자열로 처리
        v = extract_metric(sort_metric, tm)
        assert not isinstance(v, list)  # _resolve_sort_metric이 스칼라 지표만 허용
        return v

    def _sort(self, items: list[tuple[float | None, str, RuleScreeningRow]],
              sort_by: str, order: SortOrder) -> list[tuple[float | None, str, RuleScreeningRow]]:
        descending = order == "desc"
        if sort_by in ("ticker", "name"):
            items.sort(key=lambda it: getattr(it[2], sort_by), reverse=descending)
            return items
        items.sort(key=lambda it: it[1])                      # secondary: ticker ASC (stable)
        items.sort(key=_make_sort_key(descending))            # primary: sort_value, NULL last
        return items
