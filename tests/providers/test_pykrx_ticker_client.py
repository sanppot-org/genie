"""PykrxTickerClient 단위 테스트."""

from datetime import date
from unittest.mock import patch

from src.constants import AssetType
from src.providers.pykrx_ticker_client import PykrxTickerClient, PykrxTickerInfo


class TestPykrxTickerClient:
    """pykrx 호출 래퍼 단위 테스트 (pykrx.stock 함수 mock)."""

    def test_fetch_stock_tickers_returns_kospi_and_kosdaq_merged(self) -> None:
        """KOSPI/KOSDAQ 종목을 합쳐서 KR_STOCK으로 반환한다."""
        def fake_ticker_list(_: str, market: str) -> list[str]:
            return {"KOSPI": ["005930", "000660"], "KOSDAQ": ["035720"]}[market]

        def fake_ticker_name(code: str) -> str:
            return {"005930": "삼성전자", "000660": "SK하이닉스", "035720": "카카오"}[code]

        with (
            patch("src.providers.pykrx_ticker_client.stock.get_market_ticker_list", side_effect=fake_ticker_list),
            patch("src.providers.pykrx_ticker_client.stock.get_market_ticker_name", side_effect=fake_ticker_name),
        ):
            result = PykrxTickerClient().fetch_stock_tickers(base_date=date(2026, 5, 15))

        assert result == [
            PykrxTickerInfo(ticker="005930", name="삼성전자", asset_type=AssetType.KR_STOCK),
            PykrxTickerInfo(ticker="000660", name="SK하이닉스", asset_type=AssetType.KR_STOCK),
            PykrxTickerInfo(ticker="035720", name="카카오", asset_type=AssetType.KR_STOCK),
        ]

    def test_fetch_etf_tickers_returns_kr_etf(self) -> None:
        """ETF 종목을 KR_ETF로 반환한다."""
        with (
            patch("src.providers.pykrx_ticker_client.stock.get_etf_ticker_list", return_value=["069500", "232080"]),
            patch(
                "src.providers.pykrx_ticker_client.stock.get_etf_ticker_name",
                side_effect=lambda code: {"069500": "KODEX 200", "232080": "TIGER 코스닥150"}[code],
            ),
        ):
            result = PykrxTickerClient().fetch_etf_tickers(base_date=date(2026, 5, 15))

        assert result == [
            PykrxTickerInfo(ticker="069500", name="KODEX 200", asset_type=AssetType.KR_ETF),
            PykrxTickerInfo(ticker="232080", name="TIGER 코스닥150", asset_type=AssetType.KR_ETF),
        ]

    def test_fetch_all_concatenates_stocks_and_etfs(self) -> None:
        """fetch_all은 주식 다음 ETF 순서로 합쳐서 반환한다."""
        with (
            patch("src.providers.pykrx_ticker_client.stock.get_market_ticker_list", return_value=["005930"]),
            patch("src.providers.pykrx_ticker_client.stock.get_market_ticker_name", return_value="삼성전자"),
            patch("src.providers.pykrx_ticker_client.stock.get_etf_ticker_list", return_value=["069500"]),
            patch("src.providers.pykrx_ticker_client.stock.get_etf_ticker_name", return_value="KODEX 200"),
        ):
            result = PykrxTickerClient().fetch_all(base_date=date(2026, 5, 15))

        # KOSPI/KOSDAQ 두 시장 호출 → 같은 종목이 두 번. ETF 한 번.
        assert len(result) == 3
        assert result[0].asset_type == AssetType.KR_STOCK
        assert result[-1] == PykrxTickerInfo(ticker="069500", name="KODEX 200", asset_type=AssetType.KR_ETF)

    def test_to_entity_maps_stock_info(self) -> None:
        """KR_STOCK PykrxTickerInfo가 Ticker 엔티티로 매핑된다."""
        info = PykrxTickerInfo(ticker="005930", name="삼성전자", asset_type=AssetType.KR_STOCK)

        entity = info.to_entity()

        assert entity.ticker == "005930"
        assert entity.name == "삼성전자"
        assert entity.asset_type == AssetType.KR_STOCK
        assert entity.data_source == "pykrx"

    def test_to_entity_maps_etf_info(self) -> None:
        """KR_ETF PykrxTickerInfo도 동일하게 매핑되며 asset_type만 달라진다."""
        info = PykrxTickerInfo(ticker="069500", name="KODEX 200", asset_type=AssetType.KR_ETF)

        entity = info.to_entity()

        assert entity.ticker == "069500"
        assert entity.name == "KODEX 200"
        assert entity.asset_type == AssetType.KR_ETF
        assert entity.data_source == "pykrx"

    def test_base_date_none_uses_today_kst(self) -> None:
        """base_date 미지정 시 KST 오늘 날짜를 YYYYMMDD로 pykrx에 전달한다."""
        from datetime import datetime
        from zoneinfo import ZoneInfo

        expected_yyyymmdd = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y%m%d")

        with (
            patch("src.providers.pykrx_ticker_client.stock.get_market_ticker_list", return_value=[]) as mock_list,
            patch("src.providers.pykrx_ticker_client.stock.get_market_ticker_name"),
        ):
            PykrxTickerClient().fetch_stock_tickers()

        # 두 번 호출됨 (KOSPI, KOSDAQ). 첫 인자가 오늘 날짜인지 확인.
        for call_args in mock_list.call_args_list:
            assert call_args.args[0] == expected_yyyymmdd
