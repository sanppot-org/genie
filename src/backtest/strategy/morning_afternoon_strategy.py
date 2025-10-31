from typing import Any

import backtrader as bt


class MorningAfternoonStrategy(bt.Strategy):
    """오전/오후 거래량 및 수익률 기반 전략

    매수 조건 (당일 오전 첫 봉):
    - 현재 시간이 오전 (0~11시)
    - 전일 오후 수익률 > 0
    - 전일 오전 거래량 < 전일 오후 거래량

    매도 조건:
    - 오전 마지막 봉(11시) 종가에 전량 매도
    """

    def __init__(self) -> None:
        """전략 초기화"""
        # 전일 데이터
        self.prev_day_morning_volume = 0.0
        self.prev_day_afternoon_volume = 0.0
        self.prev_day_afternoon_return = 0.0

        # 당일 데이터 누적
        self.current_date: Any = None
        self.current_morning_volume = 0.0
        self.current_afternoon_volume = 0.0
        self.morning_open = 0.0
        self.afternoon_open = 0.0
        self.afternoon_close = 0.0

        # 오전 첫 봉 추적
        self.is_first_morning_bar = False

        # 주문 추적
        self.order: Any = None

        # 테스트용 플래그
        self.buy_executed = False
        self.sell_executed = False

    def notify_order(self, order: Any) -> None:
        """주문 상태 변경 알림"""
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                self.buy_executed = True
                self.log(f"BUY EXECUTED, Price: {order.executed.price:.2f}")
            elif order.issell():
                self.sell_executed = True
                self.log(f"SELL EXECUTED, Price: {order.executed.price:.2f}")

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log("Order Canceled/Margin/Rejected")

        self.order = None

    def next(self) -> None:
        """매 봉마다 실행되는 전략 로직"""
        current_dt = self.datas[0].datetime.datetime(0)
        current_hour = current_dt.hour
        current_date = current_dt.date()

        # 날짜 변경 감지 → 전일 데이터 저장
        if self.current_date is not None and current_date != self.current_date:
            self._save_previous_day_data()

        # 날짜 초기화
        if self.current_date != current_date:
            self.current_date = current_date
            self.current_morning_volume = 0.0
            self.current_afternoon_volume = 0.0
            self.morning_open = 0.0
            self.afternoon_open = 0.0
            self.afternoon_close = 0.0
            self.is_first_morning_bar = True

        # 오전 봉 (0~11시)
        if 0 <= current_hour <= 11:
            self._process_morning_bar(current_hour)

        # 오후 봉 (12~23시)
        else:
            self._process_afternoon_bar()

    def _save_previous_day_data(self) -> None:
        """전일 데이터 저장"""
        self.prev_day_morning_volume = self.current_morning_volume
        self.prev_day_afternoon_volume = self.current_afternoon_volume

        # 오후 수익률 계산
        if self.afternoon_open > 0:
            self.prev_day_afternoon_return = (
                (self.afternoon_close - self.afternoon_open) / self.afternoon_open * 100
            )
        else:
            self.prev_day_afternoon_return = 0.0

        self.log(
            f"Previous day saved - Morning Vol: {self.prev_day_morning_volume:.0f}, "
            f"Afternoon Vol: {self.prev_day_afternoon_volume:.0f}, "
            f"Afternoon Return: {self.prev_day_afternoon_return:.2f}%"
        )

    def _process_morning_bar(self, current_hour: int) -> None:
        """오전 봉 처리"""
        # 오전 첫 봉: 매수 조건 체크
        if self.is_first_morning_bar:
            self.morning_open = self.datas[0].open[0]
            self.is_first_morning_bar = False

            if self._check_buy_conditions():
                self.log(f"BUY CREATE, {self.datas[0].open[0]:.2f}")
                self.order = self.buy()

        # 거래량 누적
        self.current_morning_volume += self.datas[0].volume[0]

        # 오전 마지막 봉 (11시): 매도
        if current_hour == 11 and self.position:
            self.log(f"SELL CREATE, {self.datas[0].close[0]:.2f}")
            self.order = self.sell()

    def _process_afternoon_bar(self) -> None:
        """오후 봉 처리"""
        # 오후 첫 봉: 시가 기록
        if self.afternoon_open == 0.0:
            self.afternoon_open = self.datas[0].open[0]

        # 거래량 누적
        self.current_afternoon_volume += self.datas[0].volume[0]

        # 오후 종가 업데이트
        self.afternoon_close = self.datas[0].close[0]

    def _check_buy_conditions(self) -> bool:
        """매수 조건 확인"""
        # 주문 대기 중이면 스킵
        if self.order:
            return False

        # 이미 포지션 보유 중이면 스킵
        if self.position:
            return False

        # 전일 데이터가 없으면 스킵
        if self.prev_day_morning_volume == 0.0:
            return False

        # 조건 1: 전일 오후 수익률 > 0
        if self.prev_day_afternoon_return <= 0:
            return False

        # 조건 2: 전일 오전 거래량 < 전일 오후 거래량
        if self.prev_day_morning_volume >= self.prev_day_afternoon_volume:
            return False

        return True

    def log(self, txt: str, dt: Any = None) -> None:
        """로깅 함수"""
        dt = dt or self.datas[0].datetime.datetime(0)
        print(f"{dt.isoformat()}, {txt}")
