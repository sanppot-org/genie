"""한투 API 차트 조회 테스트"""
from datetime import date, time

import pytest

from src.config import HantuConfig
from src.hantu.domestic_api import HantuDomesticAPI
from src.hantu.model.domestic.account_type import AccountType
from src.hantu.model.domestic.chart import ChartInterval, PriceType
from src.hantu.model.domestic.market_code import MarketCode


class TestGetDailyChart:
    """일/주/월/년봉 차트 조회 테스트"""

    def test_get_daily_chart_success(self, mocker):
        """정상적인 일봉 차트 조회 - 삼성전자"""
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
            "output1": {
                "prdy_vrss": "100",
                "prdy_vrss_sign": "2",
                "prdy_ctrt": "0.15",
                "stck_prdy_clpr": "65000",
                "acml_vol": "10000000",
                "acml_tr_pbmn": "650000000000",
                "hts_kor_isnm": "삼성전자",
                "stck_prpr": "65100",
                "stck_shrn_iscd": "005930",
                "prdy_vol": "9000000",
                "stck_mxpr": "84500",
                "stck_llam": "45500",
                "stck_oprc": "65000",
                "stck_hgpr": "65200",
                "stck_lwpr": "64900",
                "stck_prdy_oprc": "64900",
                "stck_prdy_hgpr": "65200",
                "stck_prdy_lwpr": "64800",
                "askp": "65150",
                "bidp": "65100",
                "prdy_vrss_vol": "1000000",
                "vol_tnrt": "5.5",
                "stck_fcam": "100",
                "lstn_stcn": "5969782550",
                "cpfn": "897514",
                "hts_avls": "388632700000000",
                "per": "18.5",
                "eps": "3520",
                "pbr": "1.2",
                "itewhol_loan_rmnd_ratem name": "0.5"
            },
            "output2": [
                {
                    "stck_bsop_date": "20220809",
                    "stck_clpr": "65100",
                    "stck_oprc": "65000",
                    "stck_hgpr": "65200",
                    "stck_lwpr": "64900",
                    "acml_vol": "10000000",
                    "acml_tr_pbmn": "650000000000",
                    "flng_cls_code": "00",
                    "prtt_rate": "0",
                    "mod_yn": "N",
                    "prdy_vrss_sign": "2",
                    "prdy_vrss": "100",
                    "revl_issu_reas": "00"
                },
                {
                    "stck_bsop_date": "20220808",
                    "stck_clpr": "65000",
                    "stck_oprc": "64800",
                    "stck_hgpr": "65100",
                    "stck_lwpr": "64700",
                    "acml_vol": "9000000",
                    "acml_tr_pbmn": "585000000000",
                    "flng_cls_code": "00",
                    "prtt_rate": "0",
                    "mod_yn": "N",
                    "prdy_vrss_sign": "2",
                    "prdy_vrss": "50",
                    "revl_issu_reas": "00"
                }
            ]
        }

        mocker.patch('requests.get', return_value=mock_response)

        # When
        response = api.get_daily_chart(
            ticker="005930",
            start_date=date(2022, 1, 1),
            end_date=date(2022, 8, 9)
        )

        # Then
        assert response is not None
        assert response.output1 is not None
        assert response.output1.hts_kor_isnm == "삼성전자"
        assert response.output1.stck_prpr == "65100"
        assert len(response.output2) == 2
        assert response.output2[0].stck_bsop_date == "20220809"
        assert response.output2[0].stck_clpr == "65100"

    def test_get_daily_chart_with_weekly_interval(self, mocker):
        """주봉 차트 조회"""
        # Given
        config = HantuConfig()
        api = HantuDomesticAPI(config, AccountType.VIRTUAL)

        mocker.patch.object(api, '_get_token', return_value='mock_token')

        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rt_cd": "0",
            "msg_cd": "MCA00000",
            "msg1": "정상처리 되었습니다.",
            "output1": {
                "prdy_vrss": "100",
                "prdy_vrss_sign": "2",
                "prdy_ctrt": "0.15",
                "stck_prdy_clpr": "65000",
                "acml_vol": "50000000",
                "acml_tr_pbmn": "3250000000000",
                "hts_kor_isnm": "삼성전자",
                "stck_prpr": "65100",
                "stck_shrn_iscd": "005930",
                "prdy_vol": "48000000",
                "stck_mxpr": "84500",
                "stck_llam": "45500",
                "stck_oprc": "65000",
                "stck_hgpr": "65200",
                "stck_lwpr": "64900",
                "stck_prdy_oprc": "64900",
                "stck_prdy_hgpr": "65200",
                "stck_prdy_lwpr": "64800",
                "askp": "65150",
                "bidp": "65100",
                "prdy_vrss_vol": "2000000",
                "vol_tnrt": "5.5",
                "stck_fcam": "100",
                "lstn_stcn": "5969782550",
                "cpfn": "897514",
                "hts_avls": "388632700000000",
                "per": "18.5",
                "eps": "3520",
                "pbr": "1.2",
                "itewhol_loan_rmnd_ratem name": "0.5"
            },
            "output2": [
                {
                    "stck_bsop_date": "20220809",
                    "stck_clpr": "65100",
                    "stck_oprc": "65000",
                    "stck_hgpr": "65200",
                    "stck_lwpr": "64900",
                    "acml_vol": "50000000",
                    "acml_tr_pbmn": "3250000000000",
                    "flng_cls_code": "00",
                    "prtt_rate": "0",
                    "mod_yn": "N",
                    "prdy_vrss_sign": "2",
                    "prdy_vrss": "100",
                    "revl_issu_reas": "00"
                }
            ]
        }

        mock_get = mocker.patch('requests.get', return_value=mock_response)

        # When
        response = api.get_daily_chart(
            ticker="005930",
            start_date=date(2022, 1, 1),
            end_date=date(2022, 8, 9),
            interval=ChartInterval.WEEK
        )

        # Then
        assert response is not None
        assert len(response.output2) == 1

        # ChartInterval enum 값이 올바르게 전달되었는지 확인
        call_params = mock_get.call_args[1]['params']
        assert call_params['FID_PERIOD_DIV_CODE'] == ChartInterval.WEEK

    def test_get_daily_chart_with_original_price(self, mocker):
        """원주가 차트 조회"""
        # Given
        config = HantuConfig()
        api = HantuDomesticAPI(config, AccountType.VIRTUAL)

        mocker.patch.object(api, '_get_token', return_value='mock_token')

        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rt_cd": "0",
            "msg_cd": "MCA00000",
            "msg1": "정상처리 되었습니다.",
            "output1": {
                "prdy_vrss": "100",
                "prdy_vrss_sign": "2",
                "prdy_ctrt": "0.15",
                "stck_prdy_clpr": "65000",
                "acml_vol": "10000000",
                "acml_tr_pbmn": "650000000000",
                "hts_kor_isnm": "삼성전자",
                "stck_prpr": "65100",
                "stck_shrn_iscd": "005930",
                "prdy_vol": "9000000",
                "stck_mxpr": "84500",
                "stck_llam": "45500",
                "stck_oprc": "65000",
                "stck_hgpr": "65200",
                "stck_lwpr": "64900",
                "stck_prdy_oprc": "64900",
                "stck_prdy_hgpr": "65200",
                "stck_prdy_lwpr": "64800",
                "askp": "65150",
                "bidp": "65100",
                "prdy_vrss_vol": "1000000",
                "vol_tnrt": "5.5",
                "stck_fcam": "100",
                "lstn_stcn": "5969782550",
                "cpfn": "897514",
                "hts_avls": "388632700000000",
                "per": "18.5",
                "eps": "3520",
                "pbr": "1.2",
                "itewhol_loan_rmnd_ratem name": "0.5"
            },
            "output2": [
                {
                    "stck_bsop_date": "20220809",
                    "stck_clpr": "65100",
                    "stck_oprc": "65000",
                    "stck_hgpr": "65200",
                    "stck_lwpr": "64900",
                    "acml_vol": "10000000",
                    "acml_tr_pbmn": "650000000000",
                    "flng_cls_code": "00",
                    "prtt_rate": "0",
                    "mod_yn": "N",
                    "prdy_vrss_sign": "2",
                    "prdy_vrss": "100",
                    "revl_issu_reas": "00"
                }
            ]
        }

        mock_get = mocker.patch('requests.get', return_value=mock_response)

        # When
        response = api.get_daily_chart(
            ticker="005930",
            start_date=date(2022, 1, 1),
            end_date=date(2022, 8, 9),
            price_type=PriceType.ORIGINAL
        )

        # Then
        assert response is not None

        # PriceType enum 값이 올바르게 전달되었는지 확인
        call_params = mock_get.call_args[1]['params']
        assert call_params['FID_ORG_ADJ_PRC'] == PriceType.ORIGINAL

    def test_get_daily_chart_error(self, mocker):
        """API 에러 응답"""
        # Given
        config = HantuConfig()
        api = HantuDomesticAPI(config, AccountType.VIRTUAL)

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
        with pytest.raises(Exception, match="Error:"):
            api.get_daily_chart(
                ticker="000000",
                start_date=date(2022, 1, 1),
                end_date=date(2022, 8, 9)
            )


