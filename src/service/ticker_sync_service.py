"""pykrx 종목 동기화 서비스."""

from dataclasses import dataclass
import logging

from src.common.data_adapter import DataSource
from src.constants import AssetType
from src.database.models import Ticker
from src.database.ticker_repository import TickerRepository
from src.providers.kis_company_client import KisCompanyClient
from src.providers.pykrx_ticker_client import PykrxTickerClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SyncResult:
    """sync_pykrx 결과 통계.

    한 row가 여러 분기에 해당할 수 있다 (예: 이름 변경 + 재상장 동시 발생 시
    renamed와 reactivated 모두 +1).
    """

    inserted: int
    deactivated: int
    renamed: int
    reactivated: int
    unchanged: int


class TickerSyncService:
    """pykrx에서 받은 종목 목록과 DB를 동기화한다.

    set 기반 diff로 4가지 분기를 한 번에 처리:
    - 신규 (pykrx O, DB X) → INSERT
    - 사라짐 (pykrx X, DB O, active=True) → UPDATE active=False
    - 이름 변경 (둘 다 O, name 다름) → UPDATE name
    - 재상장 (둘 다 O, DB.active=False) → UPDATE active=True

    KIS `search_stock_info`에서 KSIC + 지수업종 3단(대/중/소) 8개 필드를 보강한다
    (best-effort):
    - 신규 INSERT 시
    - 기존 row 중 `sector_large_code`가 NULL인 경우 ("둘 다 존재" 분기에서 백필)
    """

    def __init__(
        self,
        client: PykrxTickerClient,
        repository: TickerRepository,
        kis_client: KisCompanyClient,
    ) -> None:
        self._client = client
        self._repo = repository
        self._kis_client = kis_client

    def sync_pykrx(self) -> SyncResult:
        """pykrx 종목 정보로 DB를 동기화. 모든 변경을 한 트랜잭션에서 commit.

        pykrx 응답이 비어있으면 client가 재시도 후 `EmptyPykrxResponseError`를 raise하므로
        여기서는 별도 가드를 두지 않는다 (호출자가 예외를 처리).
        """
        pykrx_map = {info.ticker: info for info in self._client.fetch_all()}
        db_map = {t.ticker: t for t in self._repo.find_by_data_source(DataSource.PYKRX)}

        inserted = deactivated = renamed = reactivated = unchanged = 0

        for code in set(pykrx_map) | set(db_map):
            info = pykrx_map.get(code)
            existing = db_map.get(code)

            if info is not None and existing is None:
                entity = info.to_entity()
                self._enrich_with_kis(entity)
                self._repo.session.add(entity)
                inserted += 1
                continue

            if info is None and existing is not None:
                if existing.active:
                    existing.active = False
                    deactivated += 1
                else:
                    unchanged += 1
                continue

            # 둘 다 존재
            assert info is not None and existing is not None
            changed = False
            if existing.name != info.name:
                existing.name = info.name
                renamed += 1
                changed = True
            if not existing.active:
                existing.active = True
                reactivated += 1
                changed = True
            if existing.sector_large_code is None:
                # 기존 row 백필 — sector NULL인 경우에만 KIS 호출 (구 DART industry_code만 있는 row 포함)
                self._enrich_with_kis(existing)
            if not changed:
                unchanged += 1

        self._repo.session.flush()
        return SyncResult(
            inserted=inserted,
            deactivated=deactivated,
            renamed=renamed,
            reactivated=reactivated,
            unchanged=unchanged,
        )

    def _enrich_with_kis(self, entity: Ticker) -> None:
        """ticker에 KIS 업종/섹터 8개 필드를 채운다.

        ETF는 KIS 응답에서 업종/섹터가 비어 와 의미가 없으므로 호출 자체를 skip한다.
        best-effort — 예외/None 응답은 warning만 남기고 sync 진행을 막지 않는다.
        """
        if entity.asset_type != AssetType.KR_STOCK:
            return
        try:
            info = self._kis_client.fetch_industry_info(entity.ticker)
        except Exception as e:
            logger.warning("KIS 메타데이터 조회 실패 (ticker=%s): %s", entity.ticker, e)
            return
        if info is None:
            return
        entity.industry_code = info.industry_code
        entity.industry_name = info.industry_name
        entity.sector_large_code = info.sector_large_code
        entity.sector_large_name = info.sector_large_name
        entity.sector_mid_code = info.sector_mid_code
        entity.sector_mid_name = info.sector_mid_name
        entity.sector_small_code = info.sector_small_code
        entity.sector_small_name = info.sector_small_name
