"""OrderNotification 모델 테스트"""

import pytest
from pydantic import ValidationError

from src.common.slack.order_notification import OrderNotification


class TestOrderNotification:
    """OrderNotification 모델 테스트"""

    def test_should_create_with_all_fields(self):
        """모든 필드로 OrderNotification을 생성할 수 있어야 한다"""
        # Given
        order_type = "매수"
        ticker = "KRW-BTC"
        execution_volume = 0.0002
        execution_price = 50000000.0
        funds = 10000.0

        # When
        notification = OrderNotification(
            order_type=order_type,
            ticker=ticker,
            execution_volume=execution_volume,
            execution_price=execution_price,
            funds=funds,
        )

        # Then
        assert notification.order_type == order_type
        assert notification.ticker == ticker
        assert notification.execution_volume == execution_volume
        assert notification.execution_price == execution_price
        assert notification.funds == funds

    def test_should_create_buy_order_notification(self):
        """매수 주문 알림을 생성할 수 있어야 한다"""
        # Given & When
        notification = OrderNotification(
            order_type="매수",
            ticker="KRW-BTC",
            execution_volume=0.0002,
            execution_price=50000000.0,
            funds=10000.0,
        )

        # Then
        assert notification.order_type == "매수"
        assert notification.ticker == "KRW-BTC"

    def test_should_create_sell_order_notification(self):
        """매도 주문 알림을 생성할 수 있어야 한다"""
        # Given & When
        notification = OrderNotification(
            order_type="매도",
            ticker="KRW-ETH",
            execution_volume=0.05,
            execution_price=3000000.0,
            funds=150000.0,
        )

        # Then
        assert notification.order_type == "매도"
        assert notification.ticker == "KRW-ETH"

    def test_should_validate_required_fields(self):
        """필수 필드가 누락되면 ValidationError가 발생해야 한다"""
        # Given & When & Then
        with pytest.raises(ValidationError):
            OrderNotification(
                order_type="매수",
                ticker="KRW-BTC",
                execution_volume=0.0002,
                execution_price=50000000.0,
                # funds 필드 누락
            )

    def test_should_accept_different_number_formats(self):
        """다양한 숫자 형식을 허용해야 한다"""
        # Given & When
        notification = OrderNotification(
            order_type="매수",
            ticker="KRW-XRP",
            execution_volume=100.5,
            execution_price=1500.0,
            funds=150750.0,
        )

        # Then
        assert notification.execution_volume == 100.5
        assert notification.execution_price == 1500.0
        assert notification.funds == 150750.0

    def test_to_message_should_return_formatted_buy_message(self):
        """매수 알림 메시지를 올바른 포맷으로 반환해야 한다"""
        # Given
        notification = OrderNotification(
            order_type="매수",
            ticker="KRW-BTC",
            execution_volume=0.0002,
            execution_price=50000000.0,
            funds=10000.0,
        )

        # When
        message = notification.to_message()

        # Then
        assert "✅ 매수 완료: KRW-BTC" in message
        assert "수량: 0.00020000" in message
        assert "가격: 50,000,000.0000원" in message
        assert "금액: 10,000.0000원" in message

    def test_to_message_should_return_formatted_sell_message(self):
        """매도 알림 메시지를 올바른 포맷으로 반환해야 한다"""
        # Given
        notification = OrderNotification(
            order_type="매도",
            ticker="KRW-ETH",
            execution_volume=0.05,
            execution_price=3000000.0,
            funds=150000.0,
        )

        # When
        message = notification.to_message()

        # Then
        assert "✅ 매도 완료: KRW-ETH" in message
        assert "수량: 0.05000000" in message
        assert "가격: 3,000,000.0000원" in message
        assert "금액: 150,000.0000원" in message

    def test_to_message_should_format_numbers_correctly(self):
        """숫자를 올바른 포맷으로 변환해야 한다"""
        # Given
        notification = OrderNotification(
            order_type="매수",
            ticker="KRW-XRP",
            execution_volume=100.5,
            execution_price=1500.0,
            funds=150750.0,
        )

        # When
        message = notification.to_message()

        # Then
        expected_message = "✅ 매수 완료: KRW-XRP\n수량: 100.50000000\n가격: 1,500.0000원\n금액: 150,750.0000원"
        assert message == expected_message
