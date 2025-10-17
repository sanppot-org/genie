"""한국투자증권 국내 주식 API 테스트"""

from src.config import HantuConfig
from src.hantu.domestic_api import HantuDomesticAPI
from src.hantu.model.domestic.account_type import AccountType


class TestHantuDomesticAPIInit:
    """HantuDomesticAPI 초기화 테스트"""

    def test_init_with_real_account(self):
        """실제 계좌로 초기화 시 실제 계좌 설정 사용"""
        # Given
        config = HantuConfig()

        # When
        api = HantuDomesticAPI(config, AccountType.REAL)

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
        api = HantuDomesticAPI(config, AccountType.VIRTUAL)

        # Then
        assert api.account_type == AccountType.VIRTUAL
        assert api.cano == config.v_cano
        assert api.acnt_prdt_cd == config.v_acnt_prdt_cd
        assert api.app_key == config.v_app_key
        assert api.app_secret == config.v_app_secret
        assert api.url_base == config.v_url_base
        assert api.token_path == config.v_token_path

    def test_real_and_virtual_use_different_configs(self):
        """실제 계좌와 가상 계좌가 서로 다른 설정 사용"""
        # Given
        config = HantuConfig()

        # When
        real_api = HantuDomesticAPI(config, AccountType.REAL)
        virtual_api = HantuDomesticAPI(config, AccountType.VIRTUAL)

        # Then
        assert real_api.app_key != virtual_api.app_key
        assert real_api.app_secret != virtual_api.app_secret
        assert real_api.url_base != virtual_api.url_base
        assert real_api.cano != virtual_api.cano


