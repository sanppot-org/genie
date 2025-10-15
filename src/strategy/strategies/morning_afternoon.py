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
