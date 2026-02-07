"""run_strategies 잔고 부족 시 스킵 처리 테스트"""

from unittest.mock import MagicMock

from src.constants import MIN_ALLOCATED_BALANCE, RESERVED_BALANCE
from src.scheduled_tasks.tasks import run_strategies


def _create_context(balance: float, tickers: list[str] | None = None, total_balance: int = 1_000_000) -> MagicMock:
    """테스트용 ScheduledTasksContext Mock을 생성합니다."""
    tickers = tickers or ["KRW-BTC"]

    context = MagicMock()
    context.allocation_manager.get_allocated_amount.return_value = balance
    context.tickers = tickers
    context.total_balance = total_balance

    return context


class TestRunStrategiesInsufficientBalance:
    """잔고 부족 시 전략 실행 스킵 테스트"""

    def test_잔고_부족시_전략이_실행되지_않는다(self):
        """allocated_balance가 MIN_ALLOCATED_BALANCE 미만이면 전략을 실행하지 않는다."""
        # given: 잔고가 부족한 상황 (allocated_balance = (0 - 10000) / 1 = -10000)
        context = _create_context(balance=0)

        # when
        run_strategies.__wrapped__(context=context)

        # then: 전략 생성이 호출되지 않아야 한다
        context.create_volatility_strategy.assert_not_called()

    def test_잔고_부족시_healthcheck_ping은_호출된다(self):
        """잔고 부족으로 스킵해도 healthcheck ping은 전송한다."""
        # given
        context = _create_context(balance=0)

        # when
        run_strategies.__wrapped__(context=context)

        # then
        context.healthcheck_client.ping.assert_called_once()

    def test_잔고_부족시_로그가_남는다(self):
        """잔고 부족 시 info 로그를 남긴다."""
        # given
        context = _create_context(balance=0)

        # when
        run_strategies.__wrapped__(context=context)

        # then
        context.logger.info.assert_called_once()
        log_message = context.logger.info.call_args[0][0]
        assert "잔고 부족" in log_message

    def test_정확히_최소_금액_미만일_때_스킵한다(self):
        """allocated_balance가 정확히 MIN_ALLOCATED_BALANCE 미만인 경계값 테스트."""
        # given: allocated = (59999 - 10000) / 1 = 49999 < 50000
        balance = RESERVED_BALANCE + MIN_ALLOCATED_BALANCE - 1
        context = _create_context(balance=balance)

        # when
        run_strategies.__wrapped__(context=context)

        # then
        context.create_volatility_strategy.assert_not_called()
        context.healthcheck_client.ping.assert_called_once()

    def test_여러_티커로_나눴을_때_잔고_부족이면_스킵한다(self):
        """티커가 여러 개일 때 나눈 금액이 부족하면 스킵한다."""
        # given: allocated = (160000 - 10000) / 3 = 50000 → 딱 경계
        # BaseStrategyConfig는 gt=50000이므로 50000은 실패
        # 실제로 MIN_ALLOCATED_BALANCE 미만이 아니므로 스킵하지 않음
        # 49999로 테스트: (159997 - 10000) / 3 = 49999
        balance = RESERVED_BALANCE + MIN_ALLOCATED_BALANCE * 3 - 3
        tickers = ["KRW-BTC", "KRW-ETH", "KRW-XRP"]
        context = _create_context(balance=balance, tickers=tickers)

        # when
        run_strategies.__wrapped__(context=context)

        # then
        context.create_volatility_strategy.assert_not_called()
        context.healthcheck_client.ping.assert_called_once()


class TestRunStrategiesSufficientBalance:
    """잔고 충분 시 전략 정상 실행 테스트"""

    def test_잔고_충분시_전략이_실행된다(self):
        """allocated_balance가 MIN_ALLOCATED_BALANCE 이상이면 전략을 실행한다."""
        # given: allocated = (200000 - 10000) / 1 = 190000 >= 50000
        context = _create_context(balance=200_000)

        # when
        run_strategies.__wrapped__(context=context)

        # then
        context.create_volatility_strategy.assert_called_once()

    def test_최소_금액_이상일_때_전략이_실행된다(self):
        """allocated_balance가 MIN_ALLOCATED_BALANCE 이상이면 스킵하지 않고 전략을 실행한다."""
        # given: allocated = (60001 - 10000) / 1 = 50001 >= 50000
        # BaseStrategyConfig의 gt=50000도 통과
        balance = RESERVED_BALANCE + MIN_ALLOCATED_BALANCE + 1
        context = _create_context(balance=balance)

        # when
        run_strategies.__wrapped__(context=context)

        # then
        context.create_volatility_strategy.assert_called_once()
