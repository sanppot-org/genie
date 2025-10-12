"""한국투자증권 API 주문 테스트"""

import pytest

from src.config import HantuConfig
from src.hantu.hantu_api import HantuAPI
from src.hantu.model import AccountType


class TestSellMarketOrder:
    """시장가 매도 주문 테스트"""

    def test_sell_market_order_virtual_account(self, mocker):
        """가상 계좌로 시장가 매도 주문"""
        # Given
        config = HantuConfig()
        api = HantuAPI(config, AccountType.VIRTUAL)

        # _get_token mock
        mocker.patch.object(api, '_get_token', return_value='mock_token')

        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rt_cd": "0",
            "msg_cd": "MCA00000",
            "msg1": "정상처리 되었습니다.",
            "output": {
                "KRX_FWDG_ORD_ORGNO": "91252",
                "ODNO": "0000117057",
                "ORD_TMD": "121052"
            }
        }

        mock_post = mocker.patch('requests.post', return_value=mock_response)

        # When
        result = api.sell_market_order(ticker="005930", quantity=10)

        # Then
        assert result.rt_cd == "0"
        assert result.msg_cd == "MCA00000"
        assert result.output.ODNO == "0000117057"

        # POST 호출 확인
        assert mock_post.call_count == 1
        call_kwargs = mock_post.call_args[1]

        # 헤더 검증
        headers = call_kwargs['headers']
        assert headers['tr_id'] == "VTTC0011U"  # 가상 계좌 매도

        # 바디 검증
        import json
        body = json.loads(call_kwargs['data'])
        assert body['PDNO'] == "005930"
        assert body['ORD_DVSN'] == "01"  # 시장가
        assert body['ORD_QTY'] == "10"
        assert body['ORD_UNPR'] == "0"  # 시장가는 0

    def test_sell_market_order_real_account(self, mocker):
        """실제 계좌로 시장가 매도 주문"""
        # Given
        config = HantuConfig()
        api = HantuAPI(config, AccountType.REAL)

        # _get_token mock
        mocker.patch.object(api, '_get_token', return_value='mock_token')

        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rt_cd": "0",
            "msg_cd": "MCA00000",
            "msg1": "정상처리 되었습니다.",
            "output": {
                "KRX_FWDG_ORD_ORGNO": "91252",
                "ODNO": "0000117057",
                "ORD_TMD": "121052"
            }
        }

        mock_post = mocker.patch('requests.post', return_value=mock_response)

        # When
        result = api.sell_market_order(ticker="005930", quantity=10)

        # Then
        assert result.rt_cd == "0"

        # 헤더 검증 - 실제 계좌는 TTTC0011U
        headers = mock_post.call_args[1]['headers']
        assert headers['tr_id'] == "TTTC0011U"

    def test_sell_market_order_error(self, mocker):
        """시장가 매도 주문 실패"""
        # Given
        config = HantuConfig()
        api = HantuAPI(config, AccountType.VIRTUAL)

        # _get_token mock
        mocker.patch.object(api, '_get_token', return_value='mock_token')

        mock_response = mocker.Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"

        mocker.patch('requests.post', return_value=mock_response)

        # When & Then
        with pytest.raises(Exception) as exc_info:
            api.sell_market_order(ticker="005930", quantity=10)

        assert "주식 주문 실패" in str(exc_info.value)

    def test_sell_market_order_with_error_response_code(self, mocker):
        """응답 코드가 실패인 경우"""
        # Given
        config = HantuConfig()
        api = HantuAPI(config, AccountType.VIRTUAL)

        # _get_token mock
        mocker.patch.object(api, '_get_token', return_value='mock_token')

        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rt_cd": "1",
            "msg_cd": "EGW00123",
            "msg1": "주문가능수량을 초과하였습니다.",
            "output": {
                "KRX_FWDG_ORD_ORGNO": "",
                "ODNO": "",
                "ORD_TMD": ""
            }
        }

        mocker.patch('requests.post', return_value=mock_response)

        # When & Then
        with pytest.raises(Exception) as exc_info:
            api.sell_market_order(ticker="005930", quantity=10)

        assert "주문 실패" in str(exc_info.value)


class TestSellLimitOrder:
    """지정가 매도 주문 테스트"""

    def test_sell_limit_order_virtual_account(self, mocker):
        """가상 계좌로 지정가 매도 주문"""
        # Given
        config = HantuConfig()
        api = HantuAPI(config, AccountType.VIRTUAL)

        mocker.patch.object(api, '_get_token', return_value='mock_token')

        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rt_cd": "0",
            "msg_cd": "MCA00000",
            "msg1": "정상처리 되었습니다.",
            "output": {
                "KRX_FWDG_ORD_ORGNO": "91252",
                "ODNO": "0000117058",
                "ORD_TMD": "121053"
            }
        }

        mock_post = mocker.patch('requests.post', return_value=mock_response)

        # When
        result = api.sell_limit_order(ticker="005930", quantity=10, price=70000)

        # Then
        assert result.rt_cd == "0"
        assert result.output.ODNO == "0000117058"

        # 헤더 검증
        headers = mock_post.call_args[1]['headers']
        assert headers['tr_id'] == "VTTC0011U"

        # 바디 검증
        import json
        body = json.loads(mock_post.call_args[1]['data'])
        assert body['PDNO'] == "005930"
        assert body['ORD_DVSN'] == "00"  # 지정가
        assert body['ORD_QTY'] == "10"
        assert body['ORD_UNPR'] == "70000"

    def test_sell_limit_order_real_account(self, mocker):
        """실제 계좌로 지정가 매도 주문"""
        # Given
        config = HantuConfig()
        api = HantuAPI(config, AccountType.REAL)

        mocker.patch.object(api, '_get_token', return_value='mock_token')

        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rt_cd": "0",
            "msg_cd": "MCA00000",
            "msg1": "정상처리 되었습니다.",
            "output": {
                "KRX_FWDG_ORD_ORGNO": "91252",
                "ODNO": "0000117058",
                "ORD_TMD": "121053"
            }
        }

        mock_post = mocker.patch('requests.post', return_value=mock_response)

        # When
        result = api.sell_limit_order(ticker="005930", quantity=10, price=70000)

        # Then
        assert result.rt_cd == "0"

        # 실제 계좌는 TTTC0011U
        headers = mock_post.call_args[1]['headers']
        assert headers['tr_id'] == "TTTC0011U"


