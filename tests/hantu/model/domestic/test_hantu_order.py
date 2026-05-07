"""주문 모델 테스트"""

from src.hantu.model.domestic.order import RequestHeader, ResponseBody


class TestRequestHeader:
    """주문 요청 헤더 테스트"""

    def test_request_header_with_alias(self):
        """alias를 통한 헤더 생성 테스트"""
        # Given & When
        header = RequestHeader(authorization="Bearer test_token", appkey="test_app_key", appsecret="test_app_secret", tr_id="VTTC0011U")

        # Then
        header_dict = header.model_dump(by_alias=True)
        assert "Content-Type" in header_dict
        assert header_dict["Content-Type"] == "application/json; charset=utf-8"


class TestResponseBody:
    """주문 응답 전체 테스트"""

    def test_successful_order_response(self):
        """정상 주문 응답 테스트"""
        # Given
        api_response = {
            "rt_cd": "0",
            "msg_cd": "MCA00000",
            "msg1": "정상처리 되었습니다.",
            "output": {"KRX_FWDG_ORD_ORGNO": "91252", "ODNO": "0000117057", "ORD_TMD": "121052"},
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
            "output": {"KRX_FWDG_ORD_ORGNO": "", "ODNO": "", "ORD_TMD": ""},
        }

        # When
        response = ResponseBody.model_validate(api_response)

        # Then
        assert response.rt_cd == "1"
        assert response.msg_cd == "EGW00123"
        assert "초과" in response.msg1
