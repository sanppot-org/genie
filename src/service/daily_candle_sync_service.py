"""KR 주식 일봉 일자별 동기화 서비스."""

from dataclasses import dataclass
from datetime import date
import logging

from src.common.data_adapter import DataSource
from src.constants import AssetType
from src.database.models import StockDailyCandle
from src.database.stock_daily_candle_repository import StockDailyCandleRepository
from src.database.ticker_repository import TickerRepository
from src.providers.pykrx_daily_candle_client import PykrxDailyCandleClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DailyCandleSyncResult:
    """sync 결과 통계."""

    received: int            # pykrx 응답 row 수
    upserted: int            # 실제 DB에 쓴 row 수
    skipped_unmapped: int    # pykrx 코드가 KR_STOCK tickers에 없음 (ETF/ETN/미동기화 신규상장)
    skipped_no_trade: int    # 거래 정지/관리종목 (volume=0 + open=0)


class DailyCandleSyncService:
    """pykrx 일자별 OHLCV를 `stock_daily_candles` 테이블에 동기화.

    절차:
    1) pykrx fetch (전 종목 1회 호출)
    2) `tickers` 중 PYKRX & KR_STOCK만 추려 `{ticker_code: ticker_id}` 매핑
    3) StockDailyCandle 엔티티 빌드 (미매핑/거래정지는 skip + 카운트)
    4) bulk_upsert (Postgres ON CONFLICT, 1 트랜잭션)
    """

    def __init__(
            self,
            client: PykrxDailyCandleClient,
            ticker_repository: TickerRepository,
            daily_candle_repository: StockDailyCandleRepository,
    ) -> None:
        self._client = client
        self._ticker_repo = ticker_repository
        self._candle_repo = daily_candle_repository

    def sync(self, target_date: date) -> DailyCandleSyncResult:
        snapshots = self._client.fetch_by_date(target_date)

        tickers = self._ticker_repo.find_by_data_source(DataSource.PYKRX)
        code_to_id: dict[str, int] = {
            t.ticker: t.id for t in tickers if t.asset_type == AssetType.KR_STOCK
        }

        entities: list[StockDailyCandle] = []
        skipped_unmapped = 0
        skipped_no_trade = 0
        for snap in snapshots:
            ticker_id = code_to_id.get(snap.ticker)
            if ticker_id is None:
                skipped_unmapped += 1
                continue
            if snap.volume == 0 and snap.open == 0:
                skipped_no_trade += 1
                continue
            entities.append(StockDailyCandle(
                ticker_id=ticker_id,
                date=target_date,
                open=snap.open,
                high=snap.high,
                low=snap.low,
                close=snap.close,
                volume=snap.volume,
                trade_value=snap.trade_value,
            ))

        self._candle_repo.bulk_upsert(entities)
        logger.info(
            "일봉 동기화 완료 date=%s received=%d upserted=%d skipped_unmapped=%d skipped_no_trade=%d",
            target_date, len(snapshots), len(entities), skipped_unmapped, skipped_no_trade,
        )
        return DailyCandleSyncResult(
            received=len(snapshots),
            upserted=len(entities),
            skipped_unmapped=skipped_unmapped,
            skipped_no_trade=skipped_no_trade,
        )
