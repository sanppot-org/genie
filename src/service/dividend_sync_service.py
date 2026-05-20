"""배당 이력 동기화 서비스 — KIS `ksdinfo_dividend` → `stock_dividends`."""

from dataclasses import dataclass
from datetime import date, datetime
import logging

from src.common.data_adapter import DataSource
from src.constants import AssetType
from src.database.models import StockDividend
from src.database.stock_dividend_repository import StockDividendRepository
from src.database.ticker_repository import TickerRepository
from src.hantu.domestic_api import HantuDomesticAPI
from src.hantu.model.domestic.dividend import DividendKind, DividendOutput

logger = logging.getLogger(__name__)


# KIS 응답 `divi_kind` 한글 라벨 → DB 라벨.
# GB1=2(INTERIM)는 "중간"만 매칭하고 "분기"는 누락되므로 GB1=0(ALL)로 단일 호출 후
# 응답 라벨로 세분 분류한다.
_HANGUL_KIND_TO_LABEL: dict[str, str] = {
    "결산": "SETTLE",
    "중간": "INTERIM",
    "반기": "INTERIM",   # KIS 응답에 "중간"과 "반기"가 혼재 — 의미상 동일.
    "분기": "QUARTERLY",
}


@dataclass(frozen=True)
class DividendSyncResult:
    """sync 결과 통계."""

    received: int           # KIS 응답 row 수
    upserted: int           # 실제 DB에 쓴 row 수
    skipped_unmapped: int   # ticker가 KR_STOCK 마스터에 없음
    skipped_invalid: int    # record_date/dps 파싱 실패


class DividendSyncService:
    """KIS 배당 이력을 `stock_dividends` 테이블에 동기화.

    절차:
    1) KIS `ksdinfo_dividend`를 결산·중간 두 번 호출 → 응답에 kind 라벨 부여
    2) `tickers` 중 PYKRX & KR_STOCK만 `{ticker_code: ticker_id}` 매핑
    3) StockDividend 엔티티 빌드 (미매핑/파싱 실패는 skip + 카운트)
    4) bulk_upsert (Postgres ON CONFLICT, 1 트랜잭션)
    """

    def __init__(
            self,
            client: HantuDomesticAPI,
            ticker_repository: TickerRepository,
            dividend_repository: StockDividendRepository,
    ) -> None:
        self._client = client
        self._ticker_repo = ticker_repository
        self._dividend_repo = dividend_repository

    def sync(self, from_date: date, to_date: date) -> DividendSyncResult:
        rows = self._client.get_dividend_history(
            from_date=from_date, to_date=to_date, kind=DividendKind.ALL,
        )

        tickers = self._ticker_repo.find_by_data_source(DataSource.PYKRX)
        code_to_id: dict[str, int] = {
            t.ticker: t.id for t in tickers if t.asset_type == AssetType.KR_STOCK
        }

        entities: list[StockDividend] = []
        skipped_unmapped = 0
        skipped_invalid = 0
        for row in rows:
            ticker_id = code_to_id.get(row.sht_cd)
            if ticker_id is None:
                skipped_unmapped += 1
                continue
            entity = _build_entity(row, ticker_id)
            if entity is None:
                skipped_invalid += 1
                continue
            entities.append(entity)

        self._dividend_repo.bulk_upsert(entities)
        logger.info(
            "배당 동기화 완료 from=%s to=%s received=%d upserted=%d skipped_unmapped=%d skipped_invalid=%d",
            from_date, to_date, len(rows), len(entities), skipped_unmapped, skipped_invalid,
        )
        return DividendSyncResult(
            received=len(rows),
            upserted=len(entities),
            skipped_unmapped=skipped_unmapped,
            skipped_invalid=skipped_invalid,
        )


def _build_entity(row: DividendOutput, ticker_id: int) -> StockDividend | None:
    record_date = _parse_kis_date(row.record_date)
    dps = _parse_float(row.per_sto_divi_amt)
    # dps=0은 "무배당 결의" 이력 — 현금배당 이벤트가 아니므로 적재하지 않는다.
    if record_date is None or dps is None or dps <= 0:
        return None
    label = _HANGUL_KIND_TO_LABEL.get((row.divi_kind or "").strip())
    if label is None:
        return None
    return StockDividend(
        ticker_id=ticker_id,
        record_date=record_date,
        pay_date=_parse_kis_date(row.divi_pay_dt),
        dps=dps,
        kind=label,
        fiscal_year=_parse_fiscal_year(row.divi_aplc_yymm) or record_date.year,
    )


_KIS_DATE_FORMATS = ("%Y%m%d", "%Y/%m/%d", "%Y-%m-%d")


def _parse_kis_date(value: str | None) -> date | None:
    """KIS 응답 날짜 — `YYYYMMDD`, `YYYY/MM/DD`, `YYYY-MM-DD` 모두 허용.

    필드마다 포맷이 다르다: record_date는 `YYYYMMDD`, divi_pay_dt는 `YYYY/MM/DD`로 옴.
    """
    if not value or not value.strip():
        return None
    text = value.strip()
    for fmt in _KIS_DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    text = value.strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _parse_fiscal_year(value: str | None) -> int | None:
    if not value or len(value.strip()) < 4:
        return None
    try:
        return int(value.strip()[:4])
    except ValueError:
        return None
