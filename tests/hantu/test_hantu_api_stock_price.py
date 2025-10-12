"""
한투 API 주식 시세 조회 테스트
"""

from src.config import HantuConfig
from src.hantu.hantu_api import HantuAPI
from src.hantu.model import AccountType


class TestGetStockPrice:
    """주식 현재가 시세 조회 테스트"""

    def test_get_stock_price_success(self):
        """정상적인 시세 조회 - 삼성전자"""
        # Given
        config = HantuConfig()
        api = HantuAPI(config, AccountType.VIRTUAL)
        ticker = "005930"  # 삼성전자

        # When
        response = api.get_stock_price(ticker)

        # Then
        assert response is not None
        assert response.output is not None
        # 현재가 필드 존재 확인 (필드명은 실제 API 응답 확인 후 조정)
        assert hasattr(response.output, 'stck_prpr')  # 주식 현재가

    def test_get_stock_price_with_market_code(self):
        """시장 코드 지정하여 조회"""
        # Given
        config = HantuConfig()
        api = HantuAPI(config, AccountType.VIRTUAL)
        ticker = "005930"
        market_code = "J"  # KRX

        # When
        response = api.get_stock_price(ticker, market_code)

        # Then
        assert response is not None
        assert response.output is not None

    def test_get_stock_price_kosdaq(self):
        """코스닥 종목 조회 - 카카오"""
        # Given
        config = HantuConfig()
        api = HantuAPI(config, AccountType.VIRTUAL)
        ticker = "035720"  # 카카오

        # When
        response = api.get_stock_price(ticker)

        # Then
        assert response is not None
        assert response.output is not None

    def test_get_stock_price_response_structure(self):
        """응답 구조 검증"""
        # Given
        config = HantuConfig()
        api = HantuAPI(config, AccountType.VIRTUAL)
        ticker = "005930"

        # When
        response = api.get_stock_price(ticker)

        # Then - 기본 필드 존재 확인
        assert response.output is not None
        # 주요 시세 정보 필드 확인 (필드명은 실제 API 문서 기준)
        output = response.output
        assert hasattr(output, 'stck_prpr')  # 현재가
