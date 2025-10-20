"""Clock 클래스 테스트"""

import datetime
from zoneinfo import ZoneInfo

from src.common.clock import FixedClock, SystemClock


class TestSystemClock:
    """SystemClock 테스트"""

    def test_now_returns_kst_time(self):
        """now()가 KST 시간을 반환하는지 확인"""
        clock = SystemClock()
        now = clock.now()

        # KST timezone이 설정되어 있는지 확인
        assert now.tzinfo is not None
        assert now.tzinfo == ZoneInfo("Asia/Seoul")

    def test_system_clock_with_custom_timezone(self):
        """커스텀 타임존을 주입하면 해당 타임존으로 시간을 반환하는지 확인"""
        utc_clock = SystemClock(timezone=ZoneInfo("UTC"))
        now = utc_clock.now()

        # UTC timezone이 설정되어 있는지 확인
        assert now.tzinfo == ZoneInfo("UTC")

    def test_clock_default_timezone_is_kst(self):
        """타임존을 지정하지 않으면 기본값이 KST인지 확인"""
        clock = SystemClock()
        assert clock.timezone == ZoneInfo("Asia/Seoul")

    def test_is_morning_at_morning_time(self):
        """오전 시간대에 is_morning()이 True를 반환하는지 확인"""
        # 고정 시간을 사용하여 테스트
        morning_time = datetime.datetime(2025, 10, 20, 6, 0, 0)
        clock = FixedClock(morning_time)

        assert clock.is_morning() is True

    def test_is_morning_at_afternoon_time(self):
        """오후 시간대에 is_morning()이 False를 반환하는지 확인"""
        afternoon_time = datetime.datetime(2025, 10, 20, 14, 0, 0)
        clock = FixedClock(afternoon_time)

        assert clock.is_morning() is False

    def test_is_afternoon_at_afternoon_time(self):
        """오후 시간대에 is_afternoon()이 True를 반환하는지 확인"""
        afternoon_time = datetime.datetime(2025, 10, 20, 14, 0, 0)
        clock = FixedClock(afternoon_time)

        assert clock.is_afternoon() is True

    def test_is_afternoon_at_morning_time(self):
        """오전 시간대에 is_afternoon()이 False를 반환하는지 확인"""
        morning_time = datetime.datetime(2025, 10, 20, 6, 0, 0)
        clock = FixedClock(morning_time)

        assert clock.is_afternoon() is False


class TestFixedClock:
    """FixedClock 테스트"""

    def test_now_returns_fixed_time(self):
        """now()가 고정된 시간을 반환하는지 확인"""
        fixed_time = datetime.datetime(2025, 10, 20, 10, 30, 45)
        clock = FixedClock(fixed_time)

        now = clock.now()

        assert now.year == 2025
        assert now.month == 10
        assert now.day == 20
        assert now.hour == 10
        assert now.minute == 30
        assert now.second == 45

    def test_now_with_timezone(self):
        """timezone이 있는 시간으로 생성 시 KST로 변환되는지 확인"""
        utc_time = datetime.datetime(2025, 10, 20, 1, 0, 0, tzinfo=ZoneInfo("UTC"))
        clock = FixedClock(utc_time)

        now = clock.now()

        # UTC 01:00 = KST 10:00
        assert now.hour == 10
        assert now.tzinfo == ZoneInfo("Asia/Seoul")

    def test_now_without_timezone(self):
        """timezone이 없는 시간으로 생성 시 KST로 간주되는지 확인"""
        naive_time = datetime.datetime(2025, 10, 20, 10, 0, 0)
        clock = FixedClock(naive_time)

        now = clock.now()

        assert now.hour == 10
        assert now.tzinfo == ZoneInfo("Asia/Seoul")

    def test_fixed_clock_with_custom_timezone(self):
        """커스텀 타임존을 주입하면 해당 타임존으로 시간을 관리하는지 확인"""
        # JST로 고정 시간 생성 (KST보다 0시간 빠름)
        jst_time = datetime.datetime(2025, 10, 20, 10, 0, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
        clock = FixedClock(jst_time, timezone=ZoneInfo("Asia/Tokyo"))

        now = clock.now()

        # JST 타임존으로 시간이 저장되는지 확인
        assert now.hour == 10
        assert now.tzinfo == ZoneInfo("Asia/Tokyo")

    def test_is_morning_boundary_midnight(self):
        """자정(00:00)은 오전인지 확인"""
        midnight = datetime.datetime(2025, 10, 20, 0, 0, 0)
        clock = FixedClock(midnight)

        assert clock.is_morning() is True

    def test_is_morning_boundary_before_noon(self):
        """정오 직전(11:59)은 오전인지 확인"""
        before_noon = datetime.datetime(2025, 10, 20, 11, 59, 59)
        clock = FixedClock(before_noon)

        assert clock.is_morning() is True

    def test_is_morning_boundary_noon(self):
        """정오(12:00)는 오후인지 확인"""
        noon = datetime.datetime(2025, 10, 20, 12, 0, 0)
        clock = FixedClock(noon)

        assert clock.is_morning() is False
        assert clock.is_afternoon() is True

    def test_is_morning_boundary_before_midnight(self):
        """자정 직전(23:59)은 오후인지 확인"""
        before_midnight = datetime.datetime(2025, 10, 20, 23, 59, 59)
        clock = FixedClock(before_midnight)

        assert clock.is_morning() is False
        assert clock.is_afternoon() is True

    def test_set_time(self):
        """set_time()으로 시간을 변경할 수 있는지 확인"""
        initial_time = datetime.datetime(2025, 10, 20, 10, 0, 0)
        clock = FixedClock(initial_time)

        assert clock.now().hour == 10

        # 시간 변경
        new_time = datetime.datetime(2025, 10, 20, 14, 0, 0)
        clock.set_time(new_time)

        assert clock.now().hour == 14

    def test_set_time_with_timezone(self):
        """set_time()에 timezone이 있는 시간 전달 시 KST로 변환되는지 확인"""
        initial_time = datetime.datetime(2025, 10, 20, 10, 0, 0)
        clock = FixedClock(initial_time)

        # UTC 시간으로 변경
        utc_time = datetime.datetime(2025, 10, 20, 5, 0, 0, tzinfo=ZoneInfo("UTC"))
        clock.set_time(utc_time)

        # UTC 05:00 = KST 14:00
        assert clock.now().hour == 14
        assert clock.now().tzinfo == ZoneInfo("Asia/Seoul")
