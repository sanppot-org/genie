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
        misfire_grace_time: 늦은 실행 허용 초. None이면 스케줄러 job_defaults(60초) 사용.
            드물게 도는 장시간 잡(분기 백필 등)은 재시작/순간부하로 인한 누락을 막으려 크게 둔다.
    """

    model_config = {"arbitrary_types_allowed": True}

    func: Callable
    trigger: CronTrigger | IntervalTrigger
    id: str
    name: str
    replace_existing: bool = True
    misfire_grace_time: int | None = None

    def to_add_job_kwargs(self) -> dict[str, Any]:
        """APScheduler의 add_job에 전달할 kwargs를 생성

        Returns:
            add_job 메서드에 전달할 수 있는 딕셔너리
        """
        kwargs: dict[str, Any] = {
            "func": self.func,
            "trigger": self.trigger,
            "id": self.id,
            "name": self.name,
            "replace_existing": self.replace_existing,
        }
        if self.misfire_grace_time is not None:
            kwargs["misfire_grace_time"] = self.misfire_grace_time
        return kwargs
