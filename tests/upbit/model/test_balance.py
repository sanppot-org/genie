"""업비트 BalanceInfo 모델 테스트"""

from src.upbit.model.balance import BalanceInfo


class TestBalanceInfo:
    """BalanceInfo 모델 테스트"""

    def test_BalanceInfo_from_dict_메서드(self):
        """from_dict 메서드로 BalanceInfo를 생성할 수 있다"""
        data = {
            "currency": "ETH",
            "balance": "10.5",
            "locked": "0.0",
            "avg_buy_price": "3000000",
            "avg_buy_price_modified": False,
            "unit_currency": "KRW",
        }

        balance = BalanceInfo.from_dict(data)

        # 핵심 필드 검증
        assert balance.currency == "ETH"
        assert balance.unit_currency == "KRW"

        # 숫자 타입 변환 검증 (문자열 → float)
        assert balance.balance == 10.5
        assert balance.avg_buy_price == 3000000.0

        # bool 필드 검증
        assert balance.avg_buy_price_modified is False
