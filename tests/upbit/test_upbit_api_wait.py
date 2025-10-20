"""업비트 API 주문 완료 대기 기능 테스트"""

from unittest.mock import MagicMock, patch

import pytest

from src.upbit.model.error import OrderTimeoutError
from src.upbit.model.order import OrderResult, OrderSide, OrderState
from src.upbit.upbit_api import UpbitAPI


class TestUpbitAPIWaitForOrderCompletion:
    """UpbitAPI.wait_for_order_completion 메서드 테스트"""

    @patch("src.upbit.upbit_api.pyupbit.Upbit")
    @patch("src.upbit.upbit_api.time.sleep")
    def test_wait_for_order_completion_즉시_완료(self, mock_sleep, mock_upbit_class):
        """주문이 즉시 완료(done) 상태일 때 바로 반환한다"""
        # Mock 설정
        mock_upbit_instance = MagicMock()
        mock_upbit_instance.get_order.return_value = {
            "uuid": "test-uuid-done",
            "side": "bid",
            "ord_type": "price",
            "price": "50000",
            "state": "done",
            "market": "KRW-BTC",
            "created_at": "2024-01-01T00:00:00+09:00",
            "volume": "0.001",
            "remaining_volume": "0",
            "reserved_fee": "25",
            "remaining_fee": "0",
            "paid_fee": "25",
            "locked": "0",
            "executed_volume": "0.001",
            "trades_count": 1,
        }
        mock_upbit_class.return_value = mock_upbit_instance

        with patch("src.upbit.upbit_api.UpbitConfig") as mock_config_class:
            mock_config = MagicMock()
            api = UpbitAPI(mock_config)

            result = api.wait_for_order_completion("test-uuid-done", timeout=30.0)

            # 검증
            assert isinstance(result, OrderResult)
            assert result.uuid == "test-uuid-done"
            assert result.state == OrderState.DONE
            mock_upbit_instance.get_order.assert_called_once_with("test-uuid-done")
            mock_sleep.assert_not_called()  # 즉시 완료되어 sleep 불필요

    @patch("src.upbit.upbit_api.pyupbit.Upbit")
    @patch("src.upbit.upbit_api.time.sleep")
    def test_wait_for_order_completion_여러번_폴링_후_완료(self, mock_sleep, mock_upbit_class):
        """주문이 대기 상태에서 완료 상태로 변경될 때까지 폴링한다"""
        # Mock 설정 - 첫 2번은 wait, 3번째는 done
        mock_upbit_instance = MagicMock()
        mock_upbit_instance.get_order.side_effect = [
            {
                "uuid": "test-uuid-wait",
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
            },
            {
                "uuid": "test-uuid-wait",
                "side": "bid",
                "ord_type": "price",
                "price": "50000",
                "state": "wait",
                "market": "KRW-BTC",
                "created_at": "2024-01-01T00:00:00+09:00",
                "volume": "0.001",
                "remaining_volume": "0.0005",
                "reserved_fee": "25",
                "remaining_fee": "12.5",
                "paid_fee": "12.5",
                "locked": "25012.5",
                "executed_volume": "0.0005",
                "trades_count": 1,
            },
            {
                "uuid": "test-uuid-wait",
                "side": "bid",
                "ord_type": "price",
                "price": "50000",
                "state": "done",
                "market": "KRW-BTC",
                "created_at": "2024-01-01T00:00:00+09:00",
                "volume": "0.001",
                "remaining_volume": "0",
                "reserved_fee": "25",
                "remaining_fee": "0",
                "paid_fee": "25",
                "locked": "0",
                "executed_volume": "0.001",
                "trades_count": 2,
            },
        ]
        mock_upbit_class.return_value = mock_upbit_instance

        with patch("src.upbit.upbit_api.UpbitConfig") as mock_config_class:
            mock_config = MagicMock()
            api = UpbitAPI(mock_config)

            result = api.wait_for_order_completion("test-uuid-wait", timeout=30.0, poll_interval=0.5)

            # 검증
            assert isinstance(result, OrderResult)
            assert result.uuid == "test-uuid-wait"
            assert result.state == OrderState.DONE
            assert mock_upbit_instance.get_order.call_count == 3
            assert mock_sleep.call_count == 2  # 2번 폴링 후 완료

    @patch("src.upbit.upbit_api.pyupbit.Upbit")
    @patch("src.upbit.upbit_api.time.sleep")
    @patch("src.upbit.upbit_api.time.time")
    def test_wait_for_order_completion_타임아웃시_예외_발생(self, mock_time, mock_sleep, mock_upbit_class):
        """타임아웃 시간이 초과되면 OrderTimeoutError 예외를 발생시킨다"""
        # Mock 설정 - 시간이 계속 증가하도록
        mock_time.side_effect = [0.0, 1.0, 2.0, 3.0, 31.0]  # 마지막 31초에 타임아웃

        mock_upbit_instance = MagicMock()
        mock_upbit_instance.get_order.return_value = {
            "uuid": "test-uuid-timeout",
            "side": "bid",
            "ord_type": "price",
            "price": "50000",
            "state": "wait",  # 계속 대기 상태
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
            api = UpbitAPI(mock_config)

            with pytest.raises(OrderTimeoutError) as exc_info:
                api.wait_for_order_completion("test-uuid-timeout", timeout=30.0)

            assert exc_info.value.uuid == "test-uuid-timeout"
            assert exc_info.value.timeout == 30.0
            assert "주문 완료 대기 시간 초과" in str(exc_info.value)


class TestUpbitAPIBuyMarketOrderAndWait:
    """UpbitAPI.buy_market_order_and_wait 메서드 테스트"""

    @patch("src.upbit.upbit_api.pyupbit.Upbit")
    @patch("src.upbit.upbit_api.time.sleep")
    def test_buy_market_order_and_wait_정상_동작(self, mock_sleep, mock_upbit_class):
        """매수 주문 후 체결 완료까지 대기하여 완료된 OrderResult를 반환한다"""
        # Mock 설정
        mock_upbit_instance = MagicMock()

        # buy_market_order 응답 (wait 상태)
        mock_upbit_instance.buy_market_order.return_value = {
            "uuid": "test-buy-uuid",
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

        # get_order 응답 (done 상태)
        mock_upbit_instance.get_order.return_value = {
            "uuid": "test-buy-uuid",
            "side": "bid",
            "ord_type": "price",
            "price": "50000",
            "state": "done",
            "market": "KRW-BTC",
            "created_at": "2024-01-01T00:00:00+09:00",
            "volume": "0.001",
            "remaining_volume": "0",
            "reserved_fee": "25",
            "remaining_fee": "0",
            "paid_fee": "25",
            "locked": "0",
            "executed_volume": "0.001",
            "trades_count": 1,
        }

        mock_upbit_class.return_value = mock_upbit_instance

        with patch("src.upbit.upbit_api.UpbitConfig") as mock_config_class:
            mock_config = MagicMock()
            api = UpbitAPI(mock_config)

            result = api.buy_market_order_and_wait("KRW-BTC", 50000.0, timeout=30.0)

            # 검증
            assert isinstance(result, OrderResult)
            assert result.uuid == "test-buy-uuid"
            assert result.state == OrderState.DONE
            assert result.side == OrderSide.BID
            mock_upbit_instance.buy_market_order.assert_called_once_with("KRW-BTC", 50000.0)
            mock_upbit_instance.get_order.assert_called_once_with("test-buy-uuid")


class TestUpbitAPISellMarketOrderAndWait:
    """UpbitAPI.sell_market_order_and_wait 메서드 테스트"""

    @patch("src.upbit.upbit_api.pyupbit.Upbit")
    @patch("src.upbit.upbit_api.time.sleep")
    def test_sell_market_order_and_wait_정상_동작(self, mock_sleep, mock_upbit_class):
        """매도 주문 후 체결 완료까지 대기하여 완료된 OrderResult를 반환한다"""
        # Mock 설정
        mock_upbit_instance = MagicMock()

        # sell_market_order 응답 (wait 상태)
        mock_upbit_instance.sell_market_order.return_value = {
            "uuid": "test-sell-uuid",
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

        # get_order 응답 (done 상태)
        mock_upbit_instance.get_order.return_value = {
            "uuid": "test-sell-uuid",
            "side": "ask",
            "ord_type": "market",
            "price": "0",
            "state": "done",
            "market": "KRW-BTC",
            "created_at": "2024-01-01T00:00:00+09:00",
            "volume": "0.001",
            "remaining_volume": "0",
            "reserved_fee": "0",
            "remaining_fee": "0",
            "paid_fee": "50",
            "locked": "0",
            "executed_volume": "0.001",
            "trades_count": 1,
        }

        mock_upbit_class.return_value = mock_upbit_instance

        with patch("src.upbit.upbit_api.UpbitConfig") as mock_config_class:
            mock_config = MagicMock()
            api = UpbitAPI(mock_config)

            result = api.sell_market_order_and_wait("KRW-BTC", 0.001, timeout=30.0)

            # 검증
            assert isinstance(result, OrderResult)
            assert result.uuid == "test-sell-uuid"
            assert result.state == OrderState.DONE
            assert result.side == OrderSide.ASK
            mock_upbit_instance.sell_market_order.assert_called_once_with("KRW-BTC", 0.001)
            mock_upbit_instance.get_order.assert_called_once_with("test-sell-uuid")
