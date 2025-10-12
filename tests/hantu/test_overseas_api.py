"""한국투자증권 해외 주식 API 테스트"""

import pytest

from src.config import HantuConfig
from src.hantu.model import AccountType, OverseasExchangeCode, TradingCurrencyCode
from src.hantu.overseas_api import HantuOverseasAPI


class TestHantuOverseasAPIInit:
    """HantuOverseasAPI 초기화 테스트"""

    def test_init_with_real_account(self):
        """실제 계좌로 초기화 시 실제 계좌 설정 사용"""
        # Given
        config = HantuConfig()

        # When
        api = HantuOverseasAPI(config, AccountType.REAL)

        # Then
        assert api.account_type == AccountType.REAL
        assert api.cano == config.cano
        assert api.acnt_prdt_cd == config.acnt_prdt_cd
        assert api.app_key == config.app_key
        assert api.app_secret == config.app_secret
        assert api.url_base == config.url_base
        assert api.token_path == config.token_path

    def test_init_with_virtual_account(self):
        """가상 계좌로 초기화 시 가상 계좌 설정 사용"""
        # Given
        config = HantuConfig()

        # When
        api = HantuOverseasAPI(config, AccountType.VIRTUAL)

        # Then
        assert api.account_type == AccountType.VIRTUAL
        assert api.cano == config.v_cano
        assert api.acnt_prdt_cd == config.v_acnt_prdt_cd
        assert api.app_key == config.v_app_key
        assert api.app_secret == config.v_app_secret
        assert api.url_base == config.v_url_base
        assert api.token_path == config.v_token_path


