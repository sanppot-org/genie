"""주문 모델 테스트"""

from src.hantu.model.domestic.order import RequestHeader, RequestBody, OrderOutput, ResponseBody


class TestRequestHeader:
    """주문 요청 헤더 테스트"""

    def test_request_header_creation(self):
        """요청 헤더 생성 테스트"""
        # Given & When
        header = RequestHeader(
            authorization="Bearer test_token",
            appkey="test_app_key",
            appsecret="test_app_secret",
            tr_id="VTTC0011U"
        )

        # Then
        assert header.authorization == "Bearer test_token"
        assert header.appkey == "test_app_key"
        assert header.appsecret == "test_app_secret"
        assert header.tr_id == "VTTC0011U"
        assert header.content_type == "application/json; charset=utf-8"

    def test_request_header_with_alias(self):
        """alias를 통한 헤더 생성 테스트"""
        # Given & When
        header = RequestHeader(
            authorization="Bearer test_token",
            appkey="test_app_key",
            appsecret="test_app_secret",
            tr_id="VTTC0011U"
        )

        # Then
        header_dict = header.model_dump(by_alias=True)
        assert "Content-Type" in header_dict
        assert header_dict["Content-Type"] == "application/json; charset=utf-8"


class TestRequestBody:
    """주문 요청 바디 테스트"""

    def test_market_sell_order_body(self):
        """시장가 매도 주문 바디 생성 테스트"""
        # Given & When
        body = RequestBody(
            CANO="12345678",
            ACNT_PRDT_CD="01",
            PDNO="005930",
            ORD_DVSN="01",  # 시장가
            ORD_QTY="10",
            ORD_UNPR="0"  # 시장가는 0
        )

        # Then
        assert body.CANO == "12345678"
        assert body.ACNT_PRDT_CD == "01"
        assert body.PDNO == "005930"
        assert body.ORD_DVSN == "01"
        assert body.ORD_QTY == "10"
        assert body.ORD_UNPR == "0"
        assert body.EXCG_ID_DVSN_CD == "KRX"  # 기본값


class TestOrderOutput:
    """주문 응답 output 테스트"""

    def test_order_output_from_api_response(self):
        """API 응답으로부터 OrderOutput 생성 테스트"""
        # Given
        api_response = {
            "KRX_FWDG_ORD_ORGNO": "91252",
            "ODNO": "0000117057",
            "ORD_TMD": "121052"
        }

        # When
        output = OrderOutput.model_validate(api_response)

        # Then
        assert output.KRX_FWDG_ORD_ORGNO == "91252"
        assert output.ODNO == "0000117057"
        assert output.ORD_TMD == "121052"


class TestResponseBody:
    """주문 응답 전체 테스트"""

    def test_successful_order_response(self):
        """정상 주문 응답 테스트"""
        # Given
        api_response = {
            "rt_cd": "0",
            "msg_cd": "MCA00000",
            "msg1": "정상처리 되었습니다.",
            "output": {
                "KRX_FWDG_ORD_ORGNO": "91252",
                "ODNO": "0000117057",
                "ORD_TMD": "121052"
            }
        }

        # When
        response = ResponseBody.model_validate(api_response)

        # Then
        assert response.rt_cd == "0"
        assert response.msg_cd == "MCA00000"
        assert response.msg1 == "정상처리 되었습니다."
        assert response.output.ODNO == "0000117057"

    def test_failed_order_response(self):
        """실패 주문 응답 테스트"""
        # Given
        api_response = {
            "rt_cd": "1",
            "msg_cd": "EGW00123",
            "msg1": "주문가능수량을 초과하였습니다.",
            "output": {
                "KRX_FWDG_ORD_ORGNO": "",
                "ODNO": "",
                "ORD_TMD": ""
            }
        }

        # When
        response = ResponseBody.model_validate(api_response)

        # Then
        assert response.rt_cd == "1"
        assert response.msg_cd == "EGW00123"
        assert "초과" in response.msg1
