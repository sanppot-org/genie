"""Tests for CandleService."""

from datetime import UTC, datetime

import pandas as pd

from src.database.candle_repositories import CandleMinute1Repository
from src.database.models import CandleMinute1, Ticker
from src.service.candle_service import CandleService, CollectMode


def create_common_candle_df(
        timestamps: list[datetime],
        local_times: list[datetime],
        opens: list[float],
        highs: list[float],
        lows: list[float],
        closes: list[float],
        volumes: list[float],
) -> pd.DataFrame:
    """CommonCandleSchema 형식의 테스트용 DataFrame 생성."""
    return pd.DataFrame({
        "timestamp": timestamps,
        "local_time": local_times,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
    }, index=pd.DatetimeIndex(timestamps))


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
            local_time=datetime(2024, 1, 1, 19, 0),
            ticker_id=sample_ticker.id,
            open=50000000,
            high=51000000,
            low=49000000,
            close=50500000,
            volume=10.5,
        )
        minute1_repo.bulk_upsert([existing_candle])

        # Mock API: DB 최신보다 오래된 데이터만 반환
        old_data = create_common_candle_df(
            timestamps=[datetime(2024, 1, 1, 9, 0, tzinfo=UTC)],  # DB보다 오래됨
            local_times=[datetime(2024, 1, 1, 18, 0)],
            opens=[49000000.0],
            highs=[50000000.0],
            lows=[48000000.0],
            closes=[49500000.0],
            volumes=[8.0],
        )

        candle_service._query_service.get_candles.return_value = old_data

        # When: incremental 모드 (기본값)
        total_saved = candle_service.collect_minute1_candles(sample_ticker)

        # Then: 아무것도 저장하지 않음
        assert total_saved == 0
        # API는 한 번만 호출됨 (첫 호출 후 필터링되어 빈 데이터가 되어 중단)
        assert candle_service._query_service.get_candles.call_count == 1

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
            local_time=datetime(2024, 1, 1, 19, 0),
            ticker_id=sample_ticker.id,
            open=50000000,
            high=51000000,
            low=49000000,
            close=50500000,
            volume=10.5,
        )
        minute1_repo.bulk_upsert([existing_candle])

        # Mock API: 새 데이터 + 오래된 데이터 혼합
        mixed_data = create_common_candle_df(
            timestamps=[
                datetime(2024, 1, 1, 11, 0, tzinfo=UTC),  # 새 데이터
                datetime(2024, 1, 1, 9, 0, tzinfo=UTC),  # 오래된 데이터
            ],
            local_times=[
                datetime(2024, 1, 1, 20, 0),
                datetime(2024, 1, 1, 18, 0),
            ],
            opens=[51000000.0, 49000000.0],
            highs=[52000000.0, 50000000.0],
            lows=[50000000.0, 48000000.0],
            closes=[51500000.0, 49500000.0],
            volumes=[12.0, 8.0],
        )

        # 두 번째 호출은 오래된 데이터만 반환 → 종료
        old_only_data = create_common_candle_df(
            timestamps=[datetime(2024, 1, 1, 8, 0, tzinfo=UTC)],
            local_times=[datetime(2024, 1, 1, 17, 0)],
            opens=[48000000.0],
            highs=[49000000.0],
            lows=[47000000.0],
            closes=[48500000.0],
            volumes=[6.0],
        )

        candle_service._query_service.get_candles.side_effect = [mixed_data, old_only_data]

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
        first_batch = create_common_candle_df(
            timestamps=[
                datetime(2024, 1, 1, 10, 0, tzinfo=UTC),
                datetime(2024, 1, 1, 9, 0, tzinfo=UTC),
            ],
            local_times=[
                datetime(2024, 1, 1, 19, 0),
                datetime(2024, 1, 1, 18, 0),
            ],
            opens=[50000000.0, 49000000.0],
            highs=[51000000.0, 50000000.0],
            lows=[49000000.0, 48000000.0],
            closes=[50500000.0, 49500000.0],
            volumes=[10.0, 8.0],
        )

        empty_df = pd.DataFrame()

        candle_service._query_service.get_candles.side_effect = [first_batch, empty_df]

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
            local_time=datetime(2024, 1, 1, 19, 0),
            ticker_id=sample_ticker.id,
            open=50000000,
            high=51000000,
            low=49000000,
            close=50500000,
            volume=10.5,
        )
        minute1_repo.bulk_upsert([existing_candle])

        # Mock API: DB 최신보다 오래된 데이터 포함
        all_data = create_common_candle_df(
            timestamps=[
                datetime(2024, 1, 1, 11, 0, tzinfo=UTC),  # 새 데이터
                datetime(2024, 1, 1, 9, 0, tzinfo=UTC),  # 오래된 데이터
            ],
            local_times=[
                datetime(2024, 1, 1, 20, 0),
                datetime(2024, 1, 1, 18, 0),
            ],
            opens=[51000000.0, 49000000.0],
            highs=[52000000.0, 50000000.0],
            lows=[50000000.0, 48000000.0],
            closes=[51500000.0, 49500000.0],
            volumes=[12.0, 8.0],
        )

        empty_df = pd.DataFrame()

        candle_service._query_service.get_candles.side_effect = [all_data, empty_df]

        # When: mode=CollectMode.FULL
        total_saved = candle_service.collect_minute1_candles(sample_ticker, batch_size=10, mode=CollectMode.FULL)

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
            local_time=datetime(2024, 1, 1, 19, 0),
            ticker_id=sample_ticker.id,
            open=50000000,
            high=51000000,
            low=49000000,
            close=50500000,
            volume=10.5,
        )
        minute1_repo.bulk_upsert([existing_candle])

        # Mock API: 3번의 배치 호출
        batch1 = create_common_candle_df(
            timestamps=[datetime(2024, 1, 1, 12, 0, tzinfo=UTC)],
            local_times=[datetime(2024, 1, 1, 21, 0)],
            opens=[52000000.0],
            highs=[53000000.0],
            lows=[51000000.0],
            closes=[52500000.0],
            volumes=[15.0],
        )

        batch2 = create_common_candle_df(
            timestamps=[datetime(2024, 1, 1, 8, 0, tzinfo=UTC)],  # DB보다 오래된 데이터
            local_times=[datetime(2024, 1, 1, 17, 0)],
            opens=[48000000.0],
            highs=[49000000.0],
            lows=[47000000.0],
            closes=[48500000.0],
            volumes=[5.0],
        )

        empty_df = pd.DataFrame()

        candle_service._query_service.get_candles.side_effect = [batch1, batch2, empty_df]

        # When: mode=CollectMode.FULL
        # batch_size=1: 1개 반환 = batch_size와 같으므로 다음 페이지 존재 가능
        total_saved = candle_service.collect_minute1_candles(sample_ticker, batch_size=1, mode=CollectMode.FULL)

        # Then: 모든 배치 수집
        assert total_saved == 2
        # API가 빈 데이터 반환할 때까지 호출됨
        assert candle_service._query_service.get_candles.call_count == 3


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
                local_time=datetime(2024, 1, 1, 19, 0),
                ticker_id=sample_ticker.id,
                open=50000000,
                high=51000000,
                low=49000000,
                close=50500000,
                volume=10.5,
            ),
            CandleMinute1(
                timestamp=datetime(2024, 1, 1, 11, 0, tzinfo=UTC),
                local_time=datetime(2024, 1, 1, 20, 0),
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
        past_data = create_common_candle_df(
            timestamps=[datetime(2024, 1, 1, 9, 0, tzinfo=UTC)],
            local_times=[datetime(2024, 1, 1, 18, 0)],
            opens=[48000000.0],
            highs=[49000000.0],
            lows=[47000000.0],
            closes=[48500000.0],
            volumes=[8.0],
        )

        empty_df = pd.DataFrame()

        candle_service._query_service.get_candles.side_effect = [past_data, empty_df]

        # When: BACKFILL 모드로 수집
        total_saved = candle_service.collect_minute1_candles(sample_ticker, batch_size=10, mode=CollectMode.BACKFILL)

        # Then: 과거 데이터 1개 저장
        assert total_saved == 1

        # API 호출 시 end_time 파라미터가 oldest timestamp (10:00)임을 확인
        # Note: SQLite는 timezone 정보를 저장하지 않아 naive datetime 반환
        first_call_kwargs = candle_service._query_service.get_candles.call_args_list[0].kwargs
        actual_end_time = first_call_kwargs["end_time"]
        expected_end_time = datetime(2024, 1, 1, 10, 0)
        # timezone 제거 후 비교
        if actual_end_time is not None and actual_end_time.tzinfo is not None:
            actual_end_time = actual_end_time.replace(tzinfo=None)
        assert actual_end_time == expected_end_time

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
            local_time=datetime(2024, 1, 1, 19, 0),
            ticker_id=sample_ticker.id,
            open=50000000,
            high=51000000,
            low=49000000,
            close=50500000,
            volume=10.5,
        )
        minute1_repo.bulk_upsert([existing_candle])

        # Mock API: 2번의 배치 호출
        batch1 = create_common_candle_df(
            timestamps=[datetime(2024, 1, 1, 9, 0, tzinfo=UTC)],
            local_times=[datetime(2024, 1, 1, 18, 0)],
            opens=[49000000.0],
            highs=[50000000.0],
            lows=[48000000.0],
            closes=[49500000.0],
            volumes=[9.0],
        )

        batch2 = create_common_candle_df(
            timestamps=[datetime(2024, 1, 1, 8, 0, tzinfo=UTC)],
            local_times=[datetime(2024, 1, 1, 17, 0)],
            opens=[48000000.0],
            highs=[49000000.0],
            lows=[47000000.0],
            closes=[48500000.0],
            volumes=[7.0],
        )

        empty_df = pd.DataFrame()

        candle_service._query_service.get_candles.side_effect = [batch1, batch2, empty_df]

        # When: BACKFILL 모드
        # batch_size=1: 1개 반환 = batch_size와 같으므로 다음 페이지 존재 가능
        total_saved = candle_service.collect_minute1_candles(sample_ticker, batch_size=1, mode=CollectMode.BACKFILL)

        # Then: 2개의 과거 데이터 저장
        assert total_saved == 2
        # API가 빈 데이터 반환할 때까지 호출됨
        assert candle_service._query_service.get_candles.call_count == 3

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
        first_batch = create_common_candle_df(
            timestamps=[datetime(2024, 1, 1, 10, 0, tzinfo=UTC)],
            local_times=[datetime(2024, 1, 1, 19, 0)],
            opens=[50000000.0],
            highs=[51000000.0],
            lows=[49000000.0],
            closes=[50500000.0],
            volumes=[10.0],
        )

        empty_df = pd.DataFrame()

        candle_service._query_service.get_candles.side_effect = [first_batch, empty_df]

        # When: BACKFILL 모드 (DB 비어있음)
        total_saved = candle_service.collect_minute1_candles(sample_ticker, batch_size=10, mode=CollectMode.BACKFILL)

        # Then: 전체 데이터 저장
        assert total_saved == 1
        # end_time 파라미터가 None (기본값)으로 호출됨
        first_call_kwargs = candle_service._query_service.get_candles.call_args_list[0].kwargs
        assert first_call_kwargs.get("end_time") is None


