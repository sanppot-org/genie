"""업비트 OrderResult 모델 테스트"""

from datetime import datetime, timedelta, timezone

from src.upbit.model.order import OrderResult, OrderSide, OrderState, OrderType


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
            "trades_count": 0,
        }

        order = OrderResult.from_dict(data)

        # 핵심 필드 검증
        assert order.uuid == "test-uuid-9999"
        assert order.market == "KRW-BTC"

        # Enum 변환 검증 (Pydantic이 자동으로 타입 변환하는지 확인)
        assert order.side == OrderSide.BID
        assert order.ord_type == OrderType.LIMIT
        assert order.state == OrderState.CANCEL

        # datetime 파싱 검증
        expected_dt = datetime(2025, 10, 10, 14, 0, 0, tzinfo=timezone(timedelta(hours=9)))
        assert order.created_at == expected_dt

        # 숫자 타입 변환 검증 (문자열 → float)
        assert order.price == 60000000.0
        assert order.volume == 0.01
