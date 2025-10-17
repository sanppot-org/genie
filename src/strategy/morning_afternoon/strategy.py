"""오전오후 전략

오전오후 전략의 모든 비즈니스 로직을 담당합니다.
"""

import logging

from apscheduler.schedulers.blocking import BlockingScheduler

from src.strategy.base import BaseStrategy
from src.strategy.clock import Clock
from src.strategy.config import MorningAfternoonConfig
from src.strategy.data.collector import DataCollector
from src.upbit.upbit_api import UpbitAPI

logger = logging.getLogger(__name__)


class MorningAfternoonStrategy(BaseStrategy):
    """
    오전오후 전략

    데이터 수집, 시그널 계산, 매수/매도 실행 등 모든 전략 로직을 담당합니다.
    """

    def __init__(
            self,
            upbit: UpbitAPI,
            config: MorningAfternoonConfig,
            clock: Clock,
            scheduler: BlockingScheduler
    ) -> None:
        """
        Args:
            upbit: UpbitAPI 인스턴스
            config: 오전오후 전략 설정
            clock: 시간 관리 객체
            scheduler: APScheduler 인스턴스
        """
        self.upbit = upbit
        self.config = config
        self.clock = clock
        self.collector = DataCollector(self.clock)
        self.scheduler = scheduler

    def try_buy(self) -> None:
        """
        매수 시도

        모든 매수 조건을 내부에서 체크하고 조건이 만족되면 매수를 실행합니다.
        """
        try:
            if self.should_buy():
                position_size = self._calculate_position_size()
                self.execute_buy(position_size)

        except Exception:
            logger.exception("[오전오후] 매수 시도 실패")

    def should_buy(self) -> bool:
        """
        매수 조건 확인

        Returns:
            매수 가능 여부
        """
        # 1. 시간 체크 - 오전이 아니면 매수 안함
        if not self.clock.is_morning():
            logger.debug("[오전오후] 오전 시간대가 아님")
            return False

        # 2. TODO: 이미 보유 중인지 체크 ()

        # 3. 시그널 체크
        return self._check_buy_signal()

    def _check_buy_signal(self) -> bool:
        """
        오전오후 매수 시그널 체크

        조건:
        1. 현재 시간이 오전(00:00~12:00 KST)
        2. 전일 오후 수익률 > 0
        3. 전일 오전 거래량 < 전일 오후 거래량

        Returns:
            매수 시그널 여부 (True: 매수, False: 대기)
        """
        try:
            # 데이터 수집 (캐시에서 가져옴)
            history = self.collector.collect_data(self.config.ticker, days=20)

            # 전일 오전/오후 캔들
            yesterday_morning = history.yesterday_morning
            yesterday_afternoon = history.yesterday_afternoon

            afternoon_return = yesterday_afternoon.return_rate

            # 조건 1: 현재 오전
            # 조건 2: 전일 오후 수익률 > 0
            # 조건 3: 전일 오전 거래량 < 전일 오후 거래량
            return (self.clock.is_morning()
                    and afternoon_return > 0
                    and yesterday_morning.volume < yesterday_afternoon.volume)

        except (ValueError, IndexError):
            # 데이터 부족이나 기타 에러 시 False 반환
            return False

    # TODO: 공통 로직으로 빼기
    def execute_buy(self, position_size: float) -> None:
        """
        매수 주문 실행

        매수 비중을 계산하여 매수 주문을 실행합니다.
        """
        try:
            if position_size <= 0:
                logger.debug(f"매수 비중 0 이하: {position_size}")
                return

            # KRW 잔고 조회
            krw_balance = self.upbit.get_available_amount("KRW")

            # 매수 금액 계산: 전체 잔고 * 전략 할당 비율 * 매수 비중
            buy_amount = krw_balance * self.config.allocation_ratio * position_size

            # 최소 주문 금액 체크
            if buy_amount < self.config.min_order_amount:
                logger.info(
                    f"[오전오후] 매수 금액이 최소 주문 금액 미만: "
                    f"{buy_amount:.0f}원 < {self.config.min_order_amount:.0f}원"
                )
                return

            # 매수 주문
            logger.info(
                f"[오전오후] 매수 시작: "
                f"잔고={krw_balance:.0f}원, "
                f"비중={position_size:.2%}, "
                f"매수금액={buy_amount:.0f}원"
            )

            result = self.upbit.buy_market_order(self.config.ticker, buy_amount)

            logger.info(f"[오전오후] 매수 완료: {result}")

        except Exception:
            logger.exception("[오전오후] 매수 실패")

    def _calculate_position_size(self) -> float:
        """
        오전오후 매수 비중 계산

        공식: 타겟 변동성 / 전일 오전 변동성
        - 결과값: 0.0 ~ 1.0

        Returns:
            매수 비중 (0.0 ~ 1.0)
        """
        try:
            # 데이터 수집 (캐시에서 가져옴)
            history = self.collector.collect_data(self.config.ticker, days=20)

            # 전일 오전 변동성
            yesterday_volatility = history.yesterday_morning.volatility

            # 변동성 < 0.1%이면 0 반환
            if yesterday_volatility < 0.001:
                return 0.0

            # 비중 계산
            position_size = self.config.target_vol / yesterday_volatility

            # 0 이하이면 0, 1 초과이면 1로 제한
            if position_size <= 0:
                return 0.0
            if position_size > 1.0:
                return 1.0

            return position_size

        except (ValueError, IndexError, ZeroDivisionError):
            # 데이터 부족이나 기타 에러 시 0 반환
            return 0.0

    def try_sell(self) -> None:
        """
        매도 시도

        보유 중인 코인이 있으면 전량 매도를 실행합니다.
        """
        try:
            if self.should_sell():
                self.execute_sell()

        except Exception:
            logger.exception("[오전오후] 매도 실패")

    def should_sell(self) -> bool:
        """
        매도 조건 확인

        Returns:
            매도 가능 여부
        """
        # 1. 시간 체크 - 오후가 아니면 매도 안함
        if not self.clock.is_afternoon():
            logger.debug("[오전오후] 오후 시간대가 아님")
            return False

        # 2. 보유 중인지 체크
        volume = self.upbit.get_available_amount(self.config.ticker)

        if volume <= 0:
            logger.debug(f"[오전오후] 보유 수량 없음: {self.config.ticker}")
            return False

        return True

    def execute_sell(self) -> None:
        """
        매도 주문 실행

        보유 수량을 조회하여 전량 매도합니다.
        """
        try:
            # 보유 수량 조회
            volume = self.upbit.get_available_amount(self.config.ticker)

            if volume <= 0:
                logger.debug(f"[오전오후] 보유 수량 없음: {self.config.ticker}")
                return

            # 매도 주문
            logger.info(f"[오전오후] 전량 매도 시작: {volume} {self.config.ticker}")
            result = self.upbit.sell_market_order(self.config.ticker, volume)

            logger.info(f"[오전오후] 매도 완료: {result}")

        except Exception:
            logger.exception("[오전오후] 매도 실패")

    def run(self) -> None:
        """
        오전오후 전략 실행

        APScheduler를 사용하여 다음 스케줄로 작업을 실행합니다:
        - 매일 00:00: 매수 시도
        - 매일 12:00: 매도 시도
        """
        if self.scheduler is None:
            self.scheduler = BlockingScheduler()

        # 매일 00:00에 매수 시도
        self.scheduler.add_job(
            self.try_buy,
            'cron',
            hour=0,
            minute=0,
            id='morning_buy'
        )

        # 매일 12:00에 매도 시도
        self.scheduler.add_job(
            self.try_sell,
            'cron',
            hour=12,
            minute=0,
            id='afternoon_sell'
        )

        logger.info("=" * 60)
        logger.info("[오전오후 전략] 스케줄러 시작")
        logger.info(f"티커: {self.config.ticker}")
        logger.info(f"타겟 변동성: {self.config.target_vol:.2%}")
        logger.info("=" * 60)

        try:
            self.scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("[오전오후 전략] 스케줄러 종료")
