"""자기주식 취득·처분 공시 동기화 서비스 — DART event → `stock_buyback_events`."""

from dataclasses import dataclass
from datetime import date
import logging

from src.common.data_adapter import DataSource
from src.constants import AssetType
from src.database.models import StockBuybackEvent
from src.database.stock_buyback_event_repository import StockBuybackEventRepository
from src.database.ticker_repository import TickerRepository
from src.providers.dart_company_client import DartCompanyClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BuybackSyncResult:
    """sync 결과 통계."""

    tickers: int            # 대상 KR_STOCK 수
    received: int           # 응답 row 수 (취득+처분 합산)
    upserted: int           # 실제 DB에 쓴 row 수 (= received, 파싱 OK)
    skipped_failure: int    # 네트워크 오류 등으로 호출 실패한 종목 수


class BuybackSyncService:
    """DART 자기주식 취득·처분 공시를 `stock_buyback_events` 테이블에 동기화.

    절차:
    1) `tickers` 중 PYKRX & KR_STOCK 만 추출
    2) 각 종목별로 `자기주식취득`, `자기주식처분` 두 키워드 호출 → 통합 이벤트 리스트
    3) StockBuybackEvent 엔티티 빌드
    4) bulk_upsert (Postgres ON CONFLICT, 1 트랜잭션)
    """

    def __init__(
            self,
            client: DartCompanyClient,
            ticker_repository: TickerRepository,
            buyback_event_repository: StockBuybackEventRepository,
    ) -> None:
        self._client = client
        self._ticker_repo = ticker_repository
        self._buyback_repo = buyback_event_repository

    def sync(self, from_date: date, to_date: date) -> BuybackSyncResult:
        """KR_STOCK 전종목에 대해 기간 내 자기주식 취득·처분 공시 동기화."""
        tickers = self._ticker_repo.find_by_data_source(DataSource.PYKRX)
        kr_tickers = [t for t in tickers if t.asset_type == AssetType.KR_STOCK]

        entities: list[StockBuybackEvent] = []
        skipped_failure = 0

        for ticker in kr_tickers:
            try:
                events = self._client.fetch_buyback_events(ticker.ticker, from_date, to_date)
            except Exception as e:
                logger.warning(
                    "자사주 공시 조회 실패 ticker=%s from=%s to=%s: %s",
                    ticker.ticker, from_date, to_date, e,
                )
                skipped_failure += 1
                continue

            for ev in events:
                entities.append(StockBuybackEvent(
                    ticker_id=ticker.id,
                    rcept_no=ev.rcept_no,
                    event_type=ev.event_type,
                    resolution_date=ev.resolution_date,
                    planned_shares=ev.planned_shares,
                    planned_amount=ev.planned_amount,
                    period_start=ev.period_start,
                    period_end=ev.period_end,
                    purpose=ev.purpose,
                ))

        self._buyback_repo.bulk_upsert(entities)
        logger.info(
            "자사주 공시 동기화 완료 from=%s to=%s tickers=%d received=%d upserted=%d skipped_failure=%d",
            from_date, to_date, len(kr_tickers), len(entities), len(entities), skipped_failure,
        )
        return BuybackSyncResult(
            tickers=len(kr_tickers),
            received=len(entities),
            upserted=len(entities),
            skipped_failure=skipped_failure,
        )
