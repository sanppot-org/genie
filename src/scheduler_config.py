"""스케줄러 설정 모델"""

from collections.abc import Callable
from typing import Any

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from pydantic import BaseModel


class ScheduleConfig(BaseModel):
    """스케줄 설정을 관리하는 Pydantic 모델

    APScheduler의 add_job에 필요한 파라미터들을 타입 안전하게 관리합니다.

    Attributes:
        func: 실행할 함수
        trigger: CronTrigger 또는 IntervalTrigger
        id: 스케줄 식별자
        name: 스케줄 이름
        replace_existing: 기존 스케줄을 대체할지 여부 (기본값: True)
    """

    model_config = {"arbitrary_types_allowed": True}

    func: Callable
    trigger: CronTrigger | IntervalTrigger
    id: str
    name: str
    replace_existing: bool = True

    def to_add_job_kwargs(self) -> dict[str, Any]:
        """APScheduler의 add_job에 전달할 kwargs를 생성

        Returns:
            add_job 메서드에 전달할 수 있는 딕셔너리
        """
        return {
            "func": self.func,
            "trigger": self.trigger,
            "id": self.id,
            "name": self.name,
            "replace_existing": self.replace_existing,
        }
