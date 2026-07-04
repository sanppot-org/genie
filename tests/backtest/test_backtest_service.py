"""BacktestService.run() 캔들 로드 예외 격리 테스트.

캔들 로드 중 DB 예외(예: 테이블 없음)가 발생하면 해당 전략만 skipped에
추가되고, 나머지 전략은 정상적으로 실행되어야 한다.
"""

from __future__ import annotations

import contextlib
from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd

from src.service.backtest_service import BacktestService

# ---------------------------------------------------------------------------
# 테스트 픽스처 헬퍼
# ---------------------------------------------------------------------------

def _make_mock_database(ticker_id: int = 1) -> MagicMock:
    """session_scope()를 동작하는 컨텍스트 매니저로 패치한 Database mock."""
    mock_session = MagicMock()

    # TickerRepository.find_by_ticker가 반환할 ticker 객체
    mock_ticker = MagicMock()
    mock_ticker.id = ticker_id

    mock_db = MagicMock()

    # session_scope()는 매 호출마다 새 세션을 yield하는 컨텍스트 매니저를 반환해야 한다.
    @contextlib.contextmanager
    def _session_scope():  # type: ignore[return]
        yield mock_session

    mock_db.session_scope.side_effect = _session_scope
    return mock_db, mock_session, mock_ticker


def _make_daily_df() -> pd.DataFrame:
    """단일 일봉 행을 가진 최소 DataFrame."""
    return pd.DataFrame(
        {"open": [100.0], "high": [110.0], "low": [90.0], "close": [105.0], "volume": [1000]},
        index=pd.DatetimeIndex(["2024-01-02"]),
    )


# ---------------------------------------------------------------------------
# 테스트
# ---------------------------------------------------------------------------


class TestBacktestServiceCandelLoadIsolation:
    """캔들 로드 예외 격리 — DB 의존 없이 mock으로 검증."""

    def test_load_exception_goes_to_skipped_not_failed(self) -> None:
        """_load_candles_df가 예외를 던지면 해당 전략은 skipped에 들어가고 전체 요청은 200으로 완료된다."""
        mock_db, mock_session, mock_ticker = _make_mock_database()

        good_df = _make_daily_df()

        # timed_hold(1h) → 예외, volatility_breakout(1d) → 정상 DataFrame
        def fake_load_candles(spec, ticker_id, start_dt, end_dt, asset, session):  # type: ignore[no-untyped-def]
            if spec.timeframe == "1h":
                raise Exception('relation "candle_hour_1" does not exist')
            return good_df, spec.timeframe

        with (
            patch("src.service.backtest_service._load_candles_df", side_effect=fake_load_candles),
            patch("src.database.ticker_repository.TickerRepository.find_by_ticker", return_value=mock_ticker),
            patch("src.service.backtest_service._run_single_strategy") as mock_run,
        ):
            # _run_single_strategy는 정상 결과를 반환
            from src.backtest.result import BacktestResult
            mock_result = MagicMock(spec=BacktestResult)
            mock_result.final_value = 10_500_000.0
            mock_result.total_return_pct = 5.0
            mock_result.strategy_name = "volatility_breakout"
            mock_run.return_value = mock_result

            service = BacktestService(mock_db)
            output = service.run(
                ticker="TQQQ",
                strategy_names=["timed_hold", "volatility_breakout"],
                start=date(2024, 1, 1),
                end=date(2024, 12, 31),
                initial_cash=10_000_000.0,
                commission=0.0005,
                slippage=0.0,
                asset="stock",
            )

        # timed_hold은 skipped
        assert "timed_hold" in output.skipped
        # volatility_breakout은 실행 성공
        assert "volatility_breakout" not in output.skipped
        assert "volatility_breakout" not in output.failed
        assert len(output.results) == 1
        # 전체 failed는 비어있어야 한다 (로드 예외는 skipped)
        assert output.failed == []

    def test_all_strategies_load_fail_returns_empty_results(self) -> None:
        """모든 전략의 캔들 로드가 실패하면 results·failed가 비고 skipped에 전부 쌓인다."""
        mock_db, mock_session, mock_ticker = _make_mock_database()

        def always_raise(spec, ticker_id, start_dt, end_dt, asset, session):  # type: ignore[no-untyped-def]
            raise RuntimeError("DB unavailable")

        with (
            patch("src.service.backtest_service._load_candles_df", side_effect=always_raise),
            patch("src.database.ticker_repository.TickerRepository.find_by_ticker", return_value=mock_ticker),
        ):
            service = BacktestService(mock_db)
            output = service.run(
                ticker="TQQQ",
                strategy_names=["timed_hold", "morning_afternoon"],
                start=None,
                end=None,
                initial_cash=10_000_000.0,
                commission=0.0005,
                slippage=0.0,
                asset="stock",
            )

        assert set(output.skipped) == {"timed_hold", "morning_afternoon"}
        assert output.results == []
        assert output.failed == []

    def test_load_exception_does_not_affect_subsequent_strategy(self) -> None:
        """첫 번째 전략 로드가 예외를 던져도 두 번째·세 번째 전략은 독립적으로 로드·실행된다."""
        mock_db, mock_session, mock_ticker = _make_mock_database()

        good_df = _make_daily_df()
        call_log: list[str] = []

        def selective_raise(spec, ticker_id, start_dt, end_dt, asset, session):  # type: ignore[no-untyped-def]
            call_log.append(spec.name)
            if spec.name == "timed_hold":
                raise Exception('relation "candle_hour_1" does not exist')
            return good_df, spec.timeframe

        with (
            patch("src.service.backtest_service._load_candles_df", side_effect=selective_raise),
            patch("src.database.ticker_repository.TickerRepository.find_by_ticker", return_value=mock_ticker),
            patch("src.service.backtest_service._run_single_strategy") as mock_run,
        ):
            from src.backtest.result import BacktestResult
            mock_result = MagicMock(spec=BacktestResult)
            mock_result.final_value = 10_500_000.0
            mock_result.total_return_pct = 5.0
            mock_result.strategy_name = "volatility_breakout"
            mock_run.return_value = mock_result

            service = BacktestService(mock_db)
            output = service.run(
                ticker="TQQQ",
                strategy_names=["timed_hold", "volatility_breakout", "buy_and_hold"],
                start=date(2024, 1, 1),
                end=date(2024, 12, 31),
                initial_cash=10_000_000.0,
                commission=0.0005,
                slippage=0.0,
                asset="stock",
            )

        # 세 전략 모두 로드 시도했는지 확인
        assert call_log == ["timed_hold", "volatility_breakout", "buy_and_hold"]
        assert "timed_hold" in output.skipped
        assert len(output.results) == 2  # volatility_breakout + buy_and_hold
