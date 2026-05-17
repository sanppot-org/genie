"""sync_kr_stock_daily_candles 스케줄 task 분기 테스트."""

from unittest.mock import MagicMock

from src.providers.pykrx_fundamental_client import KrxClosedDayError
from src.providers.pykrx_ticker_client import EmptyPykrxResponseError
from src.scheduled_tasks.tasks import sync_kr_stock_daily_candles
from src.service.daily_candle_sync_service import DailyCandleSyncResult


class TestSyncKrStockDailyCandlesTask:
    """task 분기 로직만 검증 (client/service 자체는 별도 테스트로 커버)."""

    def test_정상_실행시_slack_알림_없이_종료한다(self) -> None:
        service = MagicMock()
        service.sync.return_value = DailyCandleSyncResult(
            received=2900, upserted=2700, skipped_unmapped=200, skipped_no_trade=0,
        )
        slack = MagicMock()

        sync_kr_stock_daily_candles.__wrapped__(service=service, slack_client=slack)  # type: ignore[attr-defined]

        service.sync.assert_called_once()
        slack.send_status.assert_not_called()

    def test_휴장일_빈응답은_slack_없이_silent_skip(self) -> None:
        service = MagicMock()
        service.sync.side_effect = EmptyPykrxResponseError("empty")
        slack = MagicMock()

        sync_kr_stock_daily_candles.__wrapped__(service=service, slack_client=slack)  # type: ignore[attr-defined]

        slack.send_status.assert_not_called()

    def test_휴장일_거래량_전부_0_패턴도_slack_없이_silent_skip(self) -> None:
        service = MagicMock()
        service.sync.side_effect = KrxClosedDayError("휴장일")
        slack = MagicMock()

        sync_kr_stock_daily_candles.__wrapped__(service=service, slack_client=slack)  # type: ignore[attr-defined]

        slack.send_status.assert_not_called()

    def test_기타_예외는_slack_알림을_발송한다(self) -> None:
        service = MagicMock()
        service.sync.side_effect = RuntimeError("DB 연결 실패")
        slack = MagicMock()

        sync_kr_stock_daily_candles.__wrapped__(service=service, slack_client=slack)  # type: ignore[attr-defined]

        slack.send_status.assert_called_once()
        message = slack.send_status.call_args[0][0]
        assert "일봉 동기화 실패" in message
        assert "DB 연결 실패" in message
