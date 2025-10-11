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
            "unit_currency": "KRW"
        }

        balance = BalanceInfo.from_dict(data)

        assert balance.currency == "ETH"
        assert balance.balance == 10.5
        assert balance.locked == 0.0
        assert balance.avg_buy_price == 3000000.0
        assert balance.avg_buy_price_modified == False
        assert balance.unit_currency == "KRW"
