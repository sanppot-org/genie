"""KisIncomeStatementClient 단위 테스트 — HantuDomesticAPI mock."""

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from src.hantu.domestic_api import HantuDomesticAPI
from src.hantu.model.domestic.income_statement import IncomeStatementOutput, ResponseBody
from src.providers.kis_income_statement_client import (
    PERIOD_ANNUAL,
    KisIncomeStatementClient,
)


def _resp(*outputs: IncomeStatementOutput) -> ResponseBody:
    return ResponseBody(rt_cd="0", msg_cd="MCA00000", msg1="정상처리", output=list(outputs))


def test_fetch_parses_values_units_and_negatives() -> None:
    """정상/적자(음수) 값을 Decimal로 파싱."""
    api = MagicMock(spec=HantuDomesticAPI)
    api.income_statement.return_value = _resp(
        IncomeStatementOutput(
            stac_yymm="202312",
            sale_account="2589355.00",
            bsop_prti="65670.00",
            thtr_ntin="-1062.00",
            sale_cost="1234.00",
            sale_totl_prfi="819132",
            op_prfi="588284.00",
        ),
    )
    client = KisIncomeStatementClient(api)

    rows = client.fetch("005930", PERIOD_ANNUAL)

    assert len(rows) == 1
    r = rows[0]
    assert r.stac_yymm == "202312"
    assert r.period_type == PERIOD_ANNUAL
    assert r.sale_account == Decimal("2589355.00")
    assert r.bsop_prti == Decimal("65670.00")
    assert r.thtr_ntin == Decimal("-1062.00")  # 적자 음수
    assert r.sale_totl_prfi == Decimal("819132")
    api.income_statement.assert_called_once_with("005930", "0")


def test_fetch_normalizes_99_99_sentinel_to_none() -> None:
    """미제공 필드 sentinel '99.99'는 None으로 정규화."""
    api = MagicMock(spec=HantuDomesticAPI)
    api.income_statement.return_value = _resp(
        IncomeStatementOutput(
            stac_yymm="202312",
            sale_account="2589355.00",
            sale_cost="99.99",       # 미제공
            sale_totl_prfi="99.99",  # 미제공
            bsop_prti="65670.00",
            op_prfi="99.99",         # 미제공
            thtr_ntin="154871.00",
        ),
    )
    client = KisIncomeStatementClient(api)

    r = client.fetch("005930", PERIOD_ANNUAL)[0]

    assert r.sale_account == Decimal("2589355.00")
    assert r.sale_cost is None
    assert r.sale_totl_prfi is None
    assert r.op_prfi is None
    assert r.thtr_ntin == Decimal("154871.00")


def test_fetch_skips_rows_without_stac_yymm() -> None:
    api = MagicMock(spec=HantuDomesticAPI)
    api.income_statement.return_value = _resp(
        IncomeStatementOutput(stac_yymm=None, sale_account="100.00"),
        IncomeStatementOutput(stac_yymm="202312", sale_account="200.00"),
    )
    client = KisIncomeStatementClient(api)

    rows = client.fetch("005930", PERIOD_ANNUAL)

    assert [r.stac_yymm for r in rows] == ["202312"]


def test_fetch_propagates_kis_api_error() -> None:
    """KIS rt_cd 비정상/HTTP 오류 → 예외 전파(빈 응답과 구분, sync가 api_calls_failed 집계)."""
    api = MagicMock(spec=HantuDomesticAPI)
    api.income_statement.side_effect = Exception("Error: rt_cd=1")
    client = KisIncomeStatementClient(api)

    with pytest.raises(Exception, match="rt_cd=1"):
        client.fetch("999999", PERIOD_ANNUAL)


def test_fetch_returns_empty_on_valid_empty_response() -> None:
    """정상 응답이지만 output 없음 → 빈 리스트 (오류 아님)."""
    api = MagicMock(spec=HantuDomesticAPI)
    api.income_statement.return_value = _resp()
    client = KisIncomeStatementClient(api)

    assert client.fetch("005930", PERIOD_ANNUAL) == []
