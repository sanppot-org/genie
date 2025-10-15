"""전략 공통 유틸리티 함수"""

from datetime import datetime, time
from zoneinfo import ZoneInfo


def is_morning(now: datetime | None = None) -> bool:
    """
    현재 시간이 한국 시간(KST) 기준 오전(00:00~12:00)인지 확인

    Args:
        now: 확인할 시간 (None이면 현재 시간 사용)

    Returns:
        오전이면 True, 아니면 False
    """
    if now is None:
        now = datetime.now(ZoneInfo("Asia/Seoul"))

    # 타임존이 없는 datetime이면 KST로 간주
    if now.tzinfo is None:
        now = now.replace(tzinfo=ZoneInfo("Asia/Seoul"))
    else:
        # 다른 타임존이면 KST로 변환
        now = now.astimezone(ZoneInfo("Asia/Seoul"))

    # 00:00 <= 현재 시간 < 12:00
    morning_start = time(0, 0)
    morning_end = time(12, 0)

    return morning_start <= now.time() < morning_end
