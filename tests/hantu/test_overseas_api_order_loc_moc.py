"""HantuOverseasAPI LOC/MOC 주문 메서드 테스트 (requests mock)."""

import json

from src.config import HantuConfig
from src.hantu.model.domestic.account_type import AccountType
from src.hantu.model.overseas.exchange_code import OverseasExchangeCode
from src.hantu.overseas_api import HantuOverseasAPI


def _order_response(mocker):
    res = mocker.Mock()
    res.status_code = 200
    res.json.return_value = {
        "rt_cd": "0", "msg_cd": "MCA00000", "msg1": "정상처리 되었습니다.",
        "output": {"KRX_FWDG_ORD_ORGNO": "01790", "ODNO": "0030000123", "ORD_TMD": "092000"},
    }
    return res


def _sent_body(post_mock) -> dict:
    """_order는 requests.post(..., data=body.model_dump_json())로 전송 → JSON 파싱."""
    return json.loads(post_mock.call_args.kwargs["data"])


def _sent_tr_id(post_mock) -> str:
    return post_mock.call_args.kwargs["headers"]["tr_id"]


def test_buy_loc_order_sends_loc_division_and_us_buy_tr_id(mocker):
    api = HantuOverseasAPI(HantuConfig(), AccountType.REAL)
    mocker.patch.object(api, "_get_token", return_value="tok")
    post = mocker.patch("requests.post", return_value=_order_response(mocker))

    out = api.buy_loc_order("TQQQ", 4, "50.00", OverseasExchangeCode.NASD)

    assert out.output.ODNO == "0030000123"
    body = _sent_body(post)
    assert body["ORD_DVSN"] == "34"          # LOC
    assert body["SLL_TYPE"] == ""            # 매수
    assert body["PDNO"] == "TQQQ"
    assert body["ORD_QTY"] == "4"
    assert body["OVRS_ORD_UNPR"] == "50.00"
    assert _sent_tr_id(post) == "TTTT1002U"  # 미국 실전 매수


def test_sell_loc_order_sends_loc_division_and_us_sell_tr_id(mocker):
    api = HantuOverseasAPI(HantuConfig(), AccountType.REAL)
    mocker.patch.object(api, "_get_token", return_value="tok")
    post = mocker.patch("requests.post", return_value=_order_response(mocker))

    api.sell_loc_order("SOXL", 3, "20.50", OverseasExchangeCode.NASD)

    body = _sent_body(post)
    assert body["ORD_DVSN"] == "34"          # LOC
    assert body["SLL_TYPE"] == "00"          # 매도
    assert body["OVRS_ORD_UNPR"] == "20.50"
    assert _sent_tr_id(post) == "TTTT1006U"  # 미국 실전 매도


def test_sell_moc_order_sends_moc_division_zero_price(mocker):
    api = HantuOverseasAPI(HantuConfig(), AccountType.REAL)
    mocker.patch.object(api, "_get_token", return_value="tok")
    post = mocker.patch("requests.post", return_value=_order_response(mocker))

    api.sell_moc_order("TQQQ", 10, OverseasExchangeCode.NASD)

    body = _sent_body(post)
    assert body["ORD_DVSN"] == "33"          # MOC (장마감시장가)
    assert body["SLL_TYPE"] == "00"          # 매도
    assert body["OVRS_ORD_UNPR"] == "0"      # 시장가 → 0
    assert _sent_tr_id(post) == "TTTT1006U"
