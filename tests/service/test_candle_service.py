"""Tests for CandleService."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pandas as pd

from src.database.candle_repositories import CandleMinute1Repository
from src.database.models import CandleMinute1, Ticker
from src.service.candle_service import CandleService, CollectMode


class TestCollectMinute1CandlesIncrementalMode:
    """collect_minute1_candles incremental 모드 (기본값) 테스트."""

    def test_stops_when_api_returns_data_older_than_db_latest(
            self,
            candle_service: CandleService,
            minute1_repo: CandleMinute1Repository,
            sample_ticker: Ticker,
    ):
        """DB에 최신 데이터가 있으면 그 이후 데이터만 수집하고 중단한다."""
        # Given: DB에 이미 캔들이 있음
        existing_candle = CandleMinute1(
            timestamp=datetime(2024, 1, 1, 10, 0, tzinfo=UTC),
            kst_time=datetime(2024, 1, 1, 19, 0),
            ticker_id=sample_ticker.id,
            open=50000000,
            high=51000000,
            low=49000000,
            close=50500000,
            volume=10.5,
        )
        minute1_repo.bulk_upsert([existing_candle])

        # Mock API: DB 최신보다 오래된 데이터만 반환
        old_data = pd.DataFrame({
            "open": [49000000],
            "high": [50000000],
            "low": [48000000],
            "close": [49500000],
            "volume": [8.0],
            "value": [400000000],
            "timestamp": [pd.Timestamp("2024-01-01 09:00:00", tz="UTC")],  # DB보다 오래됨
        }, index=pd.DatetimeIndex([
            pd.Timestamp("2024-01-01 18:00:00", tz="Asia/Seoul"),
        ], name="index"))

        with patch("src.upbit.upbit_api.UpbitAPI") as mock_api_class:
            mock_api = MagicMock()
            mock_api.get_candles.return_value = old_data
            mock_api_class.return_value = mock_api

            # When: incremental 모드 (기본값)
            total_saved = candle_service.collect_minute1_candles(sample_ticker)

            # Then: 아무것도 저장하지 않음
            assert total_saved == 0
            # API는 한 번만 호출됨 (첫 호출 후 필터링되어 빈 데이터가 되어 중단)
            assert mock_api.get_candles.call_count == 1

    def test_collects_only_newer_data_than_db_latest(
            self,
            candle_service: CandleService,
            minute1_repo: CandleMinute1Repository,
            sample_ticker: Ticker,
    ):
        """DB 최신보다 새로운 데이터만 수집한다."""
        # Given: DB에 이미 캔들이 있음
        existing_candle = CandleMinute1(
            timestamp=datetime(2024, 1, 1, 10, 0, tzinfo=UTC),
            kst_time=datetime(2024, 1, 1, 19, 0),
            ticker_id=sample_ticker.id,
            open=50000000,
            high=51000000,
            low=49000000,
            close=50500000,
            volume=10.5,
        )
        minute1_repo.bulk_upsert([existing_candle])

        # Mock API: 새 데이터 + 오래된 데이터 혼합
        mixed_data = pd.DataFrame({
            "open": [51000000, 49000000],
            "high": [52000000, 50000000],
            "low": [50000000, 48000000],
            "close": [51500000, 49500000],
            "volume": [12.0, 8.0],
            "value": [600000000, 400000000],
            "timestamp": [
                pd.Timestamp("2024-01-01 11:00:00", tz="UTC"),  # 새 데이터
                pd.Timestamp("2024-01-01 09:00:00", tz="UTC"),  # 오래된 데이터
            ],
        }, index=pd.DatetimeIndex([
            pd.Timestamp("2024-01-01 20:00:00", tz="Asia/Seoul"),
            pd.Timestamp("2024-01-01 18:00:00", tz="Asia/Seoul"),
        ], name="index"))

        # 두 번째 호출은 오래된 데이터만 반환 → 종료
        old_only_data = pd.DataFrame({
            "open": [48000000],
            "high": [49000000],
            "low": [47000000],
            "close": [48500000],
            "volume": [6.0],
            "value": [300000000],
            "timestamp": [pd.Timestamp("2024-01-01 08:00:00", tz="UTC")],
        }, index=pd.DatetimeIndex([
            pd.Timestamp("2024-01-01 17:00:00", tz="Asia/Seoul"),
        ], name="index"))

        with patch("src.upbit.upbit_api.UpbitAPI") as mock_api_class:
            mock_api = MagicMock()
            mock_api.get_candles.side_effect = [mixed_data, old_only_data]
            mock_api_class.return_value = mock_api

            # When
            total_saved = candle_service.collect_minute1_candles(sample_ticker, batch_size=10)

            # Then: 새 데이터 1개만 저장됨
            assert total_saved == 1

            # DB에 새 캔들이 저장됨
            latest = minute1_repo.get_latest_candle(sample_ticker.id)
            assert latest is not None
            assert latest.timestamp.replace(tzinfo=UTC) == datetime(2024, 1, 1, 11, 0, tzinfo=UTC)

    def test_collects_all_when_db_is_empty(
            self,
            candle_service: CandleService,
            minute1_repo: CandleMinute1Repository,
            sample_ticker: Ticker,
    ):
        """DB에 데이터가 없으면 전체 수집한다."""
        # Given: DB가 비어있음
        assert minute1_repo.get_latest_candle(sample_ticker.id) is None

        # Mock API 응답
        first_batch = pd.DataFrame({
            "open": [50000000, 49000000],
            "high": [51000000, 50000000],
            "low": [49000000, 48000000],
            "close": [50500000, 49500000],
            "volume": [10.0, 8.0],
            "value": [500000000, 400000000],
            "timestamp": [
                pd.Timestamp("2024-01-01 10:00:00", tz="UTC"),
                pd.Timestamp("2024-01-01 09:00:00", tz="UTC"),
            ],
        }, index=pd.DatetimeIndex([
            pd.Timestamp("2024-01-01 19:00:00", tz="Asia/Seoul"),
            pd.Timestamp("2024-01-01 18:00:00", tz="Asia/Seoul"),
        ], name="index"))

        empty_df = pd.DataFrame()

        with patch("src.upbit.upbit_api.UpbitAPI") as mock_api_class:
            mock_api = MagicMock()
            mock_api.get_candles.side_effect = [first_batch, empty_df]
            mock_api_class.return_value = mock_api

            # When: incremental 모드 (기본값)
            total_saved = candle_service.collect_minute1_candles(sample_ticker, batch_size=10)

            # Then: 전체 데이터 저장
            assert total_saved == 2


class TestCollectMinute1CandlesFullSyncMode:
    """collect_minute1_candles mode=CollectMode.FULL 모드 테스트."""

    def test_collects_all_data_ignoring_db_latest(
            self,
            candle_service: CandleService,
            minute1_repo: CandleMinute1Repository,
            sample_ticker: Ticker,
    ):
        """mode=CollectMode.FULL일 때 DB 최신 데이터를 무시하고 전체 수집한다."""
        # Given: DB에 이미 캔들이 있음
        existing_candle = CandleMinute1(
            timestamp=datetime(2024, 1, 1, 10, 0, tzinfo=UTC),
            kst_time=datetime(2024, 1, 1, 19, 0),
            ticker_id=sample_ticker.id,
            open=50000000,
            high=51000000,
            low=49000000,
            close=50500000,
            volume=10.5,
        )
        minute1_repo.bulk_upsert([existing_candle])

        # Mock API: DB 최신보다 오래된 데이터 포함
        all_data = pd.DataFrame({
            "open": [51000000, 49000000],
            "high": [52000000, 50000000],
            "low": [50000000, 48000000],
            "close": [51500000, 49500000],
            "volume": [12.0, 8.0],
            "value": [600000000, 400000000],
            "timestamp": [
                pd.Timestamp("2024-01-01 11:00:00", tz="UTC"),  # 새 데이터
                pd.Timestamp("2024-01-01 09:00:00", tz="UTC"),  # 오래된 데이터
            ],
        }, index=pd.DatetimeIndex([
            pd.Timestamp("2024-01-01 20:00:00", tz="Asia/Seoul"),
            pd.Timestamp("2024-01-01 18:00:00", tz="Asia/Seoul"),
        ], name="index"))

        empty_df = pd.DataFrame()

        with patch("src.upbit.upbit_api.UpbitAPI") as mock_api_class:
            mock_api = MagicMock()
            mock_api.get_candles.side_effect = [all_data, empty_df]
            mock_api_class.return_value = mock_api

            # When: mode=CollectMode.FULL
            total_saved = candle_service.collect_minute1_candles(sample_ticker, mode=CollectMode.FULL, batch_size=10)

            # Then: 오래된 데이터 포함 전체 저장
            assert total_saved == 2

    def test_full_mode_continues_until_api_returns_empty(
            self,
            candle_service: CandleService,
            minute1_repo: CandleMinute1Repository,
            sample_ticker: Ticker,
    ):
        """FULL 모드는 API가 빈 데이터를 반환할 때까지 계속 수집한다."""
        # Given: DB에 데이터가 있음
        existing_candle = CandleMinute1(
            timestamp=datetime(2024, 1, 1, 10, 0, tzinfo=UTC),
            kst_time=datetime(2024, 1, 1, 19, 0),
            ticker_id=sample_ticker.id,
            open=50000000,
            high=51000000,
            low=49000000,
            close=50500000,
            volume=10.5,
        )
        minute1_repo.bulk_upsert([existing_candle])

        # Mock API: 3번의 배치 호출
        batch1 = pd.DataFrame({
            "open": [52000000],
            "high": [53000000],
            "low": [51000000],
            "close": [52500000],
            "volume": [15.0],
            "value": [750000000],
            "timestamp": [pd.Timestamp("2024-01-01 12:00:00", tz="UTC")],
        }, index=pd.DatetimeIndex([
            pd.Timestamp("2024-01-01 21:00:00", tz="Asia/Seoul"),
        ], name="index"))

        batch2 = pd.DataFrame({
            "open": [48000000],
            "high": [49000000],
            "low": [47000000],
            "close": [48500000],
            "volume": [5.0],
            "value": [250000000],
            "timestamp": [pd.Timestamp("2024-01-01 08:00:00", tz="UTC")],  # DB보다 오래된 데이터
        }, index=pd.DatetimeIndex([
            pd.Timestamp("2024-01-01 17:00:00", tz="Asia/Seoul"),
        ], name="index"))

        empty_df = pd.DataFrame()

        with patch("src.upbit.upbit_api.UpbitAPI") as mock_api_class:
            mock_api = MagicMock()
            mock_api.get_candles.side_effect = [batch1, batch2, empty_df]
            mock_api_class.return_value = mock_api

            # When: mode=CollectMode.FULL
            total_saved = candle_service.collect_minute1_candles(sample_ticker, mode=CollectMode.FULL, batch_size=10)

            # Then: 모든 배치 수집
            assert total_saved == 2
            # API가 빈 데이터 반환할 때까지 호출됨
            assert mock_api.get_candles.call_count == 3


class TestCollectMinute1CandlesBackfillMode:
    """collect_minute1_candles mode=CollectMode.BACKFILL 모드 테스트."""

    def test_backfill_starts_from_oldest_timestamp(
            self,
            candle_service: CandleService,
            minute1_repo: CandleMinute1Repository,
            sample_ticker: Ticker,
    ):
        """BACKFILL 모드는 DB의 가장 오래된 timestamp부터 시작한다."""
        # Given: DB에 캔들이 있음 (10:00, 11:00)
        existing_candles = [
            CandleMinute1(
                timestamp=datetime(2024, 1, 1, 10, 0, tzinfo=UTC),
                kst_time=datetime(2024, 1, 1, 19, 0),
                ticker_id=sample_ticker.id,
                open=50000000,
                high=51000000,
                low=49000000,
                close=50500000,
                volume=10.5,
            ),
            CandleMinute1(
                timestamp=datetime(2024, 1, 1, 11, 0, tzinfo=UTC),
                kst_time=datetime(2024, 1, 1, 20, 0),
                ticker_id=sample_ticker.id,
                open=50500000,
                high=51500000,
                low=50000000,
                close=51000000,
                volume=12.3,
            ),
        ]
        minute1_repo.bulk_upsert(existing_candles)

        # Mock API: 10:00 이전의 과거 데이터 반환
        past_data = pd.DataFrame({
            "open": [48000000],
            "high": [49000000],
            "low": [47000000],
            "close": [48500000],
            "volume": [8.0],
            "value": [400000000],
            "timestamp": [pd.Timestamp("2024-01-01 09:00:00", tz="UTC")],
        }, index=pd.DatetimeIndex([
            pd.Timestamp("2024-01-01 18:00:00", tz="Asia/Seoul"),
        ], name="index"))

        empty_df = pd.DataFrame()

        with patch("src.upbit.upbit_api.UpbitAPI") as mock_api_class:
            mock_api = MagicMock()
            mock_api.get_candles.side_effect = [past_data, empty_df]
            mock_api_class.return_value = mock_api

            # When: BACKFILL 모드로 수집
            total_saved = candle_service.collect_minute1_candles(sample_ticker, mode=CollectMode.BACKFILL, batch_size=10)

            # Then: 과거 데이터 1개 저장
            assert total_saved == 1

            # API 호출 시 to 파라미터가 oldest timestamp (10:00)임을 확인
            # Note: SQLite는 timezone 정보를 저장하지 않아 naive datetime 반환
            first_call_kwargs = mock_api.get_candles.call_args_list[0].kwargs
            actual_to = first_call_kwargs["to"]
            expected_to = datetime(2024, 1, 1, 10, 0)
            # timezone 제거 후 비교
            if actual_to.tzinfo is not None:
                actual_to = actual_to.replace(tzinfo=None)
            assert actual_to == expected_to

    def test_backfill_collects_until_api_returns_empty(
            self,
            candle_service: CandleService,
            minute1_repo: CandleMinute1Repository,
            sample_ticker: Ticker,
    ):
        """BACKFILL 모드는 API가 빈 데이터를 반환할 때까지 수집한다."""
        # Given: DB에 캔들이 있음
        existing_candle = CandleMinute1(
            timestamp=datetime(2024, 1, 1, 10, 0, tzinfo=UTC),
            kst_time=datetime(2024, 1, 1, 19, 0),
            ticker_id=sample_ticker.id,
            open=50000000,
            high=51000000,
            low=49000000,
            close=50500000,
            volume=10.5,
        )
        minute1_repo.bulk_upsert([existing_candle])

        # Mock API: 2번의 배치 호출
        batch1 = pd.DataFrame({
            "open": [49000000],
            "high": [50000000],
            "low": [48000000],
            "close": [49500000],
            "volume": [9.0],
            "value": [450000000],
            "timestamp": [pd.Timestamp("2024-01-01 09:00:00", tz="UTC")],
        }, index=pd.DatetimeIndex([
            pd.Timestamp("2024-01-01 18:00:00", tz="Asia/Seoul"),
        ], name="index"))

        batch2 = pd.DataFrame({
            "open": [48000000],
            "high": [49000000],
            "low": [47000000],
            "close": [48500000],
            "volume": [7.0],
            "value": [350000000],
            "timestamp": [pd.Timestamp("2024-01-01 08:00:00", tz="UTC")],
        }, index=pd.DatetimeIndex([
            pd.Timestamp("2024-01-01 17:00:00", tz="Asia/Seoul"),
        ], name="index"))

        empty_df = pd.DataFrame()

        with patch("src.upbit.upbit_api.UpbitAPI") as mock_api_class:
            mock_api = MagicMock()
            mock_api.get_candles.side_effect = [batch1, batch2, empty_df]
            mock_api_class.return_value = mock_api

            # When: BACKFILL 모드
            total_saved = candle_service.collect_minute1_candles(sample_ticker, mode=CollectMode.BACKFILL, batch_size=10)

            # Then: 2개의 과거 데이터 저장
            assert total_saved == 2
            # API가 빈 데이터 반환할 때까지 호출됨
            assert mock_api.get_candles.call_count == 3

    def test_backfill_with_empty_db_acts_like_full(
            self,
            candle_service: CandleService,
            minute1_repo: CandleMinute1Repository,
            sample_ticker: Ticker,
    ):
        """DB가 비어있으면 FULL 모드처럼 동작한다."""
        # Given: DB가 비어있음
        assert minute1_repo.get_oldest_candle(sample_ticker.id) is None

        # Mock API 응답
        first_batch = pd.DataFrame({
            "open": [50000000],
            "high": [51000000],
            "low": [49000000],
            "close": [50500000],
            "volume": [10.0],
            "value": [500000000],
            "timestamp": [pd.Timestamp("2024-01-01 10:00:00", tz="UTC")],
        }, index=pd.DatetimeIndex([
            pd.Timestamp("2024-01-01 19:00:00", tz="Asia/Seoul"),
        ], name="index"))

        empty_df = pd.DataFrame()

        with patch("src.upbit.upbit_api.UpbitAPI") as mock_api_class:
            mock_api = MagicMock()
            mock_api.get_candles.side_effect = [first_batch, empty_df]
            mock_api_class.return_value = mock_api

            # When: BACKFILL 모드 (DB 비어있음)
            total_saved = candle_service.collect_minute1_candles(sample_ticker, mode=CollectMode.BACKFILL, batch_size=10)

            # Then: 전체 데이터 저장
            assert total_saved == 1
            # to 파라미터가 None (기본값)으로 호출됨
            first_call_kwargs = mock_api.get_candles.call_args_list[0].kwargs
            assert first_call_kwargs.get("to") is None
