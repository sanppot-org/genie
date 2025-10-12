"""
한투 API 주식 시세 조회 테스트
"""
import pytest

from src.config import HantuConfig
from src.hantu.domestic_api import HantuDomesticAPI
from src.hantu.model import AccountType, MarketCode


class TestGetStockPrice:
    """주식 현재가 시세 조회 테스트"""

    def test_get_stock_price_success(self, mocker):
        """정상적인 시세 조회 - 삼성전자"""
        # Given
        config = HantuConfig()
        api = HantuDomesticAPI(config, AccountType.VIRTUAL)

        # _get_token mock
        mocker.patch.object(api, '_get_token', return_value='mock_token')

        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rt_cd": "0",
            "msg_cd": "MCA00000",
            "msg1": "정상처리 되었습니다.",
            "output": {
                "stck_prpr": "71000",
                "stck_oprc": "70500",
                "stck_hgpr": "71500",
                "stck_lwpr": "70000",
                "stck_mxpr": "91000",
                "stck_llam": "51000",
                "stck_sdpr": "71000",
                "acml_vol": "15000000",
                "acml_tr_pbmn": "1065000000000",
                "prdy_vrss": "1000",
                "prdy_vrss_sign": "2",
                "prdy_ctrt": "1.43",
                "per": "10.5",
                "pbr": "1.2",
                "eps": "6800",
                "bps": "59000"
            }
        }

        mocker.patch('requests.get', return_value=mock_response)

        # When
        response = api.get_stock_price("005930")

        # Then
        assert response is not None
        assert response.output is not None
        assert response.output.stck_prpr == "71000"
        assert response.output.stck_oprc == "70500"
        assert response.output.acml_vol == "15000000"
        assert response.output.prdy_vrss == "1000"
        assert response.output.prdy_ctrt == "1.43"

    def test_get_stock_price_with_market_code(self, mocker):
        """시장 코드 지정하여 조회"""
        # Given
        config = HantuConfig()
        api = HantuDomesticAPI(config, AccountType.VIRTUAL)

        # _get_token mock
        mocker.patch.object(api, '_get_token', return_value='mock_token')

        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rt_cd": "0",
            "msg_cd": "MCA00000",
            "msg1": "정상처리 되었습니다.",
            "output": {
                "stck_prpr": "71000",
                "stck_oprc": "70500",
                "stck_hgpr": "71500",
                "stck_lwpr": "70000",
                "stck_mxpr": "91000",
                "stck_llam": "51000",
                "stck_sdpr": "71000",
                "acml_vol": "15000000",
                "acml_tr_pbmn": "1065000000000",
                "prdy_vrss": "1000",
                "prdy_vrss_sign": "2",
                "prdy_ctrt": "1.43"
            }
        }

        mock_get = mocker.patch('requests.get', return_value=mock_response)

        # When
        response = api.get_stock_price("005930", MarketCode.KRX)

        # Then
        assert response is not None
        assert response.output is not None

        # MarketCode enum 값이 올바르게 전달되었는지 확인
        call_params = mock_get.call_args[1]['params']
        assert call_params['FID_COND_MRKT_DIV_CODE'] == MarketCode.KRX

    def test_get_stock_price_kosdaq(self, mocker):
        """코스닥 종목 조회 - 카카오"""
        # Given
        config = HantuConfig()
        api = HantuDomesticAPI(config, AccountType.VIRTUAL)

        # _get_token mock
        mocker.patch.object(api, '_get_token', return_value='mock_token')

        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rt_cd": "0",
            "msg_cd": "MCA00000",
            "msg1": "정상처리 되었습니다.",
            "output": {
                "stck_prpr": "52000",
                "stck_oprc": "51500",
                "stck_hgpr": "52500",
                "stck_lwpr": "51000",
                "stck_mxpr": "67000",
                "stck_llam": "37000",
                "stck_sdpr": "52000",
                "acml_vol": "8000000",
                "acml_tr_pbmn": "416000000000",
                "prdy_vrss": "2000",
                "prdy_vrss_sign": "2",
                "prdy_ctrt": "4.00",
                "hts_kor_isnm": "카카오"
            }
        }

        mocker.patch('requests.get', return_value=mock_response)

        # When
        response = api.get_stock_price("035720")

        # Then
        assert response is not None
        assert response.output is not None
        assert response.output.stck_prpr == "52000"
        assert response.output.hts_kor_isnm == "카카오"

    def test_get_stock_price_response_structure(self, mocker):
        """응답 구조 검증"""
        # Given
        config = HantuConfig()
        api = HantuDomesticAPI(config, AccountType.VIRTUAL)

        # _get_token mock
        mocker.patch.object(api, '_get_token', return_value='mock_token')

        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rt_cd": "0",
            "msg_cd": "MCA00000",
            "msg1": "정상처리 되었습니다.",
            "output": {
                "stck_prpr": "71000",
                "stck_oprc": "70500",
                "stck_hgpr": "71500",
                "stck_lwpr": "70000",
                "stck_mxpr": "91000",
                "stck_llam": "51000",
                "stck_sdpr": "71000",
                "acml_vol": "15000000",
                "acml_tr_pbmn": "1065000000000",
                "prdy_vrss": "1000",
                "prdy_vrss_sign": "2",
                "prdy_ctrt": "1.43"
            }
        }

        mocker.patch('requests.get', return_value=mock_response)

        # When
        response = api.get_stock_price("005930")

        # Then - 기본 필드 존재 확인
        assert response.output is not None
        output = response.output
        assert hasattr(output, 'stck_prpr')  # 현재가
        assert hasattr(output, 'stck_oprc')  # 시가
        assert hasattr(output, 'stck_hgpr')  # 고가
        assert hasattr(output, 'stck_lwpr')  # 저가
        assert hasattr(output, 'acml_vol')  # 누적 거래량
        assert hasattr(output, 'prdy_vrss')  # 전일 대비
        assert hasattr(output, 'prdy_ctrt')  # 전일 대비율

    def test_get_stock_price_error(self, mocker):
        """API 에러 응답"""
        # Given
        config = HantuConfig()
        api = HantuDomesticAPI(config, AccountType.VIRTUAL)

        # _get_token mock
        mocker.patch.object(api, '_get_token', return_value='mock_token')

        mock_response = mocker.Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_response.json.return_value = {
            "rt_cd": "1",
            "msg_cd": "EGW00123",
            "msg1": "종목코드 오류"
        }

        mocker.patch('requests.get', return_value=mock_response)

        # When & Then
        with pytest.raises(Exception, match="주식 시세 조회 실패"):
            api.get_stock_price("000000")