class TestBuyMarketOrder:
    """시장가 매수 주문 테스트"""

    def test_buy_market_order_virtual_account(self, mocker):
        """가상 계좌로 시장가 매수 주문"""
        # Given
        config = HantuConfig()
        api = HantuAPI(config, AccountType.VIRTUAL)

        mocker.patch.object(api, '_get_token', return_value='mock_token')

        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rt_cd": "0",
            "msg_cd": "MCA00000",
            "msg1": "정상처리 되었습니다.",
            "output": {
                "KRX_FWDG_ORD_ORGNO": "91252",
                "ODNO": "0000117059",
                "ORD_TMD": "121054"
            }
        }

        mock_post = mocker.patch('requests.post', return_value=mock_response)

        # When
        result = api.buy_market_order(ticker="005930", price=100000)

        # Then
        assert result.rt_cd == "0"
        assert result.output.ODNO == "0000117059"

        # 헤더 검증
        headers = mock_post.call_args[1]['headers']
        assert headers['tr_id'] == "VTTC0012U"  # 가상 계좌 매수

        # 바디 검증
        import json
        body = json.loads(mock_post.call_args[1]['data'])
        assert body['PDNO'] == "005930"
        assert body['ORD_DVSN'] == "01"  # 시장가
        assert body['ORD_QTY'] == "100000"  # 시장가 매수는 매수 금액
        assert body['ORD_UNPR'] == "0"  # 시장가는 0

    def test_buy_market_order_real_account(self, mocker):
        """실제 계좌로 시장가 매수 주문"""
        # Given
        config = HantuConfig()
        api = HantuAPI(config, AccountType.REAL)

        mocker.patch.object(api, '_get_token', return_value='mock_token')

        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rt_cd": "0",
            "msg_cd": "MCA00000",
            "msg1": "정상처리 되었습니다.",
            "output": {
                "KRX_FWDG_ORD_ORGNO": "91252",
                "ODNO": "0000117059",
                "ORD_TMD": "121054"
            }
        }

        mock_post = mocker.patch('requests.post', return_value=mock_response)

        # When
        result = api.buy_market_order(ticker="005930", price=100000)

        # Then
        assert result.rt_cd == "0"

        # 실제 계좌는 TTTC0012U
        headers = mock_post.call_args[1]['headers']
        assert headers['tr_id'] == "TTTC0012U"

        # 바디 검증
        import json
        body = json.loads(mock_post.call_args[1]['data'])
        assert body['ORD_QTY'] == "100000"  # 시장가 매수는 매수 금액


class TestBuyLimitOrder:
    """지정가 매수 주문 테스트"""

    def test_buy_limit_order_virtual_account(self, mocker):
        """가상 계좌로 지정가 매수 주문"""
        # Given
        config = HantuConfig()
        api = HantuAPI(config, AccountType.VIRTUAL)

        mocker.patch.object(api, '_get_token', return_value='mock_token')

        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rt_cd": "0",
            "msg_cd": "MCA00000",
            "msg1": "정상처리 되었습니다.",
            "output": {
                "KRX_FWDG_ORD_ORGNO": "91252",
                "ODNO": "0000117060",
                "ORD_TMD": "121055"
            }
        }

        mock_post = mocker.patch('requests.post', return_value=mock_response)

        # When
        result = api.buy_limit_order(ticker="005930", quantity=10, price=70000)

        # Then
        assert result.rt_cd == "0"
        assert result.output.ODNO == "0000117060"

        # 헤더 검증
        headers = mock_post.call_args[1]['headers']
        assert headers['tr_id'] == "VTTC0012U"

        # 바디 검증
        import json
        body = json.loads(mock_post.call_args[1]['data'])
        assert body['PDNO'] == "005930"
        assert body['ORD_DVSN'] == "00"  # 지정가
        assert body['ORD_QTY'] == "10"
        assert body['ORD_UNPR'] == "70000"

    def test_buy_limit_order_real_account(self, mocker):
        """실제 계좌로 지정가 매수 주문"""
        # Given
        config = HantuConfig()
        api = HantuAPI(config, AccountType.REAL)

        mocker.patch.object(api, '_get_token', return_value='mock_token')

        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rt_cd": "0",
            "msg_cd": "MCA00000",
            "msg1": "정상처리 되었습니다.",
            "output": {
                "KRX_FWDG_ORD_ORGNO": "91252",
                "ODNO": "0000117060",
                "ORD_TMD": "121055"
            }
        }

        mock_post = mocker.patch('requests.post', return_value=mock_response)

        # When
        result = api.buy_limit_order(ticker="005930", quantity=10, price=70000)

        # Then
        assert result.rt_cd == "0"

        # 실제 계좌는 TTTC0012U
        headers = mock_post.call_args[1]['headers']
        assert headers['tr_id'] == "TTTC0012U"
