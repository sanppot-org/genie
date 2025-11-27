"""업비트 Order 모델 테스트"""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from src.upbit.model.order import OrderParams, OrderResult, OrderSide, OrderState, OrderType, TimeInForce


class TestOrderParams:
    """OrderParams 모델 테스트"""

    def test_지정가_주문_생성_성공(self):
        """지정가 주문은 market, side, ord_type, price, volume이 필요하다"""
        params = OrderParams(
            market="KRW-BTC",
            side=OrderSide.BID,
            ord_type=OrderType.LIMIT,
            price=60000000.0,
            volume=0.01,
        )

        assert params.market == "KRW-BTC"
        assert params.side == OrderSide.BID
        assert params.ord_type == OrderType.LIMIT
        assert params.price == 60000000.0
        assert params.volume == 0.01

    def test_시장가_매수_주문_생성_성공(self):
        """시장가 매수(price)는 price가 필요하다"""
        params = OrderParams(
            market="KRW-BTC",
            side=OrderSide.BID,
            ord_type=OrderType.PRICE,
            price=10000.0,  # 매수 금액
        )

        assert params.market == "KRW-BTC"
        assert params.side == OrderSide.BID
        assert params.ord_type == OrderType.PRICE
        assert params.price == 10000.0
        assert params.volume is None

    def test_시장가_매도_주문_생성_성공(self):
        """시장가 매도(market)는 volume이 필요하다"""
        params = OrderParams(
            market="KRW-BTC",
            side=OrderSide.ASK,
            ord_type=OrderType.MARKET,
            volume=0.01,  # 매도 수량
        )

        assert params.market == "KRW-BTC"
        assert params.side == OrderSide.ASK
        assert params.ord_type == OrderType.MARKET
        assert params.volume == 0.01
        assert params.price is None

    def test_time_in_force_옵션_포함(self):
        """time_in_force는 선택적으로 추가할 수 있다"""
        params = OrderParams(
            market="KRW-BTC",
            side=OrderSide.BID,
            ord_type=OrderType.LIMIT,
            price=60000000.0,
            volume=0.01,
            time_in_force=TimeInForce.IOC,
        )

        assert params.time_in_force == TimeInForce.IOC

    def test_지정가_주문_price_누락_시_실패(self):
        """지정가 주문에서 price가 없으면 ValidationError가 발생한다"""
        with pytest.raises(ValidationError) as exc_info:
            OrderParams(
                market="KRW-BTC",
                side=OrderSide.BID,
                ord_type=OrderType.LIMIT,
                volume=0.01,
                # price 누락
            )

        assert "price" in str(exc_info.value).lower()

    def test_지정가_주문_volume_누락_시_실패(self):
        """지정가 주문에서 volume이 없으면 ValidationError가 발생한다"""
        with pytest.raises(ValidationError) as exc_info:
            OrderParams(
                market="KRW-BTC",
                side=OrderSide.BID,
                ord_type=OrderType.LIMIT,
                price=60000000.0,
                # volume 누락
            )

        assert "volume" in str(exc_info.value).lower()

    def test_시장가_매수_price_누락_시_실패(self):
        """시장가 매수에서 price가 없으면 ValidationError가 발생한다"""
        with pytest.raises(ValidationError) as exc_info:
            OrderParams(
                market="KRW-BTC",
                side=OrderSide.BID,
                ord_type=OrderType.PRICE,
                # price 누락
            )

        assert "price" in str(exc_info.value).lower()

    def test_시장가_매도_volume_누락_시_실패(self):
        """시장가 매도에서 volume이 없으면 ValidationError가 발생한다"""
        with pytest.raises(ValidationError) as exc_info:
            OrderParams(
                market="KRW-BTC",
                side=OrderSide.ASK,
                ord_type=OrderType.MARKET,
                # volume 누락
            )

        assert "volume" in str(exc_info.value).lower()

    def test_to_dict_메서드_None_값_제외(self):
        """to_dict()는 None 값을 제외한 딕셔너리를 반환하고, 숫자를 문자열로 변환한다"""
        params = OrderParams(
            market="KRW-BTC",
            side=OrderSide.BID,
            ord_type=OrderType.PRICE,
            price=10000.0,
        )

        result = params.to_dict()

        assert result == {
            "market": "KRW-BTC",
            "side": "bid",
            "ord_type": "price",
            "price": "10000.0",  # float -> string 변환
        }
        assert "volume" not in result
        assert "time_in_force" not in result

    def test_최유리지정가_매수_주문_생성_성공(self):
        """최유리지정가 매수는 price와 time_in_force가 필요하다"""
        params = OrderParams(
            market="KRW-BTC",
            side=OrderSide.BID,
            ord_type=OrderType.BEST,
            price=10000000.0,  # 매수 총액
            time_in_force=TimeInForce.IOC,
        )

        assert params.market == "KRW-BTC"
        assert params.side == OrderSide.BID
        assert params.ord_type == OrderType.BEST
        assert params.price == 10000000.0
        assert params.time_in_force == TimeInForce.IOC
        assert params.volume is None

    def test_최유리지정가_매도_주문_생성_성공(self):
        """최유리지정가 매도는 volume과 time_in_force가 필요하다"""
        params = OrderParams(
            market="KRW-BTC",
            side=OrderSide.ASK,
            ord_type=OrderType.BEST,
            volume=0.01,  # 매도 수량
            time_in_force=TimeInForce.FOK,
        )

        assert params.market == "KRW-BTC"
        assert params.side == OrderSide.ASK
        assert params.ord_type == OrderType.BEST
        assert params.volume == 0.01
        assert params.time_in_force == TimeInForce.FOK
        assert params.price is None

    def test_최유리지정가_매수_price_누락_시_실패(self):
        """최유리지정가 매수에서 price가 없으면 ValidationError가 발생한다"""
        with pytest.raises(ValidationError) as exc_info:
            OrderParams(
                market="KRW-BTC",
                side=OrderSide.BID,
                ord_type=OrderType.BEST,
                time_in_force=TimeInForce.IOC,
                # price 누락
            )

        assert "price" in str(exc_info.value).lower()

    def test_최유리지정가_매도_volume_누락_시_실패(self):
        """최유리지정가 매도에서 volume이 없으면 ValidationError가 발생한다"""
        with pytest.raises(ValidationError) as exc_info:
            OrderParams(
                market="KRW-BTC",
                side=OrderSide.ASK,
                ord_type=OrderType.BEST,
                time_in_force=TimeInForce.FOK,
                # volume 누락
            )

        assert "volume" in str(exc_info.value).lower()

    def test_최유리지정가_time_in_force_누락_시_실패(self):
        """최유리지정가 주문에서 time_in_force가 없으면 ValidationError가 발생한다"""
        with pytest.raises(ValidationError) as exc_info:
            OrderParams(
                market="KRW-BTC",
                side=OrderSide.BID,
                ord_type=OrderType.BEST,
                price="10000000",
                # time_in_force 누락
            )

        assert "time_in_force" in str(exc_info.value).lower()

    def test_최유리지정가_post_only_사용_시_실패(self):
        """최유리지정가 주문은 post_only를 사용할 수 없다"""
        with pytest.raises(ValidationError) as exc_info:
            OrderParams(
                market="KRW-BTC",
                side=OrderSide.BID,
                ord_type=OrderType.BEST,
                price=10000000.0,
                time_in_force=TimeInForce.POST_ONLY,  # best 주문에서 post_only 불가
            )

        assert "post_only" in str(exc_info.value).lower() or "ioc" in str(exc_info.value).lower() or "fok" in str(exc_info.value).lower()


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