class TestCollectMinute1CandlesStartParameter:
    """start 파라미터 테스트"""

    def test_stops_when_all_data_is_before_start(
            self,
            candle_service: CandleService,
            sample_ticker: Ticker,
    ):
        """모든 데이터가 start 이전이면 수집을 중단한다."""
        # Given: API가 start 이전 데이터만 반환
        old_data = create_common_candle_df(
            timestamps=[datetime(2024, 1, 1, 9, 0, tzinfo=UTC)],
            local_times=[datetime(2024, 1, 1, 18, 0)],
            opens=[49000000.0],
            highs=[50000000.0],
            lows=[48000000.0],
            closes=[49500000.0],
            volumes=[8.0],
        )

        candle_service._query_service.get_candles.return_value = old_data

        # When: start를 데이터보다 미래로 설정
        start = datetime(2024, 1, 1, 10, 0, tzinfo=UTC)
        total_saved = candle_service.collect_minute1_candles(sample_ticker, start=start, mode=CollectMode.FULL)

        # Then: 아무것도 저장하지 않음
        assert total_saved == 0
        assert candle_service._query_service.get_candles.call_count == 1

    def test_filters_data_before_start(
            self,
            candle_service: CandleService,
            minute1_repo: CandleMinute1Repository,
            sample_ticker: Ticker,
    ):
        """start 이전 데이터는 필터링하고 이후 데이터만 저장한다."""
        # Given: API가 start 전후 데이터 모두 반환
        mixed_data = create_common_candle_df(
            timestamps=[
                datetime(2024, 1, 1, 9, 0, tzinfo=UTC),  # start 이전
                datetime(2024, 1, 1, 10, 0, tzinfo=UTC),  # start 이후
            ],
            local_times=[
                datetime(2024, 1, 1, 18, 0),
                datetime(2024, 1, 1, 19, 0),
            ],
            opens=[49000000.0, 50000000.0],
            highs=[50000000.0, 51000000.0],
            lows=[48000000.0, 49000000.0],
            closes=[49500000.0, 50500000.0],
            volumes=[8.0, 10.0],
        )

        empty_df = pd.DataFrame()

        candle_service._query_service.get_candles.side_effect = [mixed_data, empty_df]

        # When: start를 중간 시점으로 설정
        start = datetime(2024, 1, 1, 10, 0, tzinfo=UTC)
        total_saved = candle_service.collect_minute1_candles(sample_ticker, start=start, batch_size=10, mode=CollectMode.FULL)

        # Then: start 이후 데이터만 저장됨
        assert total_saved == 1


