"""우선주 식별 및 보통주 코드 도출 유틸리티

KRX 단축코드 채번 규칙:
  6자리 = 1~5자리(발행체 고유코드) + 6번째(종목구분)
  6번째 자리가 '0' → 보통주
  6번째 자리가 '5', '7', '9' → 2013년 이전 우선주
  6번째 자리가 영문자(K, L, M …) → 2013년 이후 우선주
  보통주 코드 = ticker[:5] + '0'  (DB 검증: 우선주 113종 100% 매핑 확인)
"""

from src.constants import AssetType


def is_preferred(ticker_code: str, asset_type: AssetType) -> bool:
    """KR_STOCK 6자리 코드에서 우선주 여부를 반환한다.

    KRX 채번 규칙상 6번째 자리가 '0'이면 보통주, 그 외('5','7','9' 또는 영문자)이면 우선주.
    KR_STOCK이 아니거나 코드가 6자리가 아니면 False를 반환한다.
    """
    if asset_type != AssetType.KR_STOCK:
        return False
    if len(ticker_code) != 6:
        return False
    return ticker_code[5] != "0"


def common_code_of(ticker_code: str, asset_type: AssetType) -> str | None:
    """우선주의 보통주 코드를 반환한다.

    우선주이면 ticker_code[:5] + '0'을 반환하고,
    보통주이거나 KR_STOCK이 아니거나 길이가 6이 아니면 None을 반환한다.
    """
    if not is_preferred(ticker_code, asset_type):
        return None
    return ticker_code[:5] + "0"
