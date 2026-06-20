"""HantuOverseasAPI 체결조회(inquire-ccnl) 테스트 (requests mock)."""

from src.config import HantuConfig
from src.hantu.model.domestic.account_type import AccountType
from src.hantu.model.overseas.exchange_code import OverseasExchangeCode
from src.hantu.overseas_api import HantuOverseasAPI


def _record(odno: str, pdno: str, ccld_qty: str, nccs_qty: str, sll_buy: str) -> dict:
    return {
        "ord_dt": "20260619", "odno": odno, "pdno": pdno,
        "sll_buy_dvsn_cd": sll_buy, "ft_ord_qty": "4",
        "ft_ccld_qty": ccld_qty, "ft_ccld_unpr3": "50.00", "nccs_qty": nccs_qty,
        "prcs_stat_name": "체결", "ord_tmd": "092000", "ovrs_excg_cd": "NASD",
    }


def _resp(mocker, tr_cont: str, output: list[dict], fk: str = "", nk: str = ""):
    res = mocker.Mock()
    res.status_code = 200
    res.headers = {"tr_cont": tr_cont}
    res.json.return_value = {
        "rt_cd": "0", "msg_cd": "MCA00000", "msg1": "정상처리 되었습니다.",
        "ctx_area_fk200": fk, "ctx_area_nk200": nk, "output": output,
    }
    return res


def test_inquire_ccnl_single_page_parses_records(mocker):
    api = HantuOverseasAPI(HantuConfig(), AccountType.REAL)
    mocker.patch.object(api, "_get_token", return_value="tok")
    res = _resp(mocker, "D", [_record("0030000123", "TQQQ", "4", "0", "02")])
    get = mocker.patch("requests.get", return_value=res)

    records = api.inquire_ccnl("20260619", "20260619", OverseasExchangeCode.NASD)

    assert len(records) == 1
    r = records[0]
    assert r.odno == "0030000123" and r.pdno == "TQQQ"
    assert r.ft_ccld_qty == "4" and r.nccs_qty == "0" and r.sll_buy_dvsn_cd == "02"
    # 실전 TR_ID
    assert get.call_args.kwargs["headers"]["tr_id"] == "TTTS3035R"
    params = get.call_args.kwargs["params"]
    assert params["ORD_STRT_DT"] == "20260619" and params["ORD_END_DT"] == "20260619"
    assert params["OVRS_EXCG_CD"] == "NASD"


def test_inquire_ccnl_follows_continuation(mocker):
    api = HantuOverseasAPI(HantuConfig(), AccountType.REAL)
    mocker.patch.object(api, "_get_token", return_value="tok")
    first = _resp(mocker, "M", [_record("0030000123", "TQQQ", "2", "2", "02")], fk="FK1", nk="NK1")
    second = _resp(mocker, "D", [_record("0030000999", "SOXL", "3", "0", "01")])
    get = mocker.patch("requests.get")
    get.side_effect = [first, second]

    records = api.inquire_ccnl("20260619", "20260619", OverseasExchangeCode.NASD)

    assert [r.odno for r in records] == ["0030000123", "0030000999"]
    assert get.call_count == 2
    second_params = get.call_args_list[1].kwargs["params"]
    assert second_params["CTX_AREA_FK200"] == "FK1"
    assert second_params["CTX_AREA_NK200"] == "NK1"


def test_inquire_ccnl_uses_virtual_tr_id(mocker):
    api = HantuOverseasAPI(HantuConfig(), AccountType.VIRTUAL)
    mocker.patch.object(api, "_get_token", return_value="tok")
    res = _resp(mocker, "D", [])
    get = mocker.patch("requests.get", return_value=res)

    api.inquire_ccnl("20260619", "20260619", OverseasExchangeCode.NASD)

    assert get.call_args.kwargs["headers"]["tr_id"] == "VTTS3035R"
