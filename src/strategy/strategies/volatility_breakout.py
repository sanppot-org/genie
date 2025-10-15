"""변동성 돌파 전략

오전 시간대에 현재가가 일정 수준 이상 상승하면 매수 시그널을 발생시킵니다.
"""

from src.strategy.data.models import Recent20DaysHalfDayCandles


def check_buy_signal(
        history: Recent20DaysHalfDayCandles,
        current_price: float
) -> bool:
    """
    변동성 돌파 매수 시그널 체크

    현재가 > 당일 시가 + (전일 오전 레인지 × 최근 20일 오전 노이즈 평균)
    - 당일 시가는 전일 오후 종가로부터 자동 계산됨

    Args:
        history: 반일봉 데이터 컬렉션 (최소 20일치)
        current_price: 현재가

    Returns:
        매수 시그널 여부 (True: 매수, False: 대기)
    """
    try:
        threshold = _calculate_threshold(history)
        return current_price > threshold

    except (ValueError, IndexError):
        # 데이터 부족이나 기타 에러 시 False 반환
        return False


def _calculate_threshold(history: Recent20DaysHalfDayCandles) -> float:
    """
    변동성 돌파 임계값 계산

    공식: 당일 시가 + (전일 오전 레인지 × 최근 20일 오전 노이즈 평균)
    - 당일 시가 = 전일 오후 종가
    - 전일 오전 레인지 = yesterday_morning.range
    - k값 = calculate_morning_noise_average()

    Args:
        history: 반일봉 데이터 컬렉션

    Returns:
        임계값
    """
    today_open = history.yesterday_afternoon.close
    k = history.calculate_morning_noise_average()

    return today_open + (history.yesterday_morning.range * k)
