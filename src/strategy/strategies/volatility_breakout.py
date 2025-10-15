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


def calculate_position_size(
        history: Recent20DaysHalfDayCandles,
        target_vol: float
) -> float:
    """
    변동성 돌파 매수 비중 계산

    공식: (타겟 변동성 / 전일 오전 변동성) × 이평선 스코어
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

        # 이평선 스코어 계산
        ma_score = history.calculate_ma_score()

        # 비중 계산
        position_size = (target_vol / yesterday_volatility) * ma_score

        # 0 이하이면 0, 1 초과이면 1로 제한
        if position_size <= 0:
            return 0.0
        if position_size > 1.0:
            return 1.0

        return position_size

    except (ValueError, IndexError, ZeroDivisionError):
        # 데이터 부족이나 기타 에러 시 0 반환
        return 0.0


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
