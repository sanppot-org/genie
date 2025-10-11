"""업비트 OrderResult 모델 테스트"""
from datetime import datetime, timezone, timedelta

from src.upbit.model.order import OrderResult
from src.upbit.model.order import OrderState, OrderSide, OrderType


class TestOrderResult:
    """OrderResult 모델 테스트"""

    def test_OrderResult_from_dict_메서드(self):
        """from_dict 메서드로 OrderResult를 생성할 수 있다"""

        data = {
            "uuid": "test-uuid-9999",
            "side": "bid",
            "ord_type": "limit",
            "price": "60000000",
            "state": "cancel",
            "market": "KRW-BTC",
            "created_at": "2025-10-10T14:00:00+09:00",
            "volume": "0.01",
            "remaining_volume": "0.01",
            "reserved_fee": "300",
            "remaining_fee": "300",
            "paid_fee": "0",
            "locked": "600300",
            "executed_volume": "0",
            "trades_count": 0
        }

        order = OrderResult.from_dict(data)

        # 문자열 필드
        assert order.market == "KRW-BTC"
        assert isinstance(order.market, str)
        assert order.uuid == "test-uuid-9999"
        assert isinstance(order.uuid, str)

        # Enum 필드
        assert order.side == OrderSide.BID
        assert isinstance(order.side, OrderSide)
        assert order.ord_type == OrderType.LIMIT
        assert isinstance(order.ord_type, OrderType)
        assert order.state == OrderState.CANCEL
        assert isinstance(order.state, OrderState)

        # float 필드
        assert order.price == 60000000.0
        assert isinstance(order.price, float)
        assert order.volume == 0.01
        assert isinstance(order.volume, float)
        assert order.remaining_volume == 0.01
        assert isinstance(order.remaining_volume, float)
        assert order.executed_volume == 0.0
        assert isinstance(order.executed_volume, float)
        assert order.reserved_fee == 300.0
        assert isinstance(order.reserved_fee, float)
        assert order.remaining_fee == 300.0
        assert isinstance(order.remaining_fee, float)
        assert order.paid_fee == 0.0
        assert isinstance(order.paid_fee, float)
        assert order.locked == 600300.0
        assert isinstance(order.locked, float)
        assert order.trades_count == 0.0
        assert isinstance(order.trades_count, float)

        # datetime 필드
        expected_dt = datetime(2025, 10, 10, 14, 0, 0, tzinfo=timezone(timedelta(hours=9)))
        assert order.created_at == expected_dt
        assert isinstance(order.created_at, datetime)
