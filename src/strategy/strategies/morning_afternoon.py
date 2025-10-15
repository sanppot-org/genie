"""오전오후 전략

전일 오후에 상승했고 거래량도 오후에 많았다면 당일도 상승 가능성이 높다고 판단합니다.
"""

from src.strategy.data.models import Recent20DaysHalfDayCandles


def check_buy_signal(history: Recent20DaysHalfDayCandles) -> bool:
    """
    오전오후 매수 시그널 체크

    조건:
    1. 전일 오후 수익률 > 0
    2. 전일 오전 거래량 < 전일 오후 거래량

    Args:
        history: 반일봉 데이터 컬렉션 (최소 2일치)

    Returns:
        매수 시그널 여부 (True: 매수, False: 대기)
    """
    try:
        # 전일 오전/오후 캔들
        yesterday_morning = history.yesterday_morning
        yesterday_afternoon = history.yesterday_afternoon

        afternoon_return = yesterday_afternoon.return_rate

        # 조건 1: 전일 오후 수익률 > 0
        # 조건 2: 전일 오전 거래량 < 전일 오후 거래량
        return afternoon_return > 0 and yesterday_morning.volume < yesterday_afternoon.volume

    except (ValueError, IndexError):
        # 데이터 부족이나 기타 에러 시 False 반환
        return False


def calculate_position_size(
        history: Recent20DaysHalfDayCandles,
        target_vol: float
) -> float:
    """
    오전오후 매수 비중 계산

    공식: 타겟 변동성 / 전일 오전 변동성
    - 결과값: 0.0 ~ 1.0

    Args:
        history: 반일봉 데이터 컬렉션 (최소 20일치)
        target_vol: 타겟 변동성 (0.005 ~ 0.02, 즉 0.5% ~ 2%)

    Returns:
        매수 비중 (0.0 ~ 1.0)
    """
    try:
        # 전일 오전 변동성
        yesterday_volatility = history.yesterday_morning.volatility

        # 변동성 < 0.1%이면 0 반환
        if yesterday_volatility < 0.001:
            return 0.0

        # 비중 계산
        position_size = target_vol / yesterday_volatility

        # 0 이하이면 0, 1 초과이면 1로 제한
        if position_size <= 0:
            return 0.0
        if position_size > 1.0:
            return 1.0

        return position_size

    except (ValueError, IndexError, ZeroDivisionError):
        # 데이터 부족이나 기타 에러 시 0 반환
        return 0.0
