"""pykrx 종목 동기화 서비스."""

from dataclasses import dataclass

from src.common.data_adapter import DataSource
from src.database.ticker_repository import TickerRepository
from src.providers.pykrx_ticker_client import PykrxTickerClient


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
    """

    def __init__(self, client: PykrxTickerClient, repository: TickerRepository) -> None:
        self._client = client
        self._repo = repository

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
                self._repo.session.add(info.to_entity())
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
