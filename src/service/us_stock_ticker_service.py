"""미국 주식/ETF 종목 등록 서비스 (FDR StockListing 기반 이름·거래소 자동 해석).

워치리스트 심볼을 받아 FDR `StockListing('NASDAQ'/'NYSE'/'AMEX')`에서 이름과
거래소를 해석하고 `tickers`에 등록(US_STOCK / FDR / exchange). 주식목록에 없는
심볼은 `StockListing('ETF/US')`로 보강해 US_ETF(exchange=None)로 등록한다.
양쪽에 모두 있으면 주식 목록을 우선한다. 어디에도 없으면 skip.
캔들 수집(`UsStockDailyCandleService`)의 **선행 단계**다.

FDR 거래소명 → KIS EXCD 매핑: NASDAQ→NAS, NYSE→NYS, AMEX→AMS.
StockListing 4종은 호출 비용이 있어 인스턴스 캐시에 1회만 로드한다.
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


@dataclass(frozen=True)
class ListingMeta:
    """FDR 상장목록에서 해석한 종목 메타."""

    name: str
    exchange: str | None
    asset_type: AssetType


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
        self._listing_map: dict[str, ListingMeta] | None = None  # symbol -> ListingMeta

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
                existing = repo.find_by_ticker(symbol)
                if existing is not None:
                    if existing.data_source != DataSource.FDR.value or existing.asset_type != meta.asset_type:
                        logger.info(
                            "미국 종목 re-home symbol=%s data_source=%s->%s asset_type=%s->%s",
                            symbol, existing.data_source, DataSource.FDR.value, existing.asset_type, meta.asset_type,
                        )
                    existing.name = meta.name
                    existing.exchange = meta.exchange
                    existing.active = True
                    existing.asset_type = meta.asset_type
                    existing.data_source = DataSource.FDR.value
                    result.updated += 1
                else:
                    repo.save(Ticker(
                        ticker=symbol.upper(),
                        name=meta.name,
                        asset_type=meta.asset_type,
                        data_source=DataSource.FDR.value,
                        exchange=meta.exchange,
                    ))
                    result.registered += 1
        logger.info(
            "미국 종목 등록 완료 registered=%d updated=%d skipped_unknown=%d",
            result.registered, result.updated, result.skipped_unknown,
        )
        return result

    def _load_listing_map(self) -> dict[str, ListingMeta]:
        """주식(NASDAQ/NYSE/AMEX)+ETF/US 상장목록을 1회 로드해 symbol→ListingMeta 맵 구성(캐시).

        주식 목록을 먼저 채우고, ETF/US는 주식 목록에 없는(miss) 심볼만 US_ETF로 보강한다
        (주식 목록 우선). ETF/US 로드는 독립 try/except로 격리해 실패해도 주식 등록은 죽지 않게 한다.
        """
        if self._listing_map is not None:
            return self._listing_map
        mapping: dict[str, ListingMeta] = {}
        for market, excd in _MARKET_TO_EXCD.items():
            df = fdr.StockListing(market)
            for symbol, name in zip(df["Symbol"], df["Name"], strict=False):
                mapping[str(symbol).upper()] = ListingMeta(str(name), excd, AssetType.US_STOCK)
        try:
            etf_df = fdr.StockListing("ETF/US")
            if {"Symbol", "Name"} <= set(etf_df.columns):
                for symbol, name in zip(etf_df["Symbol"], etf_df["Name"], strict=False):
                    key = str(symbol).upper()
                    if key not in mapping:  # 주식 목록 우선, ETF는 miss일 때만 보강
                        mapping[key] = ListingMeta(str(name), None, AssetType.US_ETF)
            else:
                logger.warning(
                    "ETF/US 목록 컬럼 누락으로 ETF 보강 skip expected={'Symbol','Name'} actual=%s",
                    list(etf_df.columns),
                )
        except Exception:
            logger.exception("ETF/US StockListing 로드 실패 — ETF 보강 skip (주식 등록은 계속)")
        self._listing_map = mapping
        return mapping
