from src.common.google_sheet.client import GoogleSheetClient
from src.hantu import HantuDomesticAPI

# 금 현물 종목 코드 (한국투자증권)
GOLD_TICKER_CODE = "M04020000"

# 구글 시트 금 가격 저장 위치 (행, 열)
GOLD_PRICE_ROW = 2
GOLD_PRICE_COL = 2


class PriceDataCollector:
    def __init__(self, hantu_api: HantuDomesticAPI, google_sheet_client: GoogleSheetClient) -> None:
        self.hantu_api = hantu_api
        self.google_sheet_client = google_sheet_client

    def collect_gold_price(self) -> None:
        chart_response = self.hantu_api.get_stock_price(GOLD_TICKER_CODE)
        gold_price = float(chart_response.output.stck_prpr)

        self.google_sheet_client.set(GOLD_PRICE_ROW, GOLD_PRICE_COL, gold_price)
