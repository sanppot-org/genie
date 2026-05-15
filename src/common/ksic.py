"""KSIC (한국표준산업분류) 코드 → 업종명 매핑.

DART OpenAPI의 `company` endpoint는 `induty_code`(KSIC 10차 개정 코드)만 반환하고
업종명은 주지 않는다. 회사가 자체 신고한 분류 레벨을 그대로 보내므로 코드 길이가
2~5자리로 다양함 (중분류/소분류/세분류/세세분류).

원본 데이터(2000여 entries)는 `_ksic_data.py`에 별도 보관 — 본 모듈은 재내보내기와
헬퍼만 정의한다.
"""

from src.common._ksic_data import KSIC_CODES

__all__ = ["KSIC_CODES", "industry_name_of"]


def industry_name_of(code: str | None) -> str | None:
    """KSIC 코드를 업종명으로 매핑한다. None/미매핑 코드는 None을 반환."""
    if code is None:
        return None
    return KSIC_CODES.get(code)
