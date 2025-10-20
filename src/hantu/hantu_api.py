from src.config import HantuConfig
from src.hantu.domestic_api import HantuDomesticAPI
from src.hantu.model.domestic.account_type import AccountType
from src.hantu.overseas_api import HantuOverseasAPI


class HantuAPI:
    """한국투자증권 API 통합 클라이언트 (Facade)

    국내 주식과 해외 주식 API를 통합하여 제공합니다.

    Args:
        config: 한투 API 설정
        account_type: 계좌 타입 (REAL: 실제 계좌, VIRTUAL: 가상 계좌)

    Examples:
        >>> from src.config import HantuConfig
        >>> from src.hantu import HantuAPI, AccountType
        >>> from hantu.model.overseas import OverseasExchangeCode
        >>> from hantu.model.domestic import TradingCurrencyCode
        >>>
        >>> config = HantuConfig()
        >>> api = HantuAPI(config, AccountType.REAL)
        >>>
        >>> # 국내 주식
        >>> domestic_balance = api.domestic.get_balance()
        >>> stock_price = api.domestic.get_stock_price(ticker="005930")
        >>>
        >>> # 해외 주식
        >>> overseas_balance = api.overseas.get_balance(
        >>>     ovrs_excg_cd=OverseasExchangeCode.NASD,
        >>>     tr_crcy_cd=TradingCurrencyCode.USD
        >>> )
    """

    def __init__(self, config: HantuConfig, account_type: AccountType = AccountType.REAL) -> None:
        """
        Args:
            config: 한투 API 설정
            account_type: 계좌 타입 (REAL: 실제 계좌, VIRTUAL: 가상 계좌)
        """
        self.domestic = HantuDomesticAPI(config, account_type)
        self.overseas = HantuOverseasAPI(config, account_type)
