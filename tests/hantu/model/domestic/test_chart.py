"""차트 조회 모델 테스트"""

from src.hantu.model.domestic import chart
from src.hantu.model.domestic.market_code import MarketCode


class TestDailyChartRequestQueryParam:
    """DailyChartRequestQueryParam 모델 테스트"""

    def test_enum_serialization(self):
        """ChartInterval과 PriceType enum이 올바르게 직렬화되는지 테스트"""
        # Given
        param = chart.DailyChartRequestQueryParam(
            FID_COND_MRKT_DIV_CODE=MarketCode.KRX,
            FID_INPUT_ISCD="005930",
            FID_INPUT_DATE_1="20220101",
            FID_INPUT_DATE_2="20220809",
            FID_PERIOD_DIV_CODE=chart.ChartInterval.DAY,
            FID_ORG_ADJ_PRC=chart.PriceType.ADJUSTED,
        )

        # When
        serialized = param.model_dump()

        # Then
        assert serialized["FID_COND_MRKT_DIV_CODE"] == "J"
        assert serialized["FID_INPUT_ISCD"] == "005930"
        assert serialized["FID_INPUT_DATE_1"] == "20220101"
        assert serialized["FID_INPUT_DATE_2"] == "20220809"
        assert serialized["FID_PERIOD_DIV_CODE"] == "D"
        assert serialized["FID_ORG_ADJ_PRC"] == "0"


class TestMinuteChartRequestQueryParam:
    """MinuteChartRequestQueryParam 모델 테스트"""

    def test_default_values(self):
        """MinuteChartRequestQueryParam의 기본값이 올바르게 설정되는지 테스트"""
        # Given
        param = chart.MinuteChartRequestQueryParam(
            FID_COND_MRKT_DIV_CODE=MarketCode.KRX,
            FID_INPUT_ISCD="005930",
            FID_INPUT_HOUR_1="130000",
            FID_INPUT_DATE_1="20241023",
        )

        # When
        serialized = param.model_dump()

        # Then
        assert serialized["FID_PW_DATA_INCU_YN"] == "N"
        assert serialized["FID_FAKE_TICK_INCU_YN"] == ""


class TestDailyChartResponseBody:
    """DailyChartResponseBody 모델 테스트"""

    def test_model_creation(self):
        """DailyChartResponseBody 모델이 올바르게 생성되는지 테스트"""
        # Given
        response_data = {
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
                "itewhol_loan_rmnd_ratem name": "0.5",
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
                    "revl_issu_reas": "00",
                }
            ],
        }

        # When
        response = chart.DailyChartResponseBody.model_validate(response_data)

        # Then
        assert response.rt_cd == "0"
        assert response.msg_cd == "MCA00000"
        assert response.output1.stck_prpr == "65100"
        assert response.output1.hts_kor_isnm == "삼성전자"
        assert len(response.output2) == 1
        assert response.output2[0].stck_bsop_date == "20220809"
        assert response.output2[0].stck_clpr == "65100"


class TestMinuteChartResponseBody:
    """MinuteChartResponseBody 모델 테스트"""

    def test_model_creation(self):
        """MinuteChartResponseBody 모델이 올바르게 생성되는지 테스트"""
        # Given
        response_data = {
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
                    "acml_tr_pbmn": "650000000000",
                }
            ],
        }

        # When
        response = chart.MinuteChartResponseBody.model_validate(response_data)

        # Then
        assert response.rt_cd == "0"
        assert response.msg_cd == "MCA00000"
        assert response.output1.stck_prpr == "65100"
        assert response.output1.hts_kor_isnm == "삼성전자"
        assert len(response.output2) == 1
        assert response.output2[0].stck_bsop_date == "20241023"
        assert response.output2[0].stck_cntg_hour == "130000"
        assert response.output2[0].stck_prpr == "65100"
