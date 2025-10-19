"""
비트코인 자동매매 시스템 상수 정의 모듈

모든 문자열 상수와 매직 넘버를 중앙에서 관리합니다.
"""
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

# 거래 관련 상수
KRW_BTC = "KRW-BTC"
CURRENCY_KRW = "KRW"

# 캔들 데이터 관련 상수
CANDLE_COUNT_24H = 24
CANDLE_MIN_COUNT = 12  # 최소 캔들 개수 (오전/오후 각 최소 1개)

# 시간대 관련 상수
MORNING_START_HOUR = 0
MORNING_END_HOUR = 12
AFTERNOON_START_HOUR = 12
AFTERNOON_END_HOUR = 24

# 데이터 필드명 상수
FIELD_PRICE = "price"
FIELD_OPEN = "open"
FIELD_CLOSE = "close"
FIELD_HIGH = "high"
FIELD_LOW = "low"
FIELD_VOLUME = "volume"
FIELD_VALUE = "value"

# 거래 결과 메시지
MSG_NO_BUY_SIGNAL = "매수 신호가 없습니다."
MSG_KRW_BALANCE_FAIL = "KRW 잔고 조회에 실패했습니다."
MSG_INSUFFICIENT_FUNDS = "투자 가능한 금액이 부족합니다. (현재: {current:,.0f}원, 최소: {minimum:,.0f}원)"
MSG_BUY_ORDER_FAIL = "매수 주문 실행에 실패했습니다."
MSG_BUY_ORDER_SUCCESS = "매수 주문이 성공적으로 실행되었습니다. (투자금액: {amount:,.0f}원)"
MSG_BUY_ERROR = "매수 실행 중 오류가 발생했습니다: {error}"

MSG_BTC_BALANCE_FAIL = "BTC 잔고 조회에 실패했습니다."
MSG_NO_BTC_TO_SELL = "매도할 BTC가 없습니다."
MSG_SELL_ORDER_FAIL = "매도 주문 실행에 실패했습니다."
MSG_SELL_ORDER_SUCCESS = "매도 주문이 성공적으로 실행되었습니다. (수량: {amount:.6f} BTC)"
MSG_SELL_ERROR = "매도 실행 중 오류가 발생했습니다: {error}"

# 수익률 계산 관련 상수
ESTIMATED_BUY_PRICE_RATIO = 0.95  # 임시 매수가 추정용 (현재가의 95%)
PERCENT_MULTIPLIER = 100
ZERO_BALANCE_THRESHOLD = 0

# 기본값 상수
DEFAULT_INVESTMENT_RATIO = "0.01"
DEFAULT_MIN_INVESTMENT_AMOUNT = "5000"
DEFAULT_LOG_LEVEL = "INFO"

# 설정 에러 메시지
ERR_INVALID_INVESTMENT_RATIO = "투자 비율이 유효하지 않습니다: {ratio} ({min}~{max} 범위여야 함)"
ERR_INVESTMENT_RATIO_NOT_NUMBER = "투자 비율이 숫자가 아닙니다"
ERR_MIN_AMOUNT_TOO_SMALL = "최소 투자금액이 너무 작습니다: {amount} ({min}원 이상이어야 함)"
ERR_MIN_AMOUNT_NOT_NUMBER = "최소 투자금액이 숫자가 아닙니다"
ERR_INVALID_LOG_LEVEL = "유효하지 않은 로그 레벨: {level} ({valid_levels} 중 하나여야 함)"
ERR_NO_ACCESS_KEY = "업비트 액세스 키가 설정되지 않았습니다"
ERR_NO_SECRET_KEY = "업비트 시크릿 키가 설정되지 않았습니다"

# API 에러 메시지
ERR_UPBIT_API_FORMAT = "업비트 API 오류 in {func_name}: {error}"
ERR_UPBIT_API_KEY_NOT_SET = "업비트 API 키가 설정되지 않았습니다"

# API 기본값 상수
DEFAULT_PRICE = 0.0
DEFAULT_VOLUME = 0.0
DEFAULT_PROFIT_RATE = 0.0
DEFAULT_INVESTMENT_AMOUNT = 0.0

# 인덱스 상수
LAST_INDEX = -1

# 거래 상태 상수
BUY_SIDE = "bid"
SELL_SIDE = "ask"
FIELD_UUID = "uuid"
FIELD_SIDE = "side"
FIELD_MARKET = "market"

UTF_8 = "utf-8"
