"""KSIC 매핑 단위 테스트."""

from src.common.ksic import KSIC_CODES, industry_name_of


def test_industry_name_of_returns_mapped_name_for_known_code() -> None:
    known_code = next(iter(KSIC_CODES))
    assert industry_name_of(known_code) == KSIC_CODES[known_code]


def test_industry_name_of_returns_none_for_unknown_code() -> None:
    assert industry_name_of("99999") is None


def test_industry_name_of_passes_through_none() -> None:
    assert industry_name_of(None) is None
