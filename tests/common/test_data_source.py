"""DataSource enum 테스트."""

from src.common.data_adapter import DataSource
from src.constants import TimeZone


def test_fdr_source_value_and_timezone() -> None:
    assert DataSource.FDR.value == "fdr"
    assert DataSource.FDR.timezone == TimeZone.NEW_YORK
    # 문자열 호환 (DB 저장값 기준 멤버 조회)
    assert DataSource("fdr") is DataSource.FDR
