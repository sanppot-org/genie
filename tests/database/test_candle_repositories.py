"""Tests for candle repositories."""

from datetime import UTC, datetime

from src.database.candle_repositories import CandleDailyRepository, CandleMinute1Repository
from src.database.models import CandleDaily, CandleMinute1


class TestCandleMinute1Repository:
    """CandleMinute1Repository 테스트."""

    def test_get_candles_returns_candles_within_date_range(self, minute1_repo: CandleMinute1Repository):
        """get_candles로 기간 내 캔들 조회."""
        # Given
        candles = [
            CandleMinute1(
                timestamp=datetime(2024, 1, 1, 9, 0, tzinfo=UTC),
                localtime=datetime(2024, 1, 1, 18, 0),
                ticker="KRW-BTC",
                open=50000000,
                high=51000000,
                low=49000000,
                close=50500000,
                volume=10.5,
            ),
            CandleMinute1(
                timestamp=datetime(2024, 1, 1, 9, 1, tzinfo=UTC),
                localtime=datetime(2024, 1, 1, 18, 1),
                ticker="KRW-BTC",
                open=50500000,
                high=51500000,
                low=50000000,
                close=51000000,
                volume=12.3,
            ),
            CandleMinute1(
                timestamp=datetime(2024, 1, 1, 9, 2, tzinfo=UTC),
                localtime=datetime(2024, 1, 1, 18, 2),
                ticker="KRW-BTC",
                open=51000000,
                high=52000000,
                low=50500000,
                close=51500000,
                volume=15.2,
            ),
        ]
        minute1_repo.bulk_upsert(candles)

        # When
        result = minute1_repo.get_candles(
            ticker="KRW-BTC",
            start_datetime=datetime(2024, 1, 1, 9, 0, tzinfo=UTC),
            end_datetime=datetime(2024, 1, 1, 9, 1, tzinfo=UTC),
        )

        # Then
        assert len(result) == 2
        # SQLite는 timezone 정보를 저장하지 않으므로 naive datetime으로 비교
        assert result[0].timestamp.replace(tzinfo=UTC) == datetime(2024, 1, 1, 9, 0, tzinfo=UTC)
        assert result[1].timestamp.replace(tzinfo=UTC) == datetime(2024, 1, 1, 9, 1, tzinfo=UTC)

    def test_get_latest_candle_returns_most_recent_candle(self, minute1_repo: CandleMinute1Repository):
        """get_latest_candle로 최신 캔들 조회."""
        # Given
        candles = [
            CandleMinute1(
                timestamp=datetime(2024, 1, 1, 9, 0, tzinfo=UTC),
                localtime=datetime(2024, 1, 1, 18, 0),
                ticker="KRW-BTC",
                open=50000000,
                high=51000000,
                low=49000000,
                close=50500000,
                volume=10.5,
            ),
            CandleMinute1(
                timestamp=datetime(2024, 1, 1, 9, 1, tzinfo=UTC),
                localtime=datetime(2024, 1, 1, 18, 1),
                ticker="KRW-BTC",
                open=50500000,
                high=51500000,
                low=50000000,
                close=51000000,
                volume=12.3,
            ),
        ]
        minute1_repo.bulk_upsert(candles)

        # When
        result = minute1_repo.get_latest_candle("KRW-BTC")

        # Then
        assert result is not None
        # SQLite는 timezone 정보를 저장하지 않으므로 naive datetime으로 비교
        assert result.timestamp.replace(tzinfo=UTC) == datetime(2024, 1, 1, 9, 1, tzinfo=UTC)
        assert result.close == 51000000

    def test_get_latest_candle_returns_none_when_no_data(self, minute1_repo: CandleMinute1Repository):
        """데이터 없을 때 get_latest_candle은 None 반환."""
        # When
        result = minute1_repo.get_latest_candle("KRW-BTC")

        # Then
        assert result is None

    def test_bulk_upsert_inserts_new_candles(self, minute1_repo: CandleMinute1Repository):
        """bulk_upsert로 새 캔들 삽입."""
        # Given
        candles = [
            CandleMinute1(
                timestamp=datetime(2024, 1, 1, 9, 0, tzinfo=UTC),
                localtime=datetime(2024, 1, 1, 18, 0),
                ticker="KRW-BTC",
                open=50000000,
                high=51000000,
                low=49000000,
                close=50500000,
                volume=10.5,
            ),
            CandleMinute1(
                timestamp=datetime(2024, 1, 1, 9, 1, tzinfo=UTC),
                localtime=datetime(2024, 1, 1, 18, 1),
                ticker="KRW-BTC",
                open=50500000,
                high=51500000,
                low=50000000,
                close=51000000,
                volume=12.3,
            ),
        ]

        # When
        minute1_repo.bulk_upsert(candles)

        # Then
        result = minute1_repo.get_candles(
            ticker="KRW-BTC",
            start_datetime=datetime(2024, 1, 1, 9, 0, tzinfo=UTC),
            end_datetime=datetime(2024, 1, 1, 9, 1, tzinfo=UTC),
        )
        assert len(result) == 2

    def test_bulk_upsert_updates_existing_candles(self, minute1_repo: CandleMinute1Repository):
        """bulk_upsert로 기존 캔들 업데이트."""
        # Given
        existing = [
            CandleMinute1(
                timestamp=datetime(2024, 1, 1, 9, 0, tzinfo=UTC),
                localtime=datetime(2024, 1, 1, 18, 0),
                ticker="KRW-BTC",
                open=50000000,
                high=51000000,
                low=49000000,
                close=50500000,
                volume=10.5,
            )
        ]
        minute1_repo.bulk_upsert(existing)

        updated_candle = CandleMinute1(
            timestamp=datetime(2024, 1, 1, 9, 0, tzinfo=UTC),
            localtime=datetime(2024, 1, 1, 18, 0),
            ticker="KRW-BTC",
            open=50000000,
            high=52000000,  # 변경
            low=49000000,
            close=51500000,  # 변경
            volume=15.0,  # 변경
        )

        # When
        minute1_repo.bulk_upsert([updated_candle])

        # Then
        result = minute1_repo.get_latest_candle("KRW-BTC")
        assert result is not None
        assert result.high == 52000000
        assert result.close == 51500000
        assert result.volume == 15.0

    def test_get_candles_with_default_dates(self, minute1_repo: CandleMinute1Repository):
        """get_candles를 기본값(최근 하루)으로 호출."""
        # Given
        from datetime import timedelta
        from zoneinfo import ZoneInfo
        now = datetime.now(UTC)
        kst_now_2h = now.astimezone(ZoneInfo("Asia/Seoul")) - timedelta(hours=2)
        kst_now_1h = now.astimezone(ZoneInfo("Asia/Seoul")) - timedelta(hours=1)
        candles = [
            CandleMinute1(
                timestamp=now - timedelta(hours=2),
                localtime=kst_now_2h.replace(tzinfo=None),
                ticker="KRW-BTC",
                open=50000000,
                high=51000000,
                low=49000000,
                close=50500000,
                volume=10.5,
            ),
            CandleMinute1(
                timestamp=now - timedelta(hours=1),
                localtime=kst_now_1h.replace(tzinfo=None),
                ticker="KRW-BTC",
                open=50500000,
                high=51500000,
                low=50000000,
                close=51000000,
                volume=12.3,
            ),
        ]
        minute1_repo.bulk_upsert(candles)

        # When - start_date, end_date를 지정하지 않음
        result = minute1_repo.get_candles(ticker="KRW-BTC")

        # Then - 최근 하루치 데이터가 조회됨
        assert len(result) == 2
        assert result[0].ticker == "KRW-BTC"
        assert result[1].ticker == "KRW-BTC"


