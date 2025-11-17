from src.collector.data_fetcher import fetch_finance_data_reader, fetch_yfinance
from src.common.google_sheet.cell_update import CellUpdate
from src.common.google_sheet.client import GoogleSheetClient
from src.hantu import HantuDomesticAPI

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
        usd_krw = float(fetch_yfinance('KRW=X')['Close'].iloc[-1])
        domestic_gold_price = float(self.hantu_api.get_stock_price(GOLD_TICKER_CODE).output.stck_prpr)
        international_gold_price = float(fetch_finance_data_reader('GC=F')['Close'].iloc[-1] / 31.1 * usd_krw)

        self.google_sheet_client.batch_update([
            CellUpdate.data(row=USD_KRW_PRICE_ROW, value=usd_krw),
            CellUpdate.data(row=DOMESTIC_GOLD_PRICE_ROW, value=domestic_gold_price),
            CellUpdate.data(row=INTERNATIONAL_GOLD_PRICE_ROW, value=international_gold_price),

            CellUpdate.now(row=USD_KRW_PRICE_ROW),
            CellUpdate.now(row=DOMESTIC_GOLD_PRICE_ROW),
            CellUpdate.now(row=INTERNATIONAL_GOLD_PRICE_ROW)
        ])
