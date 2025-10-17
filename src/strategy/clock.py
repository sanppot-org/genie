"""시간 관리 클래스

시간 관련 로직을 중앙화하고 테스트 용이성을 높이기 위한 Clock 추상화입니다.
"""

from abc import ABC, abstractmethod
from datetime import date, datetime, time
from zoneinfo import ZoneInfo


class Clock(ABC):
    """시간 제공 인터페이스"""

    def __init__(self, timezone: ZoneInfo | None = None) -> None:
        """
        Args:
            timezone: 사용할 타임존 (기본값: KST)
        """
        self.timezone = timezone if timezone is not None else ZoneInfo("Asia/Seoul")

    @abstractmethod
    def now(self) -> datetime:
        """
        현재 시간을 지정된 타임존으로 반환

        Returns:
            현재 시간 (지정된 timezone 포함)
        """
        pass

    def today(self) -> date:
        return self.now().date()

    def is_morning(self) -> bool:
        """
        현재 시간이 오전(00:00~12:00 KST)인지 확인

        Returns:
            오전이면 True, 아니면 False
        """
        current_time = self.now()
        morning_start = time(0, 0)
        morning_end = time(12, 0)

        return morning_start <= current_time.time() < morning_end

    def is_afternoon(self) -> bool:
        """
        현재 시간이 오후(12:00~24:00 KST)인지 확인

        Returns:
            오후이면 True, 아니면 False
        """
        return not self.is_morning()


class SystemClock(Clock):
    """실제 시스템 시간을 사용하는 Clock 구현"""

    def now(self) -> datetime:
        """
        실제 시스템의 현재 시간을 지정된 타임존으로 반환

        Returns:
            현재 시간 (지정된 timezone 포함)
        """
        return datetime.now(self.timezone)


class FixedClock(Clock):
    """테스트용 고정 시간을 제공하는 Clock 구현"""

    def __init__(self, fixed_time: datetime, timezone: ZoneInfo | None = None) -> None:
        """
        Args:
            fixed_time: 고정할 시간 (timezone 없으면 지정된 timezone으로 간주)
            timezone: 사용할 타임존 (기본값: KST)
        """
        super().__init__(timezone if timezone is not None else None)
        if fixed_time.tzinfo is None:
            self._fixed_time = fixed_time.replace(tzinfo=self.timezone)
        else:
            # 다른 타임존이면 지정된 타임존으로 변환
            self._fixed_time = fixed_time.astimezone(self.timezone)

    def now(self) -> datetime:
        """
        고정된 시간을 반환

        Returns:
            고정된 시간 (지정된 timezone 포함)
        """
        return self._fixed_time

    def set_time(self, new_time: datetime) -> None:
        """
        고정 시간 변경

        Args:
            new_time: 새로운 고정 시간
        """
        if new_time.tzinfo is None:
            self._fixed_time = new_time.replace(tzinfo=self.timezone)
        else:
            self._fixed_time = new_time.astimezone(self.timezone)
