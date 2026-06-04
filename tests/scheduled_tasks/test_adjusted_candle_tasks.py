"""수정주가 재보정/안전망 스케줄 task + 스케줄 등록 테스트."""

from unittest.mock import MagicMock

from apscheduler.triggers.cron import CronTrigger

from src.scheduled_tasks.schedules import get_schedules
from src.scheduled_tasks.tasks import readjust_kr_stock_splits, resync_all_adjusted_candles
from src.scheduler_config import ScheduleConfig
from src.service.adjusted_candle_sync_service import AdjustedSyncResult


def _result(attempted: int = 1, failed: tuple[str, ...] = ()) -> AdjustedSyncResult:
    return AdjustedSyncResult(
        ticker_count=attempted, skipped_already=0, api_attempted=attempted,
        api_failed=len(failed), tickers_updated=attempted - len(failed),
        rows_updated=attempted * 100, partial_tickers=0, failed_tickers=list(failed),
    )


class TestReadjustSplitsTask:
    def test_후보_있고_실패_없으면_slack_없음(self) -> None:
        service = MagicMock()
        service.readjust_recent_splits.return_value = _result(attempted=2)
        slack = MagicMock()

        readjust_kr_stock_splits.__wrapped__(service=service, slack_client=slack)  # type: ignore[attr-defined]

        service.readjust_recent_splits.assert_called_once()
        slack.send_status.assert_not_called()

    def test_후보_없으면_slack_없음(self) -> None:
        service = MagicMock()
        service.readjust_recent_splits.return_value = _result(attempted=0)
        slack = MagicMock()

        readjust_kr_stock_splits.__wrapped__(service=service, slack_client=slack)  # type: ignore[attr-defined]

        slack.send_status.assert_not_called()

    def test_일부_실패시_slack_알림(self) -> None:
        service = MagicMock()
        service.readjust_recent_splits.return_value = _result(attempted=2, failed=("005930",))
        slack = MagicMock()

        readjust_kr_stock_splits.__wrapped__(service=service, slack_client=slack)  # type: ignore[attr-defined]

        slack.send_status.assert_called_once()

    def test_예외시_slack_알림(self) -> None:
        service = MagicMock()
        service.readjust_recent_splits.side_effect = RuntimeError("boom")
        slack = MagicMock()

        readjust_kr_stock_splits.__wrapped__(service=service, slack_client=slack)  # type: ignore[attr-defined]

        assert "재보정 실패" in slack.send_status.call_args[0][0]


class TestResyncAllTask:
    def test_전종목_재백필_only_stale_false_호출(self) -> None:
        service = MagicMock()
        service.sync.return_value = _result(attempted=2772)
        slack = MagicMock()

        resync_all_adjusted_candles.__wrapped__(service=service, slack_client=slack)  # type: ignore[attr-defined]

        service.sync.assert_called_once_with(only_stale=False)
        slack.send_status.assert_not_called()

    def test_일부_실패시_slack_알림(self) -> None:
        service = MagicMock()
        service.sync.return_value = _result(attempted=2772, failed=("000660",))
        slack = MagicMock()

        resync_all_adjusted_candles.__wrapped__(service=service, slack_client=slack)  # type: ignore[attr-defined]

        slack.send_status.assert_called_once()

    def test_예외시_slack_알림(self) -> None:
        service = MagicMock()
        service.sync.side_effect = RuntimeError("boom")
        slack = MagicMock()

        resync_all_adjusted_candles.__wrapped__(service=service, slack_client=slack)  # type: ignore[attr-defined]

        assert "안전망 실패" in slack.send_status.call_args[0][0]


class TestScheduleRegistration:
    def test_분기_안전망_스케줄_등록(self) -> None:
        schedules = get_schedules()
        by_id = {s.id: s for s in schedules}
        assert "readjust_kr_stock_splits" in by_id
        assert "resync_all_adjusted_candles" in by_id
        # 분기 안전망은 misfire 유예가 길게 설정돼 있어야 함
        assert by_id["resync_all_adjusted_candles"].misfire_grace_time == 3600

    def test_misfire_grace_time_kwargs_조건부_포함(self) -> None:
        with_grace = ScheduleConfig(
            func=lambda: None, trigger=CronTrigger(hour=3), id="x", name="x",
            misfire_grace_time=3600,
        )
        without = ScheduleConfig(func=lambda: None, trigger=CronTrigger(hour=3), id="y", name="y")
        assert with_grace.to_add_job_kwargs()["misfire_grace_time"] == 3600
        assert "misfire_grace_time" not in without.to_add_job_kwargs()
