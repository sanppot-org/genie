import logging

from src.collector.data_fetcher import fetch_finance_data_reader, fetch_yfinance
from src.common.google_sheet.cell_update import CellUpdate
from src.common.google_sheet.client import GoogleSheetClient
from src.hantu import HantuDomesticAPI

logger = logging.getLogger(__name__)

# 금 현물 종목 코드 (한국투자증권)
GOLD_TICKER_CODE = "M04020000"

# 구글 시트 금 가격 저장 위치 (행, 열)
USD_KRW_PRICE_ROW = 3
DOMESTIC_GOLD_PRICE_ROW = 4
INTERNATIONAL_GOLD_PRICE_ROW = 5


class GoogleSheetDataCollector:
    def __init__(self, hantu_api: HantuDomesticAPI, google_sheet_client: GoogleSheetClient) -> None:
        self.hantu_api = hantu_api
        self.google_sheet_client = google_sheet_client

    def collect_price(self) -> None:
        """금/환율 시세를 구글 시트에 갱신. 소스별 best-effort 부분 업데이트.

        외부 소스(yfinance/KIS/FDR)가 장애·점검으로 실패해도 크래시하지 않고, 성공한 소스만
        갱신한다. 실패는 한 줄 warning으로 남기고 해당 셀은 스킵(옛 값·옛 시각 유지).
        """
        updates: list[CellUpdate] = []

        # 블록 A: 환율(yfinance). 성공 시 국제 금(FDR × 환율)을 파생 — 국제 금은 환율에 의존.
        try:
            usd_krw = float(fetch_yfinance('KRW=X')['Close'].iloc[-1])
            updates += [CellUpdate.data(row=USD_KRW_PRICE_ROW, value=usd_krw), CellUpdate.now(row=USD_KRW_PRICE_ROW)]
            try:
                international_gold_price = float(fetch_finance_data_reader('GC=F')['Close'].iloc[-1] / 31.1 * usd_krw)
                updates += [CellUpdate.data(row=INTERNATIONAL_GOLD_PRICE_ROW, value=international_gold_price), CellUpdate.now(row=INTERNATIONAL_GOLD_PRICE_ROW)]
            except Exception as e:  # noqa: BLE001 — best-effort 시트 갱신, 다른 소스는 계속돼야 함
                logger.warning("국제 금 시세 수집 실패, 건너뜀: %s", e)
        except Exception as e:  # noqa: BLE001 — best-effort 시트 갱신, 다른 소스는 계속돼야 함
            logger.warning("환율(USD/KRW) 수집 실패, 국제 금까지 건너뜀: %s", e)

        # 블록 B: 국내 금(KIS) — 독립. 점검 시 HantuConnectionError/HTTP 오류 등.
        try:
            domestic_gold_price = float(self.hantu_api.get_stock_price(GOLD_TICKER_CODE).output.stck_prpr)
            updates += [CellUpdate.data(row=DOMESTIC_GOLD_PRICE_ROW, value=domestic_gold_price), CellUpdate.now(row=DOMESTIC_GOLD_PRICE_ROW)]
        except Exception as e:  # noqa: BLE001 — best-effort 시트 갱신, 다른 소스는 계속돼야 함
            logger.warning("국내 금 시세(KIS) 수집 실패, 건너뜀: %s", e)

        if updates:
            self.google_sheet_client.batch_update(updates)