class TestCollectMinute1CandlesTimezoneConversion:
    """start/to 파라미터의 타임존 변환 테스트."""

    def test_converts_kst_start_to_utc(
            self,
            candle_service: CandleService,
            minute1_repo: CandleMinute1Repository,
            sample_ticker: Ticker,
    ):
        """KST timezone이 포함된 start는 UTC로 변환되어 필터링에 사용된다."""
        from zoneinfo import ZoneInfo

        kst = ZoneInfo("Asia/Seoul")

        # Given: API가 반환하는 데이터 (UTC 10:00 = KST 19:00)
        api_data = create_common_candle_df(
            timestamps=[datetime(2024, 1, 1, 10, 0, tzinfo=UTC)],  # UTC 10:00
            local_times=[datetime(2024, 1, 1, 19, 0)],
            opens=[50000000.0],
            highs=[51000000.0],
            lows=[49000000.0],
            closes=[50500000.0],
            volumes=[10.0],
        )

        empty_df = pd.DataFrame()
        candle_service._query_service.get_candles.side_effect = [api_data, empty_df]

        # When: start를 KST 19:00 (= UTC 10:00)으로 설정
        # 이 시점 이후 데이터만 수집해야 함 → 10:00 데이터는 포함됨
        start_kst = datetime(2024, 1, 1, 19, 0, tzinfo=kst)
        total_saved = candle_service.collect_minute1_candles(
            sample_ticker, start=start_kst, batch_size=10, mode=CollectMode.FULL
        )

        # Then: start와 같은 시점 데이터가 포함됨 (>= 조건)
        assert total_saved == 1

    def test_filters_correctly_with_kst_start(
            self,
            candle_service: CandleService,
            minute1_repo: CandleMinute1Repository,
            sample_ticker: Ticker,
    ):
        """KST timezone start로 올바르게 필터링된다."""
        from zoneinfo import ZoneInfo

        kst = ZoneInfo("Asia/Seoul")

        # Given: API가 반환하는 데이터
        # UTC 09:00 (= KST 18:00), UTC 10:00 (= KST 19:00)
        api_data = create_common_candle_df(
            timestamps=[
                datetime(2024, 1, 1, 9, 0, tzinfo=UTC),  # UTC 09:00 = KST 18:00
                datetime(2024, 1, 1, 10, 0, tzinfo=UTC),  # UTC 10:00 = KST 19:00
            ],
            local_times=[
                datetime(2024, 1, 1, 18, 0),
                datetime(2024, 1, 1, 19, 0),
            ],
            opens=[49000000.0, 50000000.0],
            highs=[50000000.0, 51000000.0],
            lows=[48000000.0, 49000000.0],
            closes=[49500000.0, 50500000.0],
            volumes=[8.0, 10.0],
        )

        empty_df = pd.DataFrame()
        candle_service._query_service.get_candles.side_effect = [api_data, empty_df]

        # When: start를 KST 18:30 (= UTC 09:30)으로 설정
        # UTC 09:30 이후 데이터만 → UTC 10:00만 포함
        start_kst = datetime(2024, 1, 1, 18, 30, tzinfo=kst)
        total_saved = candle_service.collect_minute1_candles(
            sample_ticker, start=start_kst, batch_size=10, mode=CollectMode.FULL
        )

        # Then: UTC 10:00 데이터만 저장됨
        assert total_saved == 1

        latest = minute1_repo.get_latest_candle(sample_ticker.id)
        assert latest is not None
        # UTC 10:00
        assert latest.timestamp.replace(tzinfo=UTC) == datetime(2024, 1, 1, 10, 0, tzinfo=UTC)

    def test_converts_kst_to_to_utc(
            self,
            candle_service: CandleService,
            sample_ticker: Ticker,
    ):
        """KST timezone이 포함된 to는 UTC로 변환되어 API 호출에 사용된다."""
        from zoneinfo import ZoneInfo

        kst = ZoneInfo("Asia/Seoul")

        # Given: 빈 데이터 반환
        empty_df = pd.DataFrame()
        candle_service._query_service.get_candles.return_value = empty_df

        # When: to를 KST 19:00 (= UTC 10:00)으로 설정
        to_kst = datetime(2024, 1, 1, 19, 0, tzinfo=kst)
        candle_service.collect_minute1_candles(
            sample_ticker, to=to_kst, batch_size=10, mode=CollectMode.FULL
        )

        # Then: API 호출 시 end_time이 UTC timezone으로 변환되어 전달됨
        call_kwargs = candle_service._query_service.get_candles.call_args.kwargs
        actual_end_time = call_kwargs["end_time"]

        # timezone이 UTC여야 함
        assert actual_end_time.tzinfo == UTC
        # 시간이 UTC 10:00 (= KST 19:00)이어야 함
        assert actual_end_time == datetime(2024, 1, 1, 10, 0, tzinfo=UTC)

    def test_naive_datetime_treated_as_utc(
            self,
            candle_service: CandleService,
            sample_ticker: Ticker,
    ):
        """naive datetime은 UTC로 간주된다."""
        # Given: 빈 데이터 반환
        empty_df = pd.DataFrame()
        candle_service._query_service.get_candles.return_value = empty_df

        # When: naive datetime 전달
        to_naive = datetime(2024, 1, 1, 10, 0)  # naive (tzinfo=None)
        candle_service.collect_minute1_candles(
            sample_ticker, to=to_naive, batch_size=10, mode=CollectMode.FULL
        )

        # Then: API 호출 시 UTC aware로 변환됨
        call_kwargs = candle_service._query_service.get_candles.call_args.kwargs
        actual_end_time = call_kwargs["end_time"]

        # UTC 10:00 (aware)
        expected_utc = datetime(2024, 1, 1, 10, 0, tzinfo=UTC)
        assert actual_end_time == expected_utc


class TestCollectMinute1CandlesBatchSize:
    """batch_size 관련 테스트."""

    def test_stops_when_api_returns_less_than_batch_size(
            self,
            candle_service: CandleService,
            sample_ticker: Ticker,
    ):
        """API가 batch_size보다 적은 데이터를 반환하면 루프를 종료한다."""
        # Given: API가 50개만 반환 (batch_size=1000보다 작음)
        data = create_common_candle_df(
            timestamps=[datetime(2024, 1, 1, 10, i, tzinfo=UTC) for i in range(50)],
            local_times=[datetime(2024, 1, 1, 19, i) for i in range(50)],
            opens=[50000000.0] * 50,
            highs=[51000000.0] * 50,
            lows=[49000000.0] * 50,
            closes=[50500000.0] * 50,
            volumes=[10.0] * 50,
        )
        candle_service._query_service.get_candles.return_value = data

        # When: batch_size=1000으로 호출
        result = candle_service.collect_minute1_candles(
            sample_ticker, batch_size=1000, mode=CollectMode.FULL
        )

        # Then: 1번만 호출되고 종료 (무한 루프 아님)
        assert candle_service._query_service.get_candles.call_count == 1
        assert result == 50
