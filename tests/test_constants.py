"""상수 정의 테스트."""

from zoneinfo import ZoneInfo

from src.constants import TimeZone


class TestTimeZoneTz:
    """TimeZone.tz 프로퍼티 테스트."""

    def test_timezone_tz_returns_zoneinfo(self):
        """TimeZone.tz가 올바른 ZoneInfo를 반환한다."""
        assert TimeZone.SEOUL.tz == ZoneInfo("Asia/Seoul")
        assert TimeZone.UTC.tz == ZoneInfo("UTC")
        assert TimeZone.NEW_YORK.tz == ZoneInfo("America/New_York")