class TestGetBalance:
    """get_balance 메서드 테스트"""

    def test_get_balance_single_page(self, mocker):
        """단일 페이지 응답 (연속 조회 불필요)"""
        # Given
        config = HantuConfig()
        api = HantuDomesticAPI(config, AccountType.VIRTUAL)

        # _get_token mock
        mocker.patch.object(api, "_get_token", return_value="mock_token")

        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.headers = {"tr_cont": "D"}  # 마지막 페이지
        mock_response.json.return_value = {
            "rt_cd": "0",
            "msg_cd": "MCA00000",
            "msg1": "정상처리 되었습니다.",
            "ctx_area_fk100": "",
            "ctx_area_nk100": "",
            "output1": [
                {
                    "pdno": "005930",
                    "prdt_name": "삼성전자",
                    "trad_dvsn_name": "현금",
                    "bfdy_buy_qty": "0",
                    "bfdy_sll_qty": "0",
                    "thdt_buyqty": "10",
                    "thdt_sll_qty": "0",
                    "hldg_qty": "10",
                    "ord_psbl_qty": "10",
                    "pchs_avg_pric": "70000.00",
                    "pchs_amt": "700000",
                    "prpr": "71000",
                    "evlu_amt": "710000",
                    "evlu_pfls_amt": "10000",
                    "evlu_pfls_rt": "1.43",
                    "evlu_erng_rt": "1.43",
                    "loan_dt": "",
                    "loan_amt": "0",
                    "stln_slng_chgs": "0",
                    "expd_dt": "",
                    "fltt_rt": "0.00",
                    "bfdy_cprs_icdc": "1000",
                    "item_mgna_rt_name": "",
                    "grta_rt_name": "",
                    "sbst_pric": "0",
                    "stck_loan_unpr": "0",
                }
            ],
            "output2": [
                {
                    "dnca_tot_amt": "1000000",
                    "nxdy_excc_amt": "0",
                    "prvs_rcdl_excc_amt": "0",
                    "cma_evlu_amt": "0",
                    "bfdy_buy_amt": "0",
                    "thdt_buy_amt": "700000",
                    "nxdy_auto_rdpt_amt": "0",
                    "bfdy_sll_amt": "0",
                    "thdt_sll_amt": "0",
                    "d2_auto_rdpt_amt": "0",
                    "bfdy_tlex_amt": "0",
                    "thdt_tlex_amt": "0",
                    "tot_loan_amt": "0",
                    "scts_evlu_amt": "710000",
                    "tot_evlu_amt": "1710000",
                    "nass_amt": "1710000",
                    "fncg_gld_auto_rdpt_yn": "N",
                    "pchs_amt_smtl_amt": "700000",
                    "evlu_amt_smtl_amt": "710000",
                    "evlu_pfls_smtl_amt": "10000",
                    "tot_stln_slng_chgs": "0",
                    "bfdy_tot_asst_evlu_amt": "1700000",
                    "asst_icdc_amt": "10000",
                    "asst_icdc_erng_rt": "0.59",
                }
            ],
        }

        mocker.patch("requests.get", return_value=mock_response)

        # When
        result = api.get_balance()

        # Then
        assert len(result.output1) == 1
        assert result.output1[0].pdno == "005930"
        assert result.output1[0].prdt_name == "삼성전자"
        assert result.output1[0].hldg_qty == "10"

        # output2 검증
        assert len(result.output2) == 1
        assert result.output2[0].tot_evlu_amt == "1710000"
        assert result.output2[0].nass_amt == "1710000"

    def test_get_balance_multiple_pages(self, mocker):
        """다중 페이지 응답 (연속 조회 필요)"""
        # Given
        config = HantuConfig()
        api = HantuDomesticAPI(config, AccountType.VIRTUAL)

        # _get_token mock
        mocker.patch.object(api, "_get_token", return_value="mock_token")

        # 첫 번째 페이지 응답
        first_response = mocker.Mock()
        first_response.status_code = 200
        first_response.headers = {"tr_cont": "M"}  # 다음 페이지 존재
        first_response.json.return_value = {
            "rt_cd": "0",
            "msg_cd": "MCA00000",
            "msg1": "정상처리 되었습니다.",
            "ctx_area_fk100": "CTX_FK_001",
            "ctx_area_nk100": "CTX_NK_001",
            "output1": [
                {
                    "pdno": "005930",
                    "prdt_name": "삼성전자",
                    "trad_dvsn_name": "현금",
                    "bfdy_buy_qty": "0",
                    "bfdy_sll_qty": "0",
                    "thdt_buyqty": "10",
                    "thdt_sll_qty": "0",
                    "hldg_qty": "10",
                    "ord_psbl_qty": "10",
                    "pchs_avg_pric": "70000.00",
                    "pchs_amt": "700000",
                    "prpr": "71000",
                    "evlu_amt": "710000",
                    "evlu_pfls_amt": "10000",
                    "evlu_pfls_rt": "1.43",
                    "evlu_erng_rt": "1.43",
                    "loan_dt": "",
                    "loan_amt": "0",
                    "stln_slng_chgs": "0",
                    "expd_dt": "",
                    "fltt_rt": "0.00",
                    "bfdy_cprs_icdc": "1000",
                    "item_mgna_rt_name": "",
                    "grta_rt_name": "",
                    "sbst_pric": "0",
                    "stck_loan_unpr": "0",
                }
            ],
            "output2": [],
        }

        # 두 번째 페이지 응답
        second_response = mocker.Mock()
        second_response.status_code = 200
        second_response.headers = {"tr_cont": "D"}  # 마지막 페이지
        second_response.json.return_value = {
            "rt_cd": "0",
            "msg_cd": "MCA00000",
            "msg1": "정상처리 되었습니다.",
            "ctx_area_fk100": "",
            "ctx_area_nk100": "",
            "output1": [
                {
                    "pdno": "035720",
                    "prdt_name": "카카오",
                    "trad_dvsn_name": "현금",
                    "bfdy_buy_qty": "0",
                    "bfdy_sll_qty": "0",
                    "thdt_buyqty": "5",
                    "thdt_sll_qty": "0",
                    "hldg_qty": "5",
                    "ord_psbl_qty": "5",
                    "pchs_avg_pric": "50000.00",
                    "pchs_amt": "250000",
                    "prpr": "52000",
                    "evlu_amt": "260000",
                    "evlu_pfls_amt": "10000",
                    "evlu_pfls_rt": "4.00",
                    "evlu_erng_rt": "4.00",
                    "loan_dt": "",
                    "loan_amt": "0",
                    "stln_slng_chgs": "0",
                    "expd_dt": "",
                    "fltt_rt": "0.00",
                    "bfdy_cprs_icdc": "2000",
                    "item_mgna_rt_name": "",
                    "grta_rt_name": "",
                    "sbst_pric": "0",
                    "stck_loan_unpr": "0",
                }
            ],
            "output2": [
                {
                    "dnca_tot_amt": "1000000",
                    "nxdy_excc_amt": "0",
                    "prvs_rcdl_excc_amt": "0",
                    "cma_evlu_amt": "0",
                    "bfdy_buy_amt": "0",
                    "thdt_buy_amt": "950000",
                    "nxdy_auto_rdpt_amt": "0",
                    "bfdy_sll_amt": "0",
                    "thdt_sll_amt": "0",
                    "d2_auto_rdpt_amt": "0",
                    "bfdy_tlex_amt": "0",
                    "thdt_tlex_amt": "0",
                    "tot_loan_amt": "0",
                    "scts_evlu_amt": "970000",
                    "tot_evlu_amt": "1970000",
                    "nass_amt": "1970000",
                    "fncg_gld_auto_rdpt_yn": "N",
                    "pchs_amt_smtl_amt": "950000",
                    "evlu_amt_smtl_amt": "970000",
                    "evlu_pfls_smtl_amt": "20000",
                    "tot_stln_slng_chgs": "0",
                    "bfdy_tot_asst_evlu_amt": "1950000",
                    "asst_icdc_amt": "20000",
                    "asst_icdc_erng_rt": "1.03",
                }
            ],
        }

        mock_get = mocker.patch("requests.get")
        mock_get.side_effect = [first_response, second_response]

        # When
        result = api.get_balance()

        # Then
        assert len(result.output1) == 2
        assert result.output1[0].pdno == "005930"
        assert result.output1[0].prdt_name == "삼성전자"
        assert result.output1[1].pdno == "035720"
        assert result.output1[1].prdt_name == "카카오"

        # output2는 마지막 페이지의 값 사용
        assert len(result.output2) == 1
        assert result.output2[0].tot_evlu_amt == "1970000"
        assert result.output2[0].nass_amt == "1970000"

        # 두 번째 호출 시 연속 조회 키가 전달되었는지 확인
        assert mock_get.call_count == 2
        second_call_params = mock_get.call_args_list[1][1]["params"]
        assert second_call_params["CTX_AREA_FK100"] == "CTX_FK_001"
        assert second_call_params["CTX_AREA_NK100"] == "CTX_NK_001"

    def test_get_balance_error(self, mocker):
        """API 에러 응답"""
        # Given
        config = HantuConfig()
        api = HantuDomesticAPI(config, AccountType.VIRTUAL)

        # _get_token mock
        mocker.patch.object(api, "_get_token", return_value="mock_token")

        mock_response = mocker.Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"

        mocker.patch("requests.get", return_value=mock_response)

        # When & Then
        import pytest

        with pytest.raises(Exception):
            api.get_balance()
