"""pykrx 종목 동기화 서비스."""

from dataclasses import dataclass
import logging

from src.common.data_adapter import DataSource
from src.database.models import Ticker
from src.database.ticker_repository import TickerRepository
from src.providers.dart_company_client import DartCompanyClient
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

    DART에서 `industry_code`를 보강한다 (best-effort):
    - 신규 INSERT 시
    - 기존 row 중 `industry_code`가 NULL인 경우 ("둘 다 존재" 분기에서 백필)
    """

    def __init__(
        self,
        client: PykrxTickerClient,
        repository: TickerRepository,
        dart_client: DartCompanyClient,
    ) -> None:
        self._client = client
        self._repo = repository
        self._dart_client = dart_client

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
                self._enrich_with_dart(entity)
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
            if existing.industry_code is None:
                # 기존 row 백필 — DART 호출은 NULL인 경우에만, 채워지면 이후 sync에선 호출 안 함
                self._enrich_with_dart(existing)
            if not changed:
                unchanged += 1

        self._repo.session.commit()
        return SyncResult(
            inserted=inserted,
            deactivated=deactivated,
            renamed=renamed,
            reactivated=reactivated,
            unchanged=unchanged,
        )

    def _enrich_with_dart(self, entity: Ticker) -> None:
        """신규 ticker에 DART 메타데이터(`industry_code`)를 채운다.
        best-effort — 예외/None 응답은 warning만 남기고 sync 진행을 막지 않는다.
        """
        try:
            dart_info = self._dart_client.fetch_company_info(entity.ticker)
        except Exception as e:
            logger.warning("DART 메타데이터 조회 실패 (ticker=%s): %s", entity.ticker, e)
            return
        if dart_info is None:
            return
        entity.industry_code = dart_info.industry_code
