"""DART 주식소각결정 공시 원문 파싱(_parse_cancellation_document) 테스트."""

from datetime import date

from src.providers.dart_company_client import _parse_cancellation_document

# 삼성전자 rcept_no=20250218800029 주식소각결정 소각표 구간 실측 raw HTML.
_SAMSUNG_DOC = (
    '<td width="165"> <span style="width:165px;font-size:10pt;">1. 소각할 주식의 종류와 수</span> </td> \r\n '
    '<td width="106"> <span style="width:106px;font-size:10pt;">보통주식 (주)</span> </td> \r\n '
    '<td colspan="2" width="329"> <span class="xforms_input" style="width:329px;font-size:10pt;text-align:right;">50,144,628</span> </td> </tr> <tr> '
    '<td width="106"> <span style="width:106px;font-size:10pt;">종류주식 (주)</span> </td> '
    '<td colspan="2" width="329"> <span class="xforms_input" style="width:329px;font-size:10pt;text-align:right;">6,912,036</span> </td> </tr> <tr> '
    '<td rowspan="2" width="165"> <span style="width:165px;font-size:10pt;">2. 발행주식 총수</span> </td> '
    '<td width="106"> <span>보통주식 (주)</span> </td> '
    '<td colspan="2"> <span class="xforms_input" style="text-align:right;">5,969,782,550</span> </td> </tr> <tr> '
    '<td><span>종류주식 (주)</span></td> <td colspan="2"><span class="xforms_input">822,886,700</span></td> </tr> <tr> '
    '<td colspan="2"><span>3. 1주당 가액(원)</span></td> <td colspan="2"><span class="xforms_input" style="text-align:right;">100</span></td> </tr> <tr> '
    '<td colspan="2"><span>4. 소각예정금액(원)</span></td> <td colspan="2"><span class="xforms_input" style="text-align:right;">3,048,696,999,300</span></td> </tr> <tr> '
    '<td rowspan="2"><span>5. 소각을 위한 자기주식 취득 예정기간</span></td> <td><span>시작일</span></td> <td colspan="2"><span class="xforms_input">-</span></td> </tr> <tr> '
    '<td><span>종료일</span></td> <td colspan="2"><span class="xforms_input">-</span></td> </tr> <tr> '
    '<td colspan="2"><span>6. 소각할 주식의 취득방법</span></td> <td colspan="2"><span class="xforms_input">기취득 자기주식</span></td> </tr> <tr> '
    '<td colspan="2"><span>7. 소각 예정일</span></td> <td colspan="2"><span class="xforms_input">2025-02-20</span></td> </tr> <tr> '
    '<td colspan="2"><span>8. 자기주식 취득 위탁 투자중개업자</span></td> <td colspan="2"><span class="xforms_input">-</span></td> </tr> <tr> '
    '<td colspan="2"><span>9. 이사회결의일(결정일)</span></td> <td colspan="2"><span class="xforms_input">2025-02-18</span></td> </tr>'
)


def test_parse_samsung_cancellation_document() -> None:
    """실측 HTML에서 소각 수량·금액·예정일·결의일·취득방법을 정확히 추출."""
    result = _parse_cancellation_document(_SAMSUNG_DOC)

    assert result is not None
    assert result["common_shares"] == 50_144_628
    assert result["preferred_shares"] == 6_912_036
    assert result["cancel_amount"] == 3_048_696_999_300
    assert result["cancel_date"] == date(2025, 2, 20)
    assert result["resolution_date"] == date(2025, 2, 18)
    assert result["acquisition_method"] == "기취득 자기주식"


def test_parse_returns_none_when_resolution_date_missing() -> None:
    """필수필드(이사회결의일) 누락 시 None 반환."""
    doc = (
        '<td><span>4. 소각예정금액(원)</span></td> <td><span class="xforms_input">1,000,000</span></td>'
    )
    assert _parse_cancellation_document(doc) is None