class TestCandleDailyRepository:
    """CandleDailyRepository 테스트."""

    def test_get_candles_returns_candles_within_date_range(self, daily_repo: CandleDailyRepository):
        """get_candles로 기간 내 캔들 조회."""
        # Given
        candles = [
            CandleDaily(
                date=datetime(2024, 1, 1).date(),
                ticker="KRW-BTC",
                open=50000000,
                high=52000000,
                low=49000000,
                close=51000000,
                volume=1000.5,
            ),
            CandleDaily(
                date=datetime(2024, 1, 2).date(),
                ticker="KRW-BTC",
                open=51000000,
                high=53000000,
                low=50000000,
                close=52000000,
                volume=1200.3,
            ),
            CandleDaily(
                date=datetime(2024, 1, 3).date(),
                ticker="KRW-BTC",
                open=52000000,
                high=54000000,
                low=51000000,
                close=53000000,
                volume=1500.2,
            ),
        ]
        daily_repo.bulk_upsert(candles)

        # When
        result = daily_repo.get_candles(
            ticker="KRW-BTC",
            start_datetime=datetime(2024, 1, 1, tzinfo=UTC),
            end_datetime=datetime(2024, 1, 2, tzinfo=UTC),
        )

        # Then
        assert len(result) == 2
        assert result[0].date == datetime(2024, 1, 1).date()
        assert result[1].date == datetime(2024, 1, 2).date()

    def test_get_latest_candle_returns_most_recent_candle(self, daily_repo: CandleDailyRepository):
        """get_latest_candle로 최신 캔들 조회."""
        # Given
        candles = [
            CandleDaily(
                date=datetime(2024, 1, 1).date(),
                ticker="KRW-BTC",
                open=50000000,
                high=52000000,
                low=49000000,
                close=51000000,
                volume=1000.5,
            ),
            CandleDaily(
                date=datetime(2024, 1, 2).date(),
                ticker="KRW-BTC",
                open=51000000,
                high=53000000,
                low=50000000,
                close=52000000,
                volume=1200.3,
            ),
        ]
        daily_repo.bulk_upsert(candles)

        # When
        result = daily_repo.get_latest_candle("KRW-BTC")

        # Then
        assert result is not None
        assert result.date == datetime(2024, 1, 2).date()
        assert result.close == 52000000

    def test_get_latest_candle_returns_none_when_no_data(self, daily_repo: CandleDailyRepository):
        """데이터 없을 때 get_latest_candle은 None 반환."""
        # When
        result = daily_repo.get_latest_candle("KRW-BTC")

        # Then
        assert result is None

    def test_bulk_upsert_inserts_new_candles(self, daily_repo: CandleDailyRepository):
        """bulk_upsert로 새 캔들 삽입."""
        # Given
        candles = [
            CandleDaily(
                date=datetime(2024, 1, 1).date(),
                ticker="KRW-BTC",
                open=50000000,
                high=52000000,
                low=49000000,
                close=51000000,
                volume=1000.5,
            ),
            CandleDaily(
                date=datetime(2024, 1, 2).date(),
                ticker="KRW-BTC",
                open=51000000,
                high=53000000,
                low=50000000,
                close=52000000,
                volume=1200.3,
            ),
        ]

        # When
        daily_repo.bulk_upsert(candles)

        # Then
        result = daily_repo.get_candles(
            ticker="KRW-BTC",
            start_datetime=datetime(2024, 1, 1, tzinfo=UTC),
            end_datetime=datetime(2024, 1, 2, tzinfo=UTC),
        )
        assert len(result) == 2

    def test_bulk_upsert_updates_existing_candles(self, daily_repo: CandleDailyRepository):
        """bulk_upsert로 기존 캔들 업데이트."""
        # Given
        existing = [
            CandleDaily(
                date=datetime(2024, 1, 1).date(),
                ticker="KRW-BTC",
                open=50000000,
                high=52000000,
                low=49000000,
                close=51000000,
                volume=1000.5,
            )
        ]
        daily_repo.bulk_upsert(existing)

        updated_candle = CandleDaily(
            date=datetime(2024, 1, 1).date(),
            ticker="KRW-BTC",
            open=50000000,
            high=54000000,  # 변경
            low=49000000,
            close=53000000,  # 변경
            volume=1500.0,  # 변경
        )

        # When
        daily_repo.bulk_upsert([updated_candle])

        # Then
        result = daily_repo.get_latest_candle("KRW-BTC")
        assert result is not None
        assert result.high == 54000000
        assert result.close == 53000000
        assert result.volume == 1500.0

    def test_get_candles_with_default_dates(self, daily_repo: CandleDailyRepository):
        """get_candles를 기본값(최근 하루)으로 호출."""
        # Given
        from datetime import timedelta
        now = datetime.now()
        candles = [
            CandleDaily(
                date=(now - timedelta(days=1)).date(),
                ticker="KRW-BTC",
                open=50000000,
                high=52000000,
                low=49000000,
                close=51000000,
                volume=1000.5,
            ),
            CandleDaily(
                date=now.date(),
                ticker="KRW-BTC",
                open=51000000,
                high=53000000,
                low=50000000,
                close=52000000,
                volume=1200.3,
            ),
        ]
        daily_repo.bulk_upsert(candles)

        # When - start_date, end_date를 지정하지 않음
        result = daily_repo.get_candles(ticker="KRW-BTC")

        # Then - 최근 하루치 데이터가 조회됨
        assert len(result) == 2
        assert result[0].ticker == "KRW-BTC"
        assert result[1].ticker == "KRW-BTC"
