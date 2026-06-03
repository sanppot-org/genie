"""우선주 식별/매핑 헬퍼 테스트"""

from src.constants import AssetType
from src.service.preferred_stock import common_code_of, is_preferred

KR_STOCK = AssetType.KR_STOCK
US_STOCK = AssetType.US_STOCK
CRYPTO = AssetType.CRYPTO


# --- is_preferred ---

def test_is_preferred_true_suffix5() -> None:
    assert is_preferred("005935", KR_STOCK) is True


def test_is_preferred_false_common() -> None:
    assert is_preferred("005930", KR_STOCK) is False


def test_is_preferred_true_alpha_suffix() -> None:
    assert is_preferred("00088K", KR_STOCK) is True


def test_is_preferred_false_us_stock() -> None:
    assert is_preferred("AAPL", US_STOCK) is False


def test_is_preferred_false_crypto() -> None:
    assert is_preferred("KRW-BTC", CRYPTO) is False


def test_is_preferred_false_short_code() -> None:
    assert is_preferred("12345", KR_STOCK) is False


def test_is_preferred_false_long_code() -> None:
    assert is_preferred("1234567", KR_STOCK) is False


def test_is_preferred_true_suffix7() -> None:
    assert is_preferred("005387", KR_STOCK) is True


def test_is_preferred_false_kr_etf() -> None:
    assert is_preferred("069500", AssetType.KR_ETF) is False


# --- common_code_of ---

def test_common_code_of_suffix5() -> None:
    assert common_code_of("005935", KR_STOCK) == "005930"


def test_common_code_of_alpha_suffix() -> None:
    assert common_code_of("00088K", KR_STOCK) == "000880"


def test_common_code_of_suffix5_another() -> None:
    assert common_code_of("005385", KR_STOCK) == "005380"


def test_common_code_of_none_for_common() -> None:
    assert common_code_of("005930", KR_STOCK) is None


def test_common_code_of_none_for_us_stock() -> None:
    assert common_code_of("AAPL", US_STOCK) is None


def test_common_code_of_none_for_short_code() -> None:
    assert common_code_of("12345", KR_STOCK) is None


def test_common_code_of_suffix7() -> None:
    assert common_code_of("005387", KR_STOCK) == "005380"


def test_common_code_of_none_for_kr_etf() -> None:
    assert common_code_of("069500", AssetType.KR_ETF) is None