class TestGetBalance:
    """get_balance 메서드 테스트"""

    def test_get_balance_single_page(self, mocker):
        """단일 페이지 응답 (연속 조회 불필요)"""
        # Given
        config = HantuConfig()
        api = HantuOverseasAPI(config, AccountType.VIRTUAL)

        # _get_token mock
        mocker.patch.object(api, '_get_token', return_value='mock_token')

        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.headers = {'tr_cont': 'D'}  # 마지막 페이지
        mock_response.json.return_value = {
            "rt_cd": "0",
            "msg_cd": "MCA00000",
            "msg1": "정상처리 되었습니다.",
            "ctx_area_fk200": "",
            "ctx_area_nk200": "",
            "output1": [
                {
                    "cano": "12345678",
                    "acnt_prdt_cd": "01",
                    "prdt_type_cd": "512",
                    "ovrs_pdno": "AAPL",
                    "ovrs_item_name": "APPLE INC",
                    "frcr_evlu_pfls_amt": "100.00",
                    "evlu_pfls_rt": "5.26",
                    "pchs_avg_pric": "150.00",
                    "ovrs_cblc_qty": "10",
                    "ord_psbl_qty": "10",
                    "frcr_pchs_amt1": "1500.00",
                    "ovrs_stck_evlu_amt": "1600.00",
                    "now_pric2": "160.00",
                    "tr_crcy_cd": "USD",
                    "ovrs_excg_cd": "NASD",
                    "loan_type_cd": "",
                    "loan_dt": "",
                    "expd_dt": ""
                }
            ],
            "output2": {
                "frcr_pchs_amt1": "1500.00",
                "ovrs_rlzt_pfls_amt": "0.00",
                "ovrs_tot_pfls": "100.00",
                "rlzt_erng_rt": "0.00",
                "tot_evlu_pfls_amt": "100.00",
                "tot_pftrt": "6.67",
                "frcr_buy_amt_smtl1": "1500.00",
                "ovrs_rlzt_pfls_amt2": "0.00",
                "frcr_buy_amt_smtl2": "1500.00"
            }
        }

        mocker.patch('requests.get', return_value=mock_response)

        # When
        result = api.get_balance(ovrs_excg_cd=OverseasExchangeCode.NASD, tr_crcy_cd=TradingCurrencyCode.USD)

        # Then
        assert len(result.output1) == 1
        assert result.output1[0].ovrs_pdno == "AAPL"
        assert result.output1[0].ovrs_item_name == "APPLE INC"
        assert result.output1[0].ovrs_cblc_qty == "10"

        # output2 검증
        assert result.output2.tot_evlu_pfls_amt == "100.00"
        assert result.output2.tot_pftrt == "6.67"

    def test_get_balance_multiple_pages(self, mocker):
        """다중 페이지 응답 (연속 조회 필요)"""
        # Given
        config = HantuConfig()
        api = HantuOverseasAPI(config, AccountType.VIRTUAL)

        # _get_token mock
        mocker.patch.object(api, '_get_token', return_value='mock_token')

        # 첫 번째 페이지 응답
        first_response = mocker.Mock()
        first_response.status_code = 200
        first_response.headers = {'tr_cont': 'M'}  # 다음 페이지 존재
        first_response.json.return_value = {
            "rt_cd": "0",
            "msg_cd": "MCA00000",
            "msg1": "정상처리 되었습니다.",
            "ctx_area_fk200": "CTX_FK_001",
            "ctx_area_nk200": "CTX_NK_001",
            "output1": [
                {
                    "cano": "12345678",
                    "acnt_prdt_cd": "01",
                    "prdt_type_cd": "512",
                    "ovrs_pdno": "AAPL",
                    "ovrs_item_name": "APPLE INC",
                    "frcr_evlu_pfls_amt": "100.00",
                    "evlu_pfls_rt": "5.26",
                    "pchs_avg_pric": "150.00",
                    "ovrs_cblc_qty": "10",
                    "ord_psbl_qty": "10",
                    "frcr_pchs_amt1": "1500.00",
                    "ovrs_stck_evlu_amt": "1600.00",
                    "now_pric2": "160.00",
                    "tr_crcy_cd": "USD",
                    "ovrs_excg_cd": "NASD",
                    "loan_type_cd": "",
                    "loan_dt": "",
                    "expd_dt": ""
                }
            ],
            "output2": {
                "frcr_pchs_amt1": "0.00",
                "ovrs_rlzt_pfls_amt": "0.00",
                "ovrs_tot_pfls": "0.00",
                "rlzt_erng_rt": "0.00",
                "tot_evlu_pfls_amt": "0.00",
                "tot_pftrt": "0.00",
                "frcr_buy_amt_smtl1": "0.00",
                "ovrs_rlzt_pfls_amt2": "0.00",
                "frcr_buy_amt_smtl2": "0.00"
            }
        }

        # 두 번째 페이지 응답
        second_response = mocker.Mock()
        second_response.status_code = 200
        second_response.headers = {'tr_cont': 'D'}  # 마지막 페이지
        second_response.json.return_value = {
            "rt_cd": "0",
            "msg_cd": "MCA00000",
            "msg1": "정상처리 되었습니다.",
            "ctx_area_fk200": "",
            "ctx_area_nk200": "",
            "output1": [
                {
                    "cano": "12345678",
                    "acnt_prdt_cd": "01",
                    "prdt_type_cd": "512",
                    "ovrs_pdno": "TSLA",
                    "ovrs_item_name": "TESLA INC",
                    "frcr_evlu_pfls_amt": "50.00",
                    "evlu_pfls_rt": "2.50",
                    "pchs_avg_pric": "200.00",
                    "ovrs_cblc_qty": "5",
                    "ord_psbl_qty": "5",
                    "frcr_pchs_amt1": "1000.00",
                    "ovrs_stck_evlu_amt": "1050.00",
                    "now_pric2": "210.00",
                    "tr_crcy_cd": "USD",
                    "ovrs_excg_cd": "NASD",
                    "loan_type_cd": "",
                    "loan_dt": "",
                    "expd_dt": ""
                }
            ],
            "output2": {
                "frcr_pchs_amt1": "2500.00",
                "ovrs_rlzt_pfls_amt": "0.00",
                "ovrs_tot_pfls": "150.00",
                "rlzt_erng_rt": "0.00",
                "tot_evlu_pfls_amt": "150.00",
                "tot_pftrt": "6.00",
                "frcr_buy_amt_smtl1": "2500.00",
                "ovrs_rlzt_pfls_amt2": "0.00",
                "frcr_buy_amt_smtl2": "2500.00"
            }
        }

        mock_get = mocker.patch('requests.get')
        mock_get.side_effect = [first_response, second_response]

        # When
        result = api.get_balance(ovrs_excg_cd=OverseasExchangeCode.NASD, tr_crcy_cd=TradingCurrencyCode.USD)

        # Then
        assert len(result.output1) == 2
        assert result.output1[0].ovrs_pdno == "AAPL"
        assert result.output1[0].ovrs_item_name == "APPLE INC"
        assert result.output1[1].ovrs_pdno == "TSLA"
        assert result.output1[1].ovrs_item_name == "TESLA INC"

        # output2는 마지막 페이지의 값 사용
        assert result.output2.tot_evlu_pfls_amt == "150.00"
        assert result.output2.tot_pftrt == "6.00"

        # 두 번째 호출 시 연속 조회 키가 전달되었는지 확인
        assert mock_get.call_count == 2
        second_call_params = mock_get.call_args_list[1][1]['params']
        assert second_call_params['CTX_AREA_FK200'] == "CTX_FK_001"
        assert second_call_params['CTX_AREA_NK200'] == "CTX_NK_001"

    def test_get_balance_error(self, mocker):
        """API 에러 응답"""
        # Given
        config = HantuConfig()
        api = HantuOverseasAPI(config, AccountType.VIRTUAL)

        # _get_token mock
        mocker.patch.object(api, '_get_token', return_value='mock_token')

        mock_response = mocker.Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"

        mocker.patch('requests.get', return_value=mock_response)

        # When & Then
        with pytest.raises(Exception, match="해외 주식 잔고 조회 실패"):
            api.get_balance(ovrs_excg_cd=OverseasExchangeCode.NASD, tr_crcy_cd=TradingCurrencyCode.USD)
