"""미국 주식 종목 등록 서비스 (FDR StockListing 기반 이름·거래소 자동 해석).

워치리스트 심볼을 받아 FDR `StockListing('NASDAQ'/'NYSE'/'AMEX')`에서 이름과
거래소를 해석하고 `tickers`에 등록(US_STOCK / FDR / exchange). 목록에 없는 심볼은 skip.
캔들 수집(`UsStockDailyCandleService`)의 **선행 단계**다.

FDR 거래소명 → KIS EXCD 매핑: NASDAQ→NAS, NYSE→NYS, AMEX→AMS.
StockListing 3종은 호출 비용이 있어(총 ~15s) 인스턴스 캐시에 1회만 로드한다.
"""

from dataclasses import dataclass, field
import logging

import FinanceDataReader as fdr  # noqa: N813

from src.common.data_adapter import DataSource
from src.constants import AssetType
from src.database.database import Database
from src.database.models import Ticker
from src.database.ticker_repository import TickerRepository

logger = logging.getLogger(__name__)

# FDR StockListing 시장명 → KIS EXCD
_MARKET_TO_EXCD: dict[str, str] = {"NASDAQ": "NAS", "NYSE": "NYS", "AMEX": "AMS"}


@dataclass
class UsTickerRegisterResult:
    """종목 등록 결과."""

    registered: int = 0          # 신규 등록 수
    updated: int = 0             # 기존 갱신 수
    skipped_unknown: int = 0     # FDR 목록에서 못 찾은 수
    skipped: list[str] = field(default_factory=list)


class UsStockTickerService:
    """FDR StockListing으로 미국 종목을 enrich하여 tickers에 등록."""

    def __init__(self, database: Database) -> None:
        self._database = database
        self._listing_map: dict[str, tuple[str, str]] | None = None  # symbol -> (name, excd)

    def register(self, symbols: list[str]) -> UsTickerRegisterResult:
        """심볼 리스트를 등록(또는 갱신). FDR 목록에 없는 심볼은 skip."""
        listing = self._load_listing_map()
        result = UsTickerRegisterResult()
        with self._database.session_scope() as session:
            repo = TickerRepository(session)
            for symbol in symbols:
                meta = listing.get(symbol.upper())
                if meta is None:
                    result.skipped_unknown += 1
                    result.skipped.append(symbol)
                    logger.warning("FDR 목록에 없는 미국 종목 skip symbol=%s", symbol)
                    continue
                name, excd = meta
                existing = repo.find_by_ticker(symbol)
                if existing is not None:
                    existing.name = name
                    existing.exchange = excd
                    existing.active = True
                    existing.asset_type = AssetType.US_STOCK
                    existing.data_source = DataSource.FDR.value
                    result.updated += 1
                else:
                    repo.save(Ticker(
                        ticker=symbol.upper(),
                        name=name,
                        asset_type=AssetType.US_STOCK,
                        data_source=DataSource.FDR.value,
                        exchange=excd,
                    ))
                    result.registered += 1
        logger.info(
            "미국 종목 등록 완료 registered=%d updated=%d skipped_unknown=%d",
            result.registered, result.updated, result.skipped_unknown,
        )
        return result

    def _load_listing_map(self) -> dict[str, tuple[str, str]]:
        """NASDAQ/NYSE/AMEX 상장목록을 1회 로드해 symbol→(name, excd) 맵 구성(캐시)."""
        if self._listing_map is not None:
            return self._listing_map
        mapping: dict[str, tuple[str, str]] = {}
        for market, excd in _MARKET_TO_EXCD.items():
            df = fdr.StockListing(market)
            for symbol, name in zip(df["Symbol"], df["Name"], strict=False):
                mapping[str(symbol).upper()] = (str(name), excd)
        self._listing_map = mapping
        return mapping
