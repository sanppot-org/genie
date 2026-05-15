"""pykrx를 통한 한국 주식/ETF 종목 목록 조회 래퍼."""

from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from pykrx import stock

from src.common.data_adapter import DataSource
from src.config import DEFAULT_ENV_FILE_PATH
from src.constants import AssetType
from src.database.models import Ticker

# pykrx는 종목 목록 조회 시 KRX 인증이 필요하고, KRX_ID/KRX_PW를 OS 환경 변수에서
# 직접 읽는다. Pydantic Settings는 .env를 읽어도 os.environ으로 export하지 않으므로,
# 본 모듈을 로드하는 시점에 .env 값을 OS env로 push한다 (이미 설정된 값은 보존).
load_dotenv(DEFAULT_ENV_FILE_PATH)

_KST = ZoneInfo("Asia/Seoul")
_STOCK_MARKETS: tuple[str, ...] = ("KOSPI", "KOSDAQ")


@dataclass(frozen=True)
class PykrxTickerInfo:
    """pykrx에서 가져온 종목 메타데이터."""

    ticker: str
    name: str
    asset_type: AssetType

    def to_entity(self) -> Ticker:
        """SQLAlchemy Ticker 엔티티로 변환. data_source는 PYKRX 고정.

        `active`는 명시적으로 설정하지 않는다 — 모델 기본값(True)에 맡긴다.
        sync 로직(후속)이 기존 엔티티의 active를 보존할지 판단한다.
        """
        return Ticker(
            ticker=self.ticker,
            name=self.name,
            asset_type=self.asset_type,
            data_source=DataSource.PYKRX.value,
        )


class PykrxTickerClient:
    """pykrx를 통한 한국 주식/ETF 종목 목록 조회 래퍼.

    - 주식: KOSPI + KOSDAQ 통합 (KONEX 제외)
    - ETF: 전체
    - DB 저장/동기화 로직은 호출자(서비스 계층) 책임
    """

    @staticmethod
    def fetch_stock_tickers(base_date: date | None = None) -> list[PykrxTickerInfo]:
        """KOSPI + KOSDAQ 종목 정보 조회."""
        yyyymmdd = _to_yyyymmdd(base_date)
        results: list[PykrxTickerInfo] = []
        for market in _STOCK_MARKETS:
            tickers: list[str] = stock.get_market_ticker_list(yyyymmdd, market=market)
            for ticker in tickers:
                results.append(
                    PykrxTickerInfo(
                        ticker=ticker,
                        name=stock.get_market_ticker_name(ticker),
                        asset_type=AssetType.KR_STOCK,
                    )
                )
        return results

    @staticmethod
    def fetch_etf_tickers(base_date: date | None = None) -> list[PykrxTickerInfo]:
        """ETF 종목 정보 조회."""
        yyyymmdd = _to_yyyymmdd(base_date)
        tickers: list[str] = stock.get_etf_ticker_list(yyyymmdd)
        return [
            PykrxTickerInfo(
                ticker=ticker,
                name=stock.get_etf_ticker_name(ticker),
                asset_type=AssetType.KR_ETF,
            )
            for ticker in tickers
        ]

    def fetch_all(self, base_date: date | None = None) -> list[PykrxTickerInfo]:
        """주식 + ETF 통합 결과."""
        return self.fetch_stock_tickers(base_date) + self.fetch_etf_tickers(base_date)


def _to_yyyymmdd(base_date: date | None) -> str:
    """pykrx 호출용 날짜 포맷. None이면 KST 기준 오늘.

    주의: pykrx는 휴장일(주말/공휴일)을 호출하면 빈 리스트를 반환한다.
    호출자(스케줄러/동기화 서비스)가 영업일 보정 책임을 진다.
    필요 시 `pykrx.stock.get_nearest_business_day_in_a_week()`로 최근 영업일을 구해 인자로 전달.
    """
    target = base_date if base_date is not None else datetime.now(_KST).date()
    return target.strftime("%Y%m%d")