class TestGetMinuteChart:
    """분봉 차트 조회 테스트"""

    def test_get_minute_chart_success(self, mocker):
        """정상적인 분봉 차트 조회 - 삼성전자"""
        # Given
        config = HantuConfig()
        api = HantuDomesticAPI(config, AccountType.VIRTUAL)

        mocker.patch.object(api, '_get_token', return_value='mock_token')

        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rt_cd": "0",
            "msg_cd": "MCA00000",
            "msg1": "정상처리 되었습니다.",
            "output1": {
                "prdy_vrss": "100",
                "prdy_vrss_sign": "2",
                "prdy_ctrt": "0.15",
                "stck_prdy_clpr": "65000",
                "acml_vol": "10000000",
                "acml_tr_pbmn": "650000000000",
                "hts_kor_isnm": "삼성전자",
                "stck_prpr": "65100"
            },
            "output2": [
                {
                    "stck_bsop_date": "20241023",
                    "stck_cntg_hour": "130000",
                    "stck_prpr": "65100",
                    "stck_oprc": "65000",
                    "stck_hgpr": "65200",
                    "stck_lwpr": "64900",
                    "cntg_vol": "100000",
                    "acml_tr_pbmn": "650000000000"
                },
                {
                    "stck_bsop_date": "20241023",
                    "stck_cntg_hour": "125900",
                    "stck_prpr": "65000",
                    "stck_oprc": "64950",
                    "stck_hgpr": "65050",
                    "stck_lwpr": "64900",
                    "cntg_vol": "95000",
                    "acml_tr_pbmn": "617500000000"
                }
            ]
        }

        mocker.patch('requests.get', return_value=mock_response)

        # When
        response = api.get_minute_chart(
            ticker="005930",
            target_date=date(2024, 10, 23),
            target_time=time(13, 0, 0)
        )

        # Then
        assert response is not None
        assert response.output1 is not None
        assert response.output1.hts_kor_isnm == "삼성전자"
        assert response.output1.stck_prpr == "65100"
        assert len(response.output2) == 2
        assert response.output2[0].stck_bsop_date == "20241023"
        assert response.output2[0].stck_cntg_hour == "130000"
        assert response.output2[0].stck_prpr == "65100"

    def test_get_minute_chart_with_market_code(self, mocker):
        """시장 코드 지정하여 분봉 조회"""
        # Given
        config = HantuConfig()
        api = HantuDomesticAPI(config, AccountType.VIRTUAL)

        mocker.patch.object(api, '_get_token', return_value='mock_token')

        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rt_cd": "0",
            "msg_cd": "MCA00000",
            "msg1": "정상처리 되었습니다.",
            "output1": {
                "prdy_vrss": "100",
                "prdy_vrss_sign": "2",
                "prdy_ctrt": "0.15",
                "stck_prdy_clpr": "65000",
                "acml_vol": "10000000",
                "acml_tr_pbmn": "650000000000",
                "hts_kor_isnm": "삼성전자",
                "stck_prpr": "65100"
            },
            "output2": [
                {
                    "stck_bsop_date": "20241023",
                    "stck_cntg_hour": "130000",
                    "stck_prpr": "65100",
                    "stck_oprc": "65000",
                    "stck_hgpr": "65200",
                    "stck_lwpr": "64900",
                    "cntg_vol": "100000",
                    "acml_tr_pbmn": "650000000000"
                }
            ]
        }

        mock_get = mocker.patch('requests.get', return_value=mock_response)

        # When
        response = api.get_minute_chart(
            ticker="005930",
            target_date=date(2024, 10, 23),
            target_time=time(13, 0, 0),
            market_code=MarketCode.KRX
        )

        # Then
        assert response is not None

        # MarketCode enum 값이 올바르게 전달되었는지 확인
        call_params = mock_get.call_args[1]['params']
        assert call_params['FID_COND_MRKT_DIV_CODE'] == MarketCode.KRX

    def test_get_minute_chart_error(self, mocker):
        """API 에러 응답"""
        # Given
        config = HantuConfig()
        api = HantuDomesticAPI(config, AccountType.VIRTUAL)

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
        with pytest.raises(Exception, match="Error:"):
            api.get_minute_chart(
                ticker="000000",
                target_date=date(2024, 10, 23),
                target_time=time(13, 0, 0)
            )
