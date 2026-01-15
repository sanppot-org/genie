"""업비트 API 함수 테스트"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.upbit.model.balance import BalanceInfo
from src.upbit.model.error import UpbitAPIError
from src.upbit.model.order import OrderResult, OrderSide, OrderType
from src.upbit.upbit_api import UpbitAPI, UpbitCandleInterval


class TestGetCandles:
    """get_candles 메서드 테스트"""

    @patch("src.upbit.upbit_api.make_api_request")
    def test_get_candles_정상_조회_200개_이하(self, mock_request):
        """200개 이하 캔들 조회 시 단일 API 호출로 정상 동작한다"""
        # Given
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "market": "KRW-BTC",
                "candle_date_time_utc": "2024-10-27T03:00:00",
                "candle_date_time_kst": "2024-10-27T12:00:00",
                "opening_price": 95000000.0,
                "high_price": 96000000.0,
                "low_price": 94000000.0,
                "trade_price": 95500000.0,
                "candle_acc_trade_volume": 15.75,
                "candle_acc_trade_price": 1503750000.0,
            },
            {
                "market": "KRW-BTC",
                "candle_date_time_utc": "2024-10-27T02:00:00",
                "candle_date_time_kst": "2024-10-27T11:00:00",
                "opening_price": 95500000.0,
                "high_price": 97000000.0,
                "low_price": 95000000.0,
                "trade_price": 96500000.0,
                "candle_acc_trade_volume": 20.5,
                "candle_acc_trade_price": 1978250000.0,
            },
        ]
        mock_request.return_value = mock_response

        config = MagicMock()
        config.base_url = "https://api.upbit.com"
        api = UpbitAPI(config)

        # When
        result = api.get_candles(market="KRW-BTC", interval=UpbitCandleInterval.DAY, count=2)

        # Then
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        assert list(result.columns) == ["open", "high", "low", "close", "volume", "value", "timestamp"]
        assert mock_request.call_count == 1

    @patch("src.upbit.upbit_api.make_api_request")
    @patch("src.upbit.upbit_api.time.sleep")
    def test_get_candles_대용량_조회_200개_초과(self, mock_sleep, mock_request):
        """200개 초과 캔들 조회 시 반복 호출로 정상 동작한다"""
        # Given
        from datetime import datetime, timedelta

        # 첫 번째 호출 응답 (200개)
        first_response = MagicMock()
        base_date = datetime(2024, 10, 27)
        first_batch = [
            {
                "market": "KRW-BTC",
                "candle_date_time_utc": (base_date - timedelta(days=i)).strftime("%Y-%m-%dT%H:%M:%S"),
                "candle_date_time_kst": (base_date - timedelta(days=i) + timedelta(hours=9)).strftime(
                    "%Y-%m-%dT%H:%M:%S"),
                "opening_price": 95000000.0 + i * 10000,
                "high_price": 96000000.0 + i * 10000,
                "low_price": 94000000.0 + i * 10000,
                "trade_price": 95500000.0 + i * 10000,
                "candle_acc_trade_volume": 15.75,
                "candle_acc_trade_price": 1503750000.0,
            }
            for i in range(200)
        ]
        first_response.json.return_value = first_batch

        # 두 번째 호출 응답 (100개)
        second_response = MagicMock()
        second_batch = [
            {
                "market": "KRW-BTC",
                "candle_date_time_utc": (base_date - timedelta(days=i + 200)).strftime("%Y-%m-%dT%H:%M:%S"),
                "candle_date_time_kst": (base_date - timedelta(days=i + 200) + timedelta(hours=9)).strftime(
                    "%Y-%m-%dT%H:%M:%S"),
                "opening_price": 95000000.0 + (i + 200) * 10000,
                "high_price": 96000000.0 + (i + 200) * 10000,
                "low_price": 94000000.0 + (i + 200) * 10000,
                "trade_price": 95500000.0 + (i + 200) * 10000,
                "candle_acc_trade_volume": 15.75,
                "candle_acc_trade_price": 1503750000.0,
            }
            for i in range(100)
        ]
        second_response.json.return_value = second_batch

        mock_request.side_effect = [first_response, second_response]

        config = MagicMock()
        config.base_url = "https://api.upbit.com"
        api = UpbitAPI(config)

        # When
        result = api.get_candles(market="KRW-BTC", interval=UpbitCandleInterval.DAY, count=300)

        # Then
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 300
        assert mock_request.call_count == 2
        assert mock_sleep.call_count == 1  # Rate limit 대기  # Rate limit 대기

    def test_get_candles_market_빈_값_검증(self):
        """market이 빈 값이면 ValueError를 발생시킨다"""
        # Given
        config = MagicMock()
        api = UpbitAPI(config)

        # When & Then
        with pytest.raises(ValueError, match="market은 비어있을 수 없습니다"):
            api.get_candles(market="", interval=UpbitCandleInterval.DAY, count=10)

        with pytest.raises(ValueError, match="market은 비어있을 수 없습니다"):
            api.get_candles(market="   ", interval=UpbitCandleInterval.DAY, count=10)

    def test_get_candles_count_0_이하_검증(self):
        """count가 0 이하면 ValueError를 발생시킨다"""
        # Given
        config = MagicMock()
        api = UpbitAPI(config)

        # When & Then
        with pytest.raises(ValueError, match="count는 1 이상이어야 합니다"):
            api.get_candles(market="KRW-BTC", interval=UpbitCandleInterval.DAY, count=0)

        with pytest.raises(ValueError, match="count는 1 이상이어야 합니다"):
            api.get_candles(market="KRW-BTC", interval=UpbitCandleInterval.DAY, count=-1)

    @patch("src.upbit.upbit_api.make_api_request")
    def test_get_candles_to_파라미터_전달(self, mock_request):
        """to 파라미터가 올바르게 API에 전달된다"""
        # Given
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "market": "KRW-BTC",
                "candle_date_time_utc": "2024-10-27T00:00:00",
                "candle_date_time_kst": "2024-10-27T09:00:00",
                "opening_price": 95000000.0,
                "high_price": 96000000.0,
                "low_price": 94000000.0,
                "trade_price": 95500000.0,
                "candle_acc_trade_volume": 15.75,
                "candle_acc_trade_price": 1503750000.0,
            }
        ]
        mock_request.return_value = mock_response

        config = MagicMock()
        config.base_url = "https://api.upbit.com"
        api = UpbitAPI(config)

        from datetime import datetime

        to_datetime = datetime(2024, 10, 27, 12, 0, 0)

        # When
        api.get_candles(market="KRW-BTC", interval=UpbitCandleInterval.DAY, count=1, to=to_datetime)

        # Then
        call_args = mock_request.call_args
        assert call_args[1]["params"]["to"] == "2024-10-27T12:00:00"

    @patch("src.upbit.upbit_api.make_api_request")
    def test_get_candles_API_에러_처리(self, mock_request):
        """API 호출 실패 시 빈 DataFrame을 반환한다"""
        # Given
        mock_request.side_effect = Exception("API Error")

        config = MagicMock()
        config.base_url = "https://api.upbit.com"
        api = UpbitAPI(config)

        # When
        result = api.get_candles(market="KRW-BTC", interval=UpbitCandleInterval.DAY, count=10)

        # Then
        assert isinstance(result, pd.DataFrame)
        assert result.empty

    @patch("src.upbit.upbit_api.make_api_request")
    def test_get_candles_빈_응답_처리(self, mock_request):
        """API 응답이 빈 리스트면 빈 DataFrame을 반환한다"""
        # Given
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_request.return_value = mock_response

        config = MagicMock()
        config.base_url = "https://api.upbit.com"
        api = UpbitAPI(config)

        # When
        result = api.get_candles(market="KRW-BTC", interval=UpbitCandleInterval.DAY, count=10)

        # Then
        assert isinstance(result, pd.DataFrame)
        assert result.empty


class TestGetCurrentPrice:
    """get_current_price 함수 테스트"""

    @patch("src.upbit.upbit_api.pyupbit.get_current_price")
    def test_get_current_price_정상_반환(self, mock_pyupbit):
        """pyupbit가 정상 가격을 반환하면 그대로 반환한다"""
        mock_pyupbit.return_value = 95000000.0

        result = UpbitAPI.get_current_price()

        assert result == 95000000.0
        assert isinstance(result, float)

    @patch("src.upbit.upbit_api.pyupbit.get_current_price")
    def test_get_current_price_실패시_0_반환(self, mock_pyupbit):
        """pyupbit가 None을 반환하면 0을 반환한다"""
        mock_pyupbit.return_value = None

        result = UpbitAPI.get_current_price()

        assert result == 0.0
        assert isinstance(result, float)


class TestUpbitAPIGetBalance:
    """UpbitAPI.get_balance 메서드 테스트"""

    @patch("src.upbit.upbit_api.pyupbit.Upbit")
    def test_get_balance_정상_반환(self, mock_upbit_class):
        """upbit.get_balance가 정상 잔고를 반환하면 그대로 반환한다"""
        # Mock 설정
        mock_upbit_instance = MagicMock()
        mock_upbit_instance.get_balance.return_value = 1000000.0
        mock_upbit_class.return_value = mock_upbit_instance

        # Config mock
        with patch("src.upbit.upbit_api.UpbitConfig") as mock_config_class:
            mock_config = MagicMock()
            mock_config.upbit_access_key = "test_access"
            mock_config.upbit_secret_key = "test_secret"

            api = UpbitAPI(mock_config)
            result = api.get_available_amount()

            assert result == 1000000.0
            assert isinstance(result, float)
            mock_upbit_instance.get_balance.assert_called_once_with("KRW")

    @patch("src.upbit.upbit_api.pyupbit.Upbit")
    def test_get_balance_실패시_0_반환(self, mock_upbit_class):
        """upbit.get_balance가 None을 반환하면 0.0을 반환한다"""
        # Mock 설정
        mock_upbit_instance = MagicMock()
        mock_upbit_instance.get_balance.return_value = None
        mock_upbit_class.return_value = mock_upbit_instance

        # Config mock
        with patch("src.upbit.upbit_api.UpbitConfig") as mock_config_class:
            mock_config = MagicMock()
            mock_config.upbit_access_key = "test_access"
            mock_config.upbit_secret_key = "test_secret"

            api = UpbitAPI(mock_config)
            result = api.get_available_amount()

            assert result == 0.0
            assert isinstance(result, float)

    @patch("src.upbit.upbit_api.pyupbit.Upbit")
    def test_get_balance_ticker_파라미터_전달(self, mock_upbit_class):
        """ticker 파라미터가 올바르게 전달된다"""
        mock_upbit_instance = MagicMock()
        mock_upbit_instance.get_balance.return_value = 1.5
        mock_upbit_class.return_value = mock_upbit_instance

        with patch("src.upbit.upbit_api.UpbitConfig") as mock_config_class:
            mock_config = MagicMock()
            mock_config.upbit_access_key = "test_access"
            mock_config.upbit_secret_key = "test_secret"

            api = UpbitAPI(mock_config)
            result = api.get_available_amount(ticker="BTC")

            assert result == 1.5
            mock_upbit_instance.get_balance.assert_called_once_with("BTC")

    @patch("src.upbit.upbit_api.pyupbit.Upbit")
    def test_get_balance_ticker_형식_전달(self, mock_upbit_class):
        """ticker 형식('KRW-BTC')이 올바르게 전달된다"""
        mock_upbit_instance = MagicMock()
        mock_upbit_instance.get_balance.return_value = 0.5
        mock_upbit_class.return_value = mock_upbit_instance

        with patch("src.upbit.upbit_api.UpbitConfig") as mock_config_class:
            mock_config = MagicMock()
            mock_config.upbit_access_key = "test_access"
            mock_config.upbit_secret_key = "test_secret"

            api = UpbitAPI(mock_config)
            result = api.get_available_amount(ticker="KRW-BTC")

            assert result == 0.5
            mock_upbit_instance.get_balance.assert_called_once_with("KRW-BTC")


class TestUpbitAPIGetBalances:
    """UpbitAPI.get_balances 메서드 테스트"""

    @patch("src.upbit.upbit_api.pyupbit.Upbit")
    def test_get_balances_정상_반환(self, mock_upbit_class):
        """정상 응답 시 BalanceInfo 리스트를 반환한다"""
        # Mock 설정
        mock_upbit_instance = MagicMock()
        mock_upbit_instance.get_balances.return_value = [
            {
                "currency": "KRW",
                "balance": "1000000.0",
                "locked": "0.0",
                "avg_buy_price": "0",
                "avg_buy_price_modified": False,
                "unit_currency": "KRW",
            },
            {
                "currency": "BTC",
                "balance": "0.5",
                "locked": "0.0",
                "avg_buy_price": "50000000",
                "avg_buy_price_modified": True,
                "unit_currency": "KRW",
            },
        ]
        mock_upbit_class.return_value = mock_upbit_instance

        with patch("src.upbit.upbit_api.UpbitConfig") as mock_config_class:
            mock_config = MagicMock()
            mock_config.upbit_access_key = "test_access"
            mock_config.upbit_secret_key = "test_secret"

            api = UpbitAPI(mock_config)
            result = api.get_balances()

            assert isinstance(result, list)
            assert len(result) == 2
            assert all(isinstance(b, BalanceInfo) for b in result)
            assert result[0].currency == "KRW"
            assert result[1].currency == "BTC"

    @patch("src.upbit.upbit_api.pyupbit.Upbit")
    def test_get_balances_에러_응답시_예외_발생(self, mock_upbit_class):
        """에러 응답 시 UpbitAPIError 예외를 발생시킨다"""
        # Mock 설정 - 에러 응답
        mock_upbit_instance = MagicMock()
        mock_upbit_instance.get_balances.return_value = {
            "error": {"message": "This is not a verified IP.", "name": "no_authorization_ip"}}
        mock_upbit_class.return_value = mock_upbit_instance

        with patch("src.upbit.upbit_api.UpbitConfig") as mock_config_class:
            mock_config = MagicMock()
            mock_config.upbit_access_key = "test_access"
            mock_config.upbit_secret_key = "test_secret"

            api = UpbitAPI(mock_config)

            with pytest.raises(UpbitAPIError) as exc_info:
                api.get_balances()

            assert exc_info.value.message == "This is not a verified IP."
            assert exc_info.value.name == "no_authorization_ip"

    @patch("src.upbit.upbit_api.pyupbit.Upbit")
    def test_get_balances_None_응답시_예외_발생(self, mock_upbit_class):
        """None 응답 시 UpbitAPIError 예외를 발생시킨다"""
        mock_upbit_instance = MagicMock()
        mock_upbit_instance.get_balances.return_value = None
        mock_upbit_class.return_value = mock_upbit_instance

        with patch("src.upbit.upbit_api.UpbitConfig") as mock_config_class:
            mock_config = MagicMock()
            mock_config.upbit_access_key = "test_access"
            mock_config.upbit_secret_key = "test_secret"

            api = UpbitAPI(mock_config)

            with pytest.raises(UpbitAPIError) as exc_info:
                api.get_balances()

            assert exc_info.value.message == "API 응답이 비어있습니다"
            assert exc_info.value.name == "empty_response"

    @patch("src.upbit.upbit_api.pyupbit.Upbit")
    def test_get_balances_빈_리스트_응답시_빈_리스트_반환(self, mock_upbit_class):
        """빈 리스트 응답 시 빈 리스트를 반환한다"""
        mock_upbit_instance = MagicMock()
        mock_upbit_instance.get_balances.return_value = []
        mock_upbit_class.return_value = mock_upbit_instance

        with patch("src.upbit.upbit_api.UpbitConfig") as mock_config_class:
            mock_config = MagicMock()
            mock_config.upbit_access_key = "test_access"
            mock_config.upbit_secret_key = "test_secret"

            api = UpbitAPI(mock_config)

            result = api.get_balances()
            assert result == []


class TestUpbitAPIBuyMarketOrder:
    """UpbitAPI.buy_market_order 메서드 테스트"""

    @patch("src.upbit.upbit_api.pyupbit.Upbit")
    def test_buy_market_order_amount가_0일때_예외_발생(self, mock_upbit_class):
        """amount가 0일 때 ValueError 예외를 발생시킨다"""
        mock_upbit_instance = MagicMock()
        mock_upbit_class.return_value = mock_upbit_instance

        with patch("src.upbit.upbit_api.UpbitConfig") as mock_config_class:
            mock_config = MagicMock()
            mock_config.upbit_access_key = "test_access"
            mock_config.upbit_secret_key = "test_secret"

            api = UpbitAPI(mock_config)

            with pytest.raises(ValueError) as exc_info:
                api.buy_market_order(ticker="KRW-BTC", amount=0.0)

            assert "amount는 0보다 커야 합니다" in str(exc_info.value)
            mock_upbit_instance.buy_market_order.assert_not_called()

    @patch("src.upbit.upbit_api.pyupbit.Upbit")
    def test_buy_market_order_amount가_음수일때_예외_발생(self, mock_upbit_class):
        """amount가 음수일 때 ValueError 예외를 발생시킨다"""
        mock_upbit_instance = MagicMock()
        mock_upbit_class.return_value = mock_upbit_instance

        with patch("src.upbit.upbit_api.UpbitConfig") as mock_config_class:
            mock_config = MagicMock()
            mock_config.upbit_access_key = "test_access"
            mock_config.upbit_secret_key = "test_secret"

            api = UpbitAPI(mock_config)

            with pytest.raises(ValueError) as exc_info:
                api.buy_market_order(ticker="KRW-BTC", amount=-1000.0)

            assert "amount는 0보다 커야 합니다" in str(exc_info.value)
            mock_upbit_instance.buy_market_order.assert_not_called()

    @patch("src.upbit.upbit_api.pyupbit.Upbit")
    def test_buy_market_order_에러_응답시_예외_발생(self, mock_upbit_class):
        """에러 응답 시 UpbitAPIError 예외를 발생시킨다"""
        mock_upbit_instance = MagicMock()
        mock_upbit_instance.buy_market_order.return_value = {
            "error": {"message": "Insufficient funds.", "name": "insufficient_funds"}}
        mock_upbit_class.return_value = mock_upbit_instance

        with patch("src.upbit.upbit_api.UpbitConfig") as mock_config_class:
            mock_config = MagicMock()
            mock_config.upbit_access_key = "test_access"
            mock_config.upbit_secret_key = "test_secret"

            api = UpbitAPI(mock_config)

            with pytest.raises(UpbitAPIError) as exc_info:
                api.buy_market_order(ticker="KRW-BTC", amount=50000.0)

            assert exc_info.value.message == "Insufficient funds."
            assert exc_info.value.name == "insufficient_funds"

    @patch("src.upbit.upbit_api.pyupbit.Upbit")
    def test_buy_market_order_정상_반환(self, mock_upbit_class):
        """정상 응답 시 OrderResult 객체를 반환한다"""
        mock_upbit_instance = MagicMock()
        mock_upbit_instance.buy_market_order.return_value = {
            "uuid": "test-uuid-123",
            "side": "bid",
            "ord_type": "price",
            "price": "50000",
            "state": "wait",
            "market": "KRW-BTC",
            "created_at": "2024-01-01T00:00:00+09:00",
            "volume": "0.001",
            "remaining_volume": "0.001",
            "reserved_fee": "25",
            "remaining_fee": "25",
            "paid_fee": "0",
            "locked": "50025",
            "executed_volume": "0",
            "trades_count": 0,
        }
        mock_upbit_class.return_value = mock_upbit_instance

        with patch("src.upbit.upbit_api.UpbitConfig") as mock_config_class:
            mock_config = MagicMock()
            mock_config.upbit_access_key = "test_access"
            mock_config.upbit_secret_key = "test_secret"

            api = UpbitAPI(mock_config)

            result = api.buy_market_order(ticker="KRW-BTC", amount=50000.0)

            assert isinstance(result, OrderResult)
            assert result.uuid == "test-uuid-123"
            assert result.side == OrderSide.BID
            assert result.ord_type == OrderType.PRICE


class TestUpbitAPISellMarketOrder:
    """UpbitAPI.sell_market_order 메서드 테스트"""

    @patch("src.upbit.upbit_api.pyupbit.Upbit")
    def test_sell_market_order_volume이_0일때_예외_발생(self, mock_upbit_class):
        """volume이 0일 때 ValueError 예외를 발생시킨다"""
        mock_upbit_instance = MagicMock()
        mock_upbit_class.return_value = mock_upbit_instance

        with patch("src.upbit.upbit_api.UpbitConfig") as mock_config_class:
            mock_config = MagicMock()
            mock_config.upbit_access_key = "test_access"
            mock_config.upbit_secret_key = "test_secret"

            api = UpbitAPI(mock_config)

            with pytest.raises(ValueError) as exc_info:
                api.sell_market_order(ticker="KRW-BTC", volume=0.0)

            assert "volume은 0보다 커야 합니다" in str(exc_info.value)
            mock_upbit_instance.sell_market_order.assert_not_called()

    @patch("src.upbit.upbit_api.pyupbit.Upbit")
    def test_sell_market_order_volume이_음수일때_예외_발생(self, mock_upbit_class):
        """volume이 음수일 때 ValueError 예외를 발생시킨다"""
        mock_upbit_instance = MagicMock()
        mock_upbit_class.return_value = mock_upbit_instance

        with patch("src.upbit.upbit_api.UpbitConfig") as mock_config_class:
            mock_config = MagicMock()
            mock_config.upbit_access_key = "test_access"
            mock_config.upbit_secret_key = "test_secret"

            api = UpbitAPI(mock_config)

            with pytest.raises(ValueError) as exc_info:
                api.sell_market_order(ticker="KRW-BTC", volume=-0.001)

            assert "volume은 0보다 커야 합니다" in str(exc_info.value)
            mock_upbit_instance.sell_market_order.assert_not_called()

    @patch("src.upbit.upbit_api.pyupbit.Upbit")
    def test_sell_market_order_에러_응답시_예외_발생(self, mock_upbit_class):
        """에러 응답 시 UpbitAPIError 예외를 발생시킨다"""
        mock_upbit_instance = MagicMock()
        mock_upbit_instance.sell_market_order.return_value = {
            "error": {"message": "Insufficient volume.", "name": "insufficient_volume"}}
        mock_upbit_class.return_value = mock_upbit_instance

        with patch("src.upbit.upbit_api.UpbitConfig") as mock_config_class:
            mock_config = MagicMock()
            mock_config.upbit_access_key = "test_access"
            mock_config.upbit_secret_key = "test_secret"

            api = UpbitAPI(mock_config)

            with pytest.raises(UpbitAPIError) as exc_info:
                api.sell_market_order(ticker="KRW-BTC", volume=0.001)

            assert exc_info.value.message == "Insufficient volume."
            assert exc_info.value.name == "insufficient_volume"

    @patch("src.upbit.upbit_api.pyupbit.Upbit")
    def test_sell_market_order_정상_반환(self, mock_upbit_class):
        """정상 응답 시 OrderResult 객체를 반환한다"""
        mock_upbit_instance = MagicMock()
        mock_upbit_instance.sell_market_order.return_value = {
            "uuid": "test-uuid-456",
            "side": "ask",
            "ord_type": "market",
            "price": "0",
            "state": "wait",
            "market": "KRW-BTC",
            "created_at": "2024-01-01T00:00:00+09:00",
            "volume": "0.001",
            "remaining_volume": "0.001",
            "reserved_fee": "0",
            "remaining_fee": "0",
            "paid_fee": "0",
            "locked": "0.001",
            "executed_volume": "0",
            "trades_count": 0,
        }
        mock_upbit_class.return_value = mock_upbit_instance

        with patch("src.upbit.upbit_api.UpbitConfig") as mock_config_class:
            mock_config = MagicMock()
            mock_config.upbit_access_key = "test_access"
            mock_config.upbit_secret_key = "test_secret"

            api = UpbitAPI(mock_config)

            result = api.sell_market_order(ticker="KRW-BTC", volume=0.001)

            assert isinstance(result, OrderResult)
            assert result.uuid == "test-uuid-456"
            assert result.side == OrderSide.ASK
            assert result.ord_type == OrderType.MARKET


class TestUpbitAPISellMarketOrderByPrice:
    """UpbitAPI.sell_market_order_by_price 메서드 테스트"""

    @patch("src.upbit.upbit_api.pyupbit.Upbit")
    def test_sell_market_order_by_price_price가_0일때_예외_발생(self, mock_upbit_class):
        """price가 0일 때 ValueError 예외를 발생시킨다"""
        mock_upbit_instance = MagicMock()
        mock_upbit_class.return_value = mock_upbit_instance

        with patch("src.upbit.upbit_api.UpbitConfig") as mock_config_class:
            mock_config = MagicMock()
            mock_config.upbit_access_key = "test_access"
            mock_config.upbit_secret_key = "test_secret"

            api = UpbitAPI(mock_config)

            with pytest.raises(ValueError) as exc_info:
                api.sell_market_order_by_price(ticker="KRW-BTC", price=0.0)

            assert "price는 0보다 커야 합니다" in str(exc_info.value)

    @patch("src.upbit.upbit_api.pyupbit.Upbit")
    def test_sell_market_order_by_price_price가_음수일때_예외_발생(self, mock_upbit_class):
        """price가 음수일 때 ValueError 예외를 발생시킨다"""
        mock_upbit_instance = MagicMock()
        mock_upbit_class.return_value = mock_upbit_instance

        with patch("src.upbit.upbit_api.UpbitConfig") as mock_config_class:
            mock_config = MagicMock()
            mock_config.upbit_access_key = "test_access"
            mock_config.upbit_secret_key = "test_secret"

            api = UpbitAPI(mock_config)

            with pytest.raises(ValueError) as exc_info:
                api.sell_market_order_by_price(ticker="KRW-BTC", price=-50000.0)

            assert "price는 0보다 커야 합니다" in str(exc_info.value)

    @patch("src.upbit.upbit_api.pyupbit.Upbit")
    @patch("src.upbit.upbit_api.UpbitAPI.get_current_price")
    def test_sell_market_order_by_price_정상_반환(self, mock_get_current_price, mock_upbit_class):
        """현재가로 수량 계산 후 매도 주문을 정상적으로 수행한다"""
        # Mock 설정
        mock_get_current_price.return_value = 100000000.0  # 1억원

        mock_upbit_instance = MagicMock()
        mock_upbit_instance.sell_market_order.return_value = {
            "uuid": "test-uuid-789",
            "side": "ask",
            "ord_type": "market",
            "price": "0",
            "state": "wait",
            "market": "KRW-BTC",
            "created_at": "2024-01-01T00:00:00+09:00",
            "volume": "0.0005",
            "remaining_volume": "0.0005",
            "reserved_fee": "0",
            "remaining_fee": "0",
            "paid_fee": "0",
            "locked": "0.0005",
            "executed_volume": "0",
            "trades_count": 0,
        }
        mock_upbit_class.return_value = mock_upbit_instance

        with patch("src.upbit.upbit_api.UpbitConfig") as mock_config_class:
            mock_config = MagicMock()
            mock_config.upbit_access_key = "test_access"
            mock_config.upbit_secret_key = "test_secret"

            api = UpbitAPI(mock_config)
            result = api.sell_market_order_by_price(ticker="KRW-BTC", price=50000.0)

            # 검증
            assert isinstance(result, OrderResult)
            assert result.uuid == "test-uuid-789"
            assert result.side == OrderSide.ASK

            # get_current_price가 올바르게 호출되었는지 확인
            mock_get_current_price.assert_called_once_with("KRW-BTC")

            # 계산된 volume으로 sell_market_order가 호출되었는지 확인
            # volume = 50000.0 / 100000000.0 = 0.0005
            mock_upbit_instance.sell_market_order.assert_called_once_with("KRW-BTC", 0.0005)

    @patch("src.upbit.upbit_api.pyupbit.Upbit")
    @patch("src.upbit.upbit_api.UpbitAPI.get_current_price")
    def test_sell_market_order_by_price_현재가_0일때_예외_발생(self, mock_get_current_price, mock_upbit_class):
        """현재가가 0일 때 ValueError 예외를 발생시킨다"""
        # Mock 설정
        mock_get_current_price.return_value = 0.0

        mock_upbit_instance = MagicMock()
        mock_upbit_class.return_value = mock_upbit_instance

        with patch("src.upbit.upbit_api.UpbitConfig") as mock_config_class:
            mock_config = MagicMock()
            mock_config.upbit_access_key = "test_access"
            mock_config.upbit_secret_key = "test_secret"

            api = UpbitAPI(mock_config)

            with pytest.raises(ValueError) as exc_info:
                api.sell_market_order_by_price(ticker="KRW-BTC", price=50000.0)

            assert "현재가를 조회할 수 없습니다" in str(exc_info.value)

            # sell_market_order는 호출되지 않아야 함
            mock_upbit_instance.sell_market_order.assert_not_called()


class TestUpbitAPISellAll:
    """UpbitAPI.sell_all 메서드 테스트"""

    @patch("src.upbit.upbit_api.pyupbit.Upbit")
    def test_sell_all_보유_수량이_있을때_정상_매도(self, mock_upbit_class):
        """보유 수량이 있을 때 전량 매도하고 OrderResult를 반환한다"""
        # Mock 설정
        mock_upbit_instance = MagicMock()
        mock_upbit_instance.get_balance.return_value = 0.5  # BTC 0.5개 보유
        mock_upbit_instance.sell_market_order.return_value = {
            "uuid": "test-uuid-sell-all",
            "side": "ask",
            "ord_type": "market",
            "price": "0",
            "state": "wait",
            "market": "KRW-BTC",
            "created_at": "2024-01-01T00:00:00+09:00",
            "volume": "0.5",
            "remaining_volume": "0.5",
            "reserved_fee": "0",
            "remaining_fee": "0",
            "paid_fee": "0",
            "locked": "0.5",
            "executed_volume": "0",
            "trades_count": 0,
        }
        mock_upbit_class.return_value = mock_upbit_instance

        with patch("src.upbit.upbit_api.UpbitConfig") as mock_config_class:
            mock_config = MagicMock()
            mock_config.upbit_access_key = "test_access"
            mock_config.upbit_secret_key = "test_secret"

            api = UpbitAPI(mock_config)
            result = api.sell_all(ticker="KRW-BTC")

            # 검증
            assert isinstance(result, OrderResult)
            assert result.uuid == "test-uuid-sell-all"
            assert result.side == OrderSide.ASK

            # get_balance가 올바른 ticker로 호출되었는지 확인
            mock_upbit_instance.get_balance.assert_called_once_with("KRW-BTC")

            # sell_market_order가 올바른 volume으로 호출되었는지 확인
            mock_upbit_instance.sell_market_order.assert_called_once_with("KRW-BTC", 0.5)

    @patch("src.upbit.upbit_api.pyupbit.Upbit")
    def test_sell_all_보유_수량이_0일때_None_반환(self, mock_upbit_class):
        """보유 수량이 0일 때 None을 반환하고 에러를 발생시키지 않는다"""
        # Mock 설정
        mock_upbit_instance = MagicMock()
        mock_upbit_instance.get_balance.return_value = 0.0  # 보유 수량 없음
        mock_upbit_class.return_value = mock_upbit_instance

        with patch("src.upbit.upbit_api.UpbitConfig") as mock_config_class:
            mock_config = MagicMock()
            mock_config.upbit_access_key = "test_access"
            mock_config.upbit_secret_key = "test_secret"

            api = UpbitAPI(mock_config)
            result = api.sell_all(ticker="KRW-ETH")

            # 검증
            assert result is None

            # get_balance는 호출되어야 함
            mock_upbit_instance.get_balance.assert_called_once_with("KRW-ETH")

            # sell_market_order는 호출되지 않아야 함
            mock_upbit_instance.sell_market_order.assert_not_called()


class TestGetLastClosedCandleTime:
    """_get_last_closed_candle_time 헬퍼 함수 테스트"""

    @pytest.fixture
    def fixed_time(self):
        """테스트용 고정 시각: 2024-01-15 10:23:45.123456 UTC"""
        from datetime import UTC, datetime
        return datetime(2024, 1, 15, 10, 23, 45, 123456, tzinfo=UTC)

    def test_minute_1_현재분_시작시각_반환(self, fixed_time):
        """1분봉: 현재 분의 시작 시각을 반환한다 (초, 마이크로초 = 0)"""
        from datetime import UTC, datetime

        from src.upbit.upbit_api import UpbitCandleInterval, _get_last_closed_candle_time

        result = _get_last_closed_candle_time(UpbitCandleInterval.MINUTE_1, _now=fixed_time)

        expected = datetime(2024, 1, 15, 10, 23, 0, 0, tzinfo=UTC)
        assert result == expected

    def test_minute_3_3분_단위로_내림(self, fixed_time):
        """3분봉: 3분 단위로 내림한 시각을 반환한다"""
        from datetime import UTC, datetime

        from src.upbit.upbit_api import UpbitCandleInterval, _get_last_closed_candle_time

        result = _get_last_closed_candle_time(UpbitCandleInterval.MINUTE_3, _now=fixed_time)

        # 23분 -> 21분 (21 = 7 * 3)
        expected = datetime(2024, 1, 15, 10, 21, 0, 0, tzinfo=UTC)
        assert result == expected

    def test_minute_5_5분_단위로_내림(self, fixed_time):
        """5분봉: 5분 단위로 내림한 시각을 반환한다"""
        from datetime import UTC, datetime

        from src.upbit.upbit_api import UpbitCandleInterval, _get_last_closed_candle_time

        result = _get_last_closed_candle_time(UpbitCandleInterval.MINUTE_5, _now=fixed_time)

        # 23분 -> 20분 (20 = 4 * 5)
        expected = datetime(2024, 1, 15, 10, 20, 0, 0, tzinfo=UTC)
        assert result == expected

    def test_minute_15_15분_단위로_내림(self, fixed_time):
        """15분봉: 15분 단위로 내림한 시각을 반환한다"""
        from datetime import UTC, datetime

        from src.upbit.upbit_api import UpbitCandleInterval, _get_last_closed_candle_time

        result = _get_last_closed_candle_time(UpbitCandleInterval.MINUTE_15, _now=fixed_time)

        # 23분 -> 15분 (15 = 1 * 15)
        expected = datetime(2024, 1, 15, 10, 15, 0, 0, tzinfo=UTC)
        assert result == expected

    def test_minute_60_정시로_내림(self, fixed_time):
        """60분봉: 정시로 내림한 시각을 반환한다"""
        from datetime import UTC, datetime

        from src.upbit.upbit_api import UpbitCandleInterval, _get_last_closed_candle_time

        result = _get_last_closed_candle_time(UpbitCandleInterval.MINUTE_60, _now=fixed_time)

        expected = datetime(2024, 1, 15, 10, 0, 0, 0, tzinfo=UTC)
        assert result == expected

    def test_minute_240_4시간_단위로_내림(self, fixed_time):
        """240분봉: 4시간 단위로 내림한 시각을 반환한다"""
        from datetime import UTC, datetime

        from src.upbit.upbit_api import UpbitCandleInterval, _get_last_closed_candle_time

        result = _get_last_closed_candle_time(UpbitCandleInterval.MINUTE_240, _now=fixed_time)

        # 10시 -> 8시 (8 = 2 * 4)
        expected = datetime(2024, 1, 15, 8, 0, 0, 0, tzinfo=UTC)
        assert result == expected

    def test_day_kst_09시_이후_당일_09시_반환(self):
        """일봉: KST 09시 이후이면 당일 09:00 KST를 UTC로 변환하여 반환한다"""
        from datetime import UTC, datetime

        from src.upbit.upbit_api import UpbitCandleInterval, _get_last_closed_candle_time

        # KST 15:00 = UTC 06:00
        utc_time = datetime(2024, 1, 15, 6, 0, 0, tzinfo=UTC)

        result = _get_last_closed_candle_time(UpbitCandleInterval.DAY, _now=utc_time)

        # KST 09:00 = UTC 00:00
        expected = datetime(2024, 1, 15, 0, 0, 0, 0, tzinfo=UTC)
        assert result == expected

    def test_day_kst_09시_이전_전일_09시_반환(self):
        """일봉: KST 09시 이전이면 전일 09:00 KST를 UTC로 변환하여 반환한다"""
        from datetime import UTC, datetime

        from src.upbit.upbit_api import UpbitCandleInterval, _get_last_closed_candle_time

        # KST 08:00 = UTC 이전날 23:00
        utc_time = datetime(2024, 1, 14, 23, 0, 0, tzinfo=UTC)

        result = _get_last_closed_candle_time(UpbitCandleInterval.DAY, _now=utc_time)

        # 전일 KST 09:00 = UTC 00:00 (2024-01-14)
        expected = datetime(2024, 1, 14, 0, 0, 0, 0, tzinfo=UTC)
        assert result == expected
