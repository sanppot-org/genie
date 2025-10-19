"""SlackClient 클래스 테스트"""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from src.common.slack.client import SlackClient
from src.config import SlackConfig
from src.strategy.order.execution_result import ExecutionResult
from src.upbit.model.order import OrderResult, OrderSide, OrderState, OrderType, Trade


@pytest.fixture
def slack_config():
    """SlackConfig 모킹"""
    return Mock(spec=SlackConfig)


@pytest.fixture
def slack_client(slack_config):
    """SlackClient 인스턴스 생성"""
    return SlackClient(slack_config)


class TestSendOrderNotification:
    """SlackClient.send_order_notification() 메서드 테스트"""

    def test_send_order_notification_should_send_buy_message(self, slack_client, slack_config):
        """매수 알림 메시지를 올바른 포맷으로 전송해야 한다"""
        # Given
        order_result = OrderResult(
            uuid="test-uuid",
            side=OrderSide.BID,
            ord_type=OrderType.MARKET,
            price=None,
            state=OrderState.DONE,
            market="KRW-BTC",
            created_at=datetime.now(),
            volume=0.0002,
            remaining_volume=0.0,
            executed_volume=0.0002,
            reserved_fee=0.0,
            remaining_fee=0.0,
            paid_fee=5.0,
            locked=0.0,
            trades_count=1,
            trades=[
                Trade(
                    market="KRW-BTC",
                    uuid="trade-uuid",
                    price=50000000.0,
                    volume=0.0002,
                    funds=10000.0,
                    trend="up",
                    created_at=datetime.now(),
                    side=OrderSide.BID,
                )
            ],
        )
        result = ExecutionResult.buy(strategy_name="test", order_result=order_result)

        with patch.object(slack_client, "send_message") as mock_send:
            # When
            slack_client.send_order_notification(result)

            # Then
            mock_send.assert_called_once()
            call_args = mock_send.call_args[0][0]
            assert "✅ 매수 완료: KRW-BTC" in call_args
            assert "수량: 0.00020000" in call_args
            assert "가격: 50,000,000.0000원" in call_args
            assert "금액: 10,000.0000원" in call_args

    def test_send_order_notification_should_send_sell_message(self, slack_client, slack_config):
        """매도 알림 메시지를 올바른 포맷으로 전송해야 한다"""
        # Given
        order_result = OrderResult(
            uuid="test-uuid",
            side=OrderSide.ASK,
            ord_type=OrderType.MARKET,
            price=None,
            state=OrderState.DONE,
            market="KRW-ETH",
            created_at=datetime.now(),
            volume=0.05,
            remaining_volume=0.0,
            executed_volume=0.05,
            reserved_fee=0.0,
            remaining_fee=0.0,
            paid_fee=5.0,
            locked=0.0,
            trades_count=1,
            trades=[
                Trade(
                    market="KRW-ETH",
                    uuid="trade-uuid",
                    price=3000000.0,
                    volume=0.05,
                    funds=150000.0,
                    trend="down",
                    created_at=datetime.now(),
                    side=OrderSide.ASK,
                )
            ],
        )
        result = ExecutionResult.sell(strategy_name="test", order_result=order_result)

        with patch.object(slack_client, "send_message") as mock_send:
            # When
            slack_client.send_order_notification(result)

            # Then
            mock_send.assert_called_once()
            call_args = mock_send.call_args[0][0]
            assert "✅ 매도 완료: KRW-ETH" in call_args
            assert "수량: 0.05000000" in call_args
            assert "가격: 3,000,000.0000원" in call_args
            assert "금액: 150,000.0000원" in call_args

    def test_send_order_notification_should_format_message_correctly(self, slack_client, slack_config):
        """알림 메시지가 올바른 형식으로 포맷팅되어야 한다"""
        # Given
        order_result = OrderResult(
            uuid="test-uuid",
            side=OrderSide.BID,
            ord_type=OrderType.MARKET,
            price=None,
            state=OrderState.DONE,
            market="KRW-XRP",
            created_at=datetime.now(),
            volume=100.5,
            remaining_volume=0.0,
            executed_volume=100.5,
            reserved_fee=0.0,
            remaining_fee=0.0,
            paid_fee=5.0,
            locked=0.0,
            trades_count=1,
            trades=[
                Trade(
                    market="KRW-XRP",
                    uuid="trade-uuid",
                    price=1500.0,
                    volume=100.5,
                    funds=150750.0,
                    trend="up",
                    created_at=datetime.now(),
                    side=OrderSide.BID,
                )
            ],
        )
        result = ExecutionResult.buy(strategy_name="test", order_result=order_result)

        with patch.object(slack_client, "send_message") as mock_send:
            # When
            slack_client.send_order_notification(result)

            # Then
            expected_message = "✅ 매수 완료: KRW-XRP\n수량: 100.50000000\n가격: 1,500.0000원\n금액: 150,750.0000원"
            mock_send.assert_called_once_with(expected_message)


class TestSendMessage:
    """SlackClient.send_message() 메서드 테스트"""

    def test_send_message_should_succeed_on_first_try(self, slack_client, slack_config):
        """네트워크 에러 없이 첫 번째 시도에서 성공해야 한다"""
        # Given
        slack_config.url = "https://hooks.slack.com/test"
        message = "테스트 메시지"

        with patch("src.common.slack.client.requests.post") as mock_post:
            mock_post.return_value = Mock(status_code=200)

            # When
            slack_client.send_message(message)

            # Then
            assert mock_post.call_count == 1

    def test_send_message_should_retry_on_network_error(self, slack_client, slack_config):
        """네트워크 에러 발생 시 재시도해야 한다"""
        # Given
        import requests

        slack_config.url = "https://hooks.slack.com/test"
        message = "테스트 메시지"

        with patch("src.common.slack.client.requests.post") as mock_post:
            # 처음 2번은 ConnectionError, 3번째는 성공
            mock_post.side_effect = [
                requests.exceptions.ConnectionError("Connection failed"),
                requests.exceptions.ConnectionError("Connection failed"),
                Mock(status_code=200),
            ]

            # When
            slack_client.send_message(message)

            # Then
            assert mock_post.call_count == 3

    def test_send_message_should_raise_exception_after_max_retries(self, slack_client, slack_config):
        """최대 재시도 횟수를 초과하면 예외를 발생시켜야 한다"""
        # Given
        import requests
        from tenacity import RetryError

        slack_config.url = "https://hooks.slack.com/test"
        message = "테스트 메시지"

        with patch("src.common.slack.client.requests.post") as mock_post:
            # 계속 실패
            mock_post.side_effect = requests.exceptions.ConnectionError("Connection failed")

            # When & Then
            with pytest.raises(RetryError):
                slack_client.send_message(message)

            # 최대 3회 재시도
            assert mock_post.call_count == 3

    def test_send_message_should_retry_on_timeout(self, slack_client, slack_config):
        """타임아웃 발생 시 재시도해야 한다"""
        # Given
        import requests

        slack_config.url = "https://hooks.slack.com/test"
        message = "테스트 메시지"

        with patch("src.common.slack.client.requests.post") as mock_post:
            # 처음에는 Timeout, 두 번째는 성공
            mock_post.side_effect = [
                requests.exceptions.Timeout("Request timeout"),
                Mock(status_code=200),
            ]

            # When
            slack_client.send_message(message)

            # Then
            assert mock_post.call_count == 2
