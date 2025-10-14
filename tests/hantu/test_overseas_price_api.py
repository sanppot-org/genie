"""해외주식 시세 조회 API 테스트"""

from unittest.mock import patch

import pytest

from src.config import HantuConfig
from src.hantu.model.overseas.asset_type import OverseasAssetType
from src.hantu.model.overseas.candle_period import OverseasCandlePeriod
from src.hantu.model.overseas.market_code import OverseasMarketCode
from src.hantu.model.overseas.price import (
    OverseasCurrentPriceResponse,
    OverseasDailyCandleResponse,
)
from src.hantu.overseas_api import HantuOverseasAPI


class TestGetCurrentPrice:
    """get_current_price() 메서드 테스트"""

    @pytest.fixture
    def api(self):
        """HantuOverseasAPI 인스턴스 생성"""
        config = HantuConfig()
        return HantuOverseasAPI(config)

    @pytest.fixture
    def mock_response(self):
        """현재가 API 모의 응답"""
        return {
            "rt_cd": "0",
            "msg_cd": "SUCCESS",
            "msg1": "성공",
            "output": {
                "rsym": "NASD.AAPL",
                "zdiv": "2",
                "base": "147.75",
                "pvol": "48000000",
                "last": "150.25",
                "sign": "1",
                "diff": "2.50",
                "rate": "1.69",
                "tvol": "50000000",
                "tamt": "7512500000",
                "ordy": "Y",
            },
        }

    def test_get_current_price_returns_valid_response(self, api, mock_response):
        """현재가 조회가 유효한 응답을 반환하는지 테스트"""
        with patch("requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = mock_response

            result = api.get_current_price(exchange_code=OverseasMarketCode.NAS, symbol="AAPL")

            assert isinstance(result, OverseasCurrentPriceResponse)
            assert result.output.rsym == "NASD.AAPL"
            assert result.output.last == "150.25"
            assert result.output.diff == "2.50"

    def test_get_current_price_with_invalid_params_raises_error(self, api):
        """잘못된 파라미터로 호출 시 에러 발생 테스트"""
        with pytest.raises(ValueError):
            api.get_current_price(symbol="")


class TestGetDailyCandles:
    """get_daily_candles() 메서드 테스트"""

    @pytest.fixture
    def api(self):
        """HantuOverseasAPI 인스턴스 생성"""
        config = HantuConfig()
        return HantuOverseasAPI(config)

    @pytest.fixture
    def mock_response(self):
        """캔들 API 모의 응답"""
        return {
            "rt_cd": "0",
            "msg_cd": "SUCCESS",
            "msg1": "성공",
            "output1": [
                {
                    "xymd": "20240101",
                    "clos": "150.00",
                    "sign": "1",
                    "diff": "1.50",
                    "rate": "1.01",
                    "open": "148.50",
                    "high": "151.00",
                    "low": "148.00",
                    "tvol": "45000000",
                    "tamt": "6750000000",
                }
            ],
            "output2": {},
        }

    def test_get_daily_candles_returns_valid_response(self, api, mock_response):
        """일봉 조회가 유효한 응답을 반환하는지 테스트"""
        with patch("requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = mock_response
            mock_get.return_value.headers = {"tr_cont": ""}

            result = api.get_daily_candles(
                asset_type=OverseasAssetType.INDEX, symbol="AAPL", start_date="20240101", end_date="20240131"
            )

            assert isinstance(result, OverseasDailyCandleResponse)
            assert len(result.output1) > 0
            assert result.output1[0].xymd == "20240101"
            assert result.output1[0].clos == "150.00"

    def test_get_daily_candles_with_period_parameter(self, api, mock_response):
        """기간 구분 파라미터 테스트"""
        with patch("requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = mock_response
            mock_get.return_value.headers = {"tr_cont": ""}

            # 주봉 조회
            result = api.get_daily_candles(
                asset_type=OverseasAssetType.INDEX,
                symbol="AAPL",
                start_date="20240101",
                end_date="20240131",
                period=OverseasCandlePeriod.WEEKLY,
            )

            assert isinstance(result, OverseasDailyCandleResponse)
