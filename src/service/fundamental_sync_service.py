"""펀더멘털 일자별 동기화 서비스."""

from dataclasses import dataclass
from datetime import date
import logging

from src.common.data_adapter import DataSource
from src.constants import AssetType
from src.database.models import StockFundamental
from src.database.stock_fundamental_repository import StockFundamentalRepository
from src.database.ticker_repository import TickerRepository
from src.providers.pykrx_fundamental_client import PykrxFundamentalClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FundamentalSyncResult:
    """sync 결과 통계."""

    received: int          # pykrx 응답 row 수
    upserted: int          # 실제 DB에 쓴 row 수
    skipped_unmapped: int  # pykrx 코드가 KR_STOCK tickers에 없음 (ETF/ETN/미동기화 신규상장)


class FundamentalSyncService:
    """pykrx 일자별 펀더멘털을 `stock_fundamentals` 테이블에 동기화.

    절차:
    1) pykrx fetch (전 종목 1회 호출)
    2) `tickers` 중 PYKRX & KR_STOCK만 추려 `{ticker_code: ticker_id}` 매핑
    3) StockFundamental 엔티티 빌드 (미매핑은 skip + 카운트)
    4) bulk_upsert (Postgres ON CONFLICT, 1 트랜잭션)
    """

    def __init__(
            self,
            client: PykrxFundamentalClient,
            ticker_repository: TickerRepository,
            fundamental_repository: StockFundamentalRepository,
    ) -> None:
        self._client = client
        self._ticker_repo = ticker_repository
        self._fundamental_repo = fundamental_repository

    def sync(self, target_date: date) -> FundamentalSyncResult:
        snapshots = self._client.fetch_by_date(target_date)

        tickers = self._ticker_repo.find_by_data_source(DataSource.PYKRX)
        code_to_id: dict[str, int] = {
            t.ticker: t.id for t in tickers if t.asset_type == AssetType.KR_STOCK
        }

        entities: list[StockFundamental] = []
        skipped = 0
        for snap in snapshots:
            ticker_id = code_to_id.get(snap.ticker)
            if ticker_id is None:
                skipped += 1
                continue
            entities.append(StockFundamental(
                ticker_id=ticker_id,
                date=target_date,
                bps=snap.bps,
                per=snap.per,
                pbr=snap.pbr,
                eps=snap.eps,
                div=snap.div,
                dps=snap.dps,
            ))

        self._fundamental_repo.bulk_upsert(entities)
        logger.info(
            "펀더멘털 동기화 완료 date=%s received=%d upserted=%d skipped_unmapped=%d",
            target_date, len(snapshots), len(entities), skipped,
        )
        return FundamentalSyncResult(
            received=len(snapshots),
            upserted=len(entities),
            skipped_unmapped=skipped,
        )
