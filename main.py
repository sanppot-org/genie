import logging
from time import sleep

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from src.common.healthcheck.client import HealthcheckClient
from src.common.slack.client import SlackClient
from src.config import HealthcheckConfig, SlackConfig
from src.strategy import o_dol_strategy

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# TODO: DB 설정
total_balance = 100_000_000
allocated_balance = 1_000_000


def run_strategies() -> None:
    """1분마다 실행될 전략 실행 함수"""
    try:
        logger.info("암호화폐 자동 매매 시작")

        slack_client = SlackClient(SlackConfig())
        healthcheck_client = HealthcheckClient(HealthcheckConfig())
        tickers = ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-USDT"]
        for ticker in tickers:
            try:
                o_dol_strategy.run(ticker=ticker, total_balance=total_balance, allocated_balance=allocated_balance)
                logger.info(f"{ticker} 전략 실행 완료")
                sleep(0.5)
            except Exception as e:
                logger.error(f"{ticker} 전략 실행 실패: {e}", exc_info=True)
                slack_client.send_error(f"{ticker} 전략 실행 실패: {e}")

        logger.info("암호화폐 자동 매매 완료")

        # 헬스체크 ping 전송 (성공 시)
        healthcheck_client.ping()
    except Exception as e:
        logger.error(f"전략 실행 중 예외 발생: {e}", exc_info=True)


if __name__ == "__main__":
    logger.info("암호화폐 자동 매매 스케줄러 시작")

    # 스케줄러 초기화
    scheduler = BlockingScheduler()

    # 1분마다 실행하도록 스케줄 등록
    scheduler.add_job(
        run_strategies,
        trigger=IntervalTrigger(minutes=1),
        id="crypto_trading",
        name="암호화폐 자동 매매",
        replace_existing=True,
    )

    # 즉시 한 번 실행
    run_strategies()

    try:
        # 스케줄러 시작 (블로킹)
        logger.info("스케줄러 시작됨 - 1분마다 실행")
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("스케줄러 종료")
