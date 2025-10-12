"""주식 현재가 시세 모델 테스트"""

from src.hantu.model.domestic import stock_price
from src.hantu.model.domestic.market_code import MarketCode


class TestRequestQueryParam:
    """RequestQueryParam 모델 테스트"""

    def test_market_code_enum_serialization(self):
        """MarketCode enum이 올바르게 직렬화되는지 테스트"""
        # Given
        param = stock_price.RequestQueryParam(
            FID_COND_MRKT_DIV_CODE=MarketCode.KRX,
            FID_INPUT_ISCD="005930"
        )

        # When
        serialized = param.model_dump()

        # Then
        assert serialized["FID_COND_MRKT_DIV_CODE"] == "J"
        assert serialized["FID_INPUT_ISCD"] == "005930"

    def test_market_code_enum_values(self):
        """다양한 MarketCode enum 값들이 올바르게 직렬화되는지 테스트"""
        # Given & When & Then
        krx_param = stock_price.RequestQueryParam(
            FID_COND_MRKT_DIV_CODE=MarketCode.KRX,
            FID_INPUT_ISCD="005930"
        )
        assert krx_param.model_dump()["FID_COND_MRKT_DIV_CODE"] == "J"

        nxt_param = stock_price.RequestQueryParam(
            FID_COND_MRKT_DIV_CODE=MarketCode.NXT,
            FID_INPUT_ISCD="005930"
        )
        assert nxt_param.model_dump()["FID_COND_MRKT_DIV_CODE"] == "NX"

        all_param = stock_price.RequestQueryParam(
            FID_COND_MRKT_DIV_CODE=MarketCode.ALL,
            FID_INPUT_ISCD="005930"
        )
        assert all_param.model_dump()["FID_COND_MRKT_DIV_CODE"] == "UN"
