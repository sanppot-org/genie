"""변동성 돌파 전략

변동성 돌파 전략의 모든 비즈니스 로직을 담당합니다.
"""

import logging
from datetime import timedelta

from apscheduler.schedulers.blocking import BlockingScheduler

from src.strategy.base import BaseStrategy
from src.strategy.clock import Clock
from src.strategy.config import VolatilityBreakoutConfig
from src.strategy.data.collector import DataCollector
from src.upbit.upbit_api import UpbitAPI

logger = logging.getLogger(__name__)

BREAKOUT_CHECK_JOB_ID = 'breakout_check'


class VolatilityBreakoutStrategy(BaseStrategy):
    """
    변동성 돌파 전략

    데이터 수집, 시그널 계산, 매수/매도 실행 등 모든 전략 로직을 담당합니다.
    """

    def __init__(
            self,
            upbit: UpbitAPI,
            config: VolatilityBreakoutConfig,
            clock: Clock,
            scheduler: BlockingScheduler
    ) -> None:
        """
        Args:
            upbit: UpbitAPI 인스턴스
            config: 변동성 돌파 전략 설정
            clock: 시간 관리 객체
            scheduler: APScheduler 인스턴스
        """
        self.upbit = upbit
        self.config = config
        self.clock = clock
        self.collector = DataCollector(self.clock)
        self.scheduler = scheduler

        # 매수 상태
        self.bought = False  # TODO: 실제로 매수 상태 확인하기

        self.position_size = 0.0
        self.threshold = 0.0

    def execute_daily_routine(self) -> None:
        """
        일일 루틴 (00:00 실행)

        1. 데이터 수집
        2. 히스토리 저장
        3. 시그널 계산 및 저장
        4. 조건부 breakout_check job 등록
        """
        try:
            logger.info("==" * 30)
            logger.info("[변동성돌파 일일 루틴] 시작")

            self.position_size = self._calculate_position_size()

            if self.position_size <= 0:
                return

            self.threshold = self._calculate_threshold()

            self._remove_breakout_check_job()

            self._register_breakout_check_job()

            logger.info("[변동성돌파 일일 루틴] 완료")
            logger.info("==" * 30)

        except Exception:
            logger.exception("[변동성돌파 일일 루틴] 실패")

    def _calculate_position_size(self) -> float:
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
            history = self.collector.collect_data(self.config.ticker, days=20)

            # 전일 오전 변동성
            yesterday_volatility = history.yesterday_morning.volatility

            # 변동성 < 0.1%이면 0 반환
            if yesterday_volatility < 0.001:
                return 0.0

            # 이평선 스코어 계산
            ma_score = history.calculate_ma_score()

            # 비중 계산
            position_size = (self.config.target_vol / yesterday_volatility) * ma_score

            # 0 이하이면 0, 1 초과이면 1로 제한
            if position_size <= 0:
                return 0.0
            if position_size > 1.0:
                return 1.0

            return position_size

        except (ValueError, IndexError, ZeroDivisionError):
            # 데이터 부족이나 기타 에러 시 0 반환
            return 0.0

    def _calculate_threshold(self) -> float:
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
        history = self.collector.collect_data(self.config.ticker, days=20)
        today_open = history.yesterday_afternoon.close
        k = history.calculate_morning_noise_average()

        return today_open + (history.yesterday_morning.range * k)

    def _register_breakout_check_job(self) -> None:
        """
        변동성 돌파 체크 job 등록

        오늘 00:01부터 11:59까지 1분마다 실행되는 job을 등록합니다.
        기존 job이 있으면 제거 후 재등록합니다.
        """
        now = self.clock.now()
        start_time = now.replace(hour=0, minute=1, second=0, microsecond=0)  # 오늘 00:01
        end_time = now.replace(hour=11, minute=59, second=0, microsecond=0)  # 오늘 11:59

        # 이미 시간이 지났으면 내일로 설정
        if now > end_time:
            start_time += timedelta(days=1)
            end_time += timedelta(days=1)

        self.scheduler.add_job(
            self._check_breakout,
            'interval',
            minutes=1,
            start_date=start_time,
            end_date=end_time,
            id=BREAKOUT_CHECK_JOB_ID
        )

        logger.info(
            f"[변동성돌파] breakout_check job 등록 완료: "
            f"{start_time.strftime('%Y-%m-%d %H:%M')} ~ {end_time.strftime('%Y-%m-%d %H:%M')}"
        )

    def _check_breakout(self) -> None:
        """
        변동성 돌파 체크 (00:01~11:59, 1분마다)

        현재가를 받아 변동성 돌파 조건을 체크합니다.

        Args:
            current_price: 현재가
        """
        try:
            # 이미 매수했으면 스킵
            if self.bought:
                return

            # 현재 시간이 오전이 아니면 스킵
            if not self.clock.is_morning():
                logger.debug("[변동성돌파] 오전 시간대가 아님")
                return

            current_price = UpbitAPI.get_current_price(self.config.ticker)

            # 저장된 threshold로 시그널 체크
            if current_price <= self.threshold:
                logger.debug(f"[변동성돌파] 매수 시그널 없음: {current_price} <= {self.threshold}")
                return

            # 매수 실행
            self._execute_buy(self.position_size)
            self.bought = True

        except Exception:
            logger.exception("[변동성돌파] 체크 실패")

    # TODO: 공통 로직으로 빼기
    def _execute_buy(self, position_size: float) -> None:
        """
        매수 주문 실행

        Args:
            position_size: 매수 비중 (0.0 ~ 1.0)
        """
        try:
            if position_size <= 0:
                logger.info(f"매수 비중 0 이하: {position_size}")
                return

            # KRW 잔고 조회
            krw_balance = self.upbit.get_available_amount("KRW")

            # 매수 금액 계산: 전체 잔고 * 전략 할당 비율 * 매수 비중
            buy_amount = krw_balance * self.config.allocation_ratio * position_size

            # 최소 주문 금액 체크
            if buy_amount < self.config.min_order_amount:
                logger.info(
                    f"[변동성돌파] 매수 금액이 최소 주문 금액 미만: "
                    f"{buy_amount:.0f}원 < {self.config.min_order_amount:.0f}원"
                )
                return

            # 매수 주문
            logger.info(
                f"[변동성돌파] 매수 시작: "
                f"잔고={krw_balance:.0f}원, "
                f"비중={position_size:.2%}, "
                f"매수금액={buy_amount:.0f}원"
            )

            result = self.upbit.buy_market_order(self.config.ticker, buy_amount)

            logger.info(f"[변동성돌파] 매수 완료: {result}")

        except Exception:
            logger.exception("[변동성돌파] 매수 실패")

    def _execute_sell_all(self) -> None:
        """
        전량 매도 (12:00 실행)

        보유 중인 코인을 모두 시장가로 매도합니다.
        """
        try:
            logger.info("==" * 30)
            logger.info("[변동성돌파 매도] 12:00 전량 매도 시작")

            # 보유 수량 조회
            balance = self.upbit.get_available_amount(self.config.ticker)

            if balance <= 0:
                logger.info(f"[변동성돌파 매도] 보유 수량 없음: {self.config.ticker}")
                logger.info("[변동성돌파 매도] 완료")
                logger.info("==" * 30)
                return

            # 매도 주문
            logger.info(f"[변동성돌파 매도] 전량 매도 시작: {balance} {coin_symbol}")
            result = self.upbit.sell_market_order(self.config.ticker, balance)

            logger.info(f"[변동성돌파 매도] 매도 완료: {result}")

            # 매수 플래그 리셋
            self.bought = False
            logger.info("[변동성돌파 매도] 매수 플래그 리셋 완료")

            logger.info("[변동성돌파 매도] 완료")
            logger.info("==" * 30)

        except Exception:
            logger.exception("[변동성돌파 매도] 실패")

    def _remove_breakout_check_job(self) -> None:
        """
        변동성 돌파 체크 job 제거

        breakout_check job이 존재하면 제거합니다.
        """
        try:
            self.scheduler.remove_job(BREAKOUT_CHECK_JOB_ID)
        except Exception:
            # job이 없으면 무시
            pass

    def run(self) -> None:
        """
        변동성 돌파 전략 실행

        APScheduler를 사용하여 다음 스케줄로 작업을 실행합니다:
        - 매일 00:00: 일일 루틴 (데이터 수집, 시그널 계산)
        - 00:01~11:59 (1분마다): 변동성 돌파 체크 및 매수 (조건부)
        - 매일 12:00: 전량 매도
        """
        if self.scheduler is None:
            self.scheduler = BlockingScheduler()

        # 매일 00:00에 일일 루틴 실행
        self.scheduler.add_job(
            self.execute_daily_routine,
            'cron',
            hour=0,
            minute=0,
            id='morning_routine'
        )

        # 매일 12:00에 전량 매도
        self.scheduler.add_job(
            self._execute_sell_all,
            'cron',
            hour=12,
            minute=0,
            id='afternoon_sell'
        )

        logger.info("=" * 60)
        logger.info("[변동성돌파 전략] 스케줄러 시작")
        logger.info(f"티커: {self.config.ticker}")
        logger.info(f"타겟 변동성: {self.config.target_vol:.2%}")
        logger.info("=" * 60)

        try:
            self.scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("[변동성돌파 전략] 스케줄러 종료")
