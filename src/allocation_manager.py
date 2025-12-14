from datetime import datetime
import json
import logging
from pathlib import Path

from pydantic import BaseModel, Field

from src.common.slack.client import SlackClient
from src.constants import DEFAULT_CACHE_DIR, KST, UTF_8
from src.upbit.upbit_api import UpbitAPI

logger = logging.getLogger(__name__)


class AllocatedAmount(BaseModel):
    """할당 상태 모델"""
    allocated_balance_per_ticker: float = Field(...)
    last_allocation_datetime: datetime = Field(default_factory=lambda: datetime.now(KST))


class AllocatedBalanceProvider:
    """일일 자금 할당 관리 클래스"""

    def __init__(
            self,
            slack_client: SlackClient,
            upbit_api: UpbitAPI,
            state_file_path: Path | None = None,
            allocation_hour: int | None = None,
    ) -> None:
        """
        Args:
            slack_client: Slack 알림 클라이언트
            upbit_api: Upbit API 클라이언트
            state_file_path: 할당 상태를 저장할 JSON 파일 경로
            allocation_hour: 자금을 할당할 시간 (0-23)
        """
        self.state_file_path = state_file_path or Path(DEFAULT_CACHE_DIR) / "allocated_balance.json"
        self.allocation_hour = allocation_hour or 23  # 오후 11시에 자금 할당
        self.upbit_api = upbit_api
        self.slack_client = slack_client

    def get_allocated_amount(self) -> float:
        """
        일일 자금 할당 관리 - 필요시 재할당, 아니면 기존 값 반환

        Returns:
            티커당 할당된 금액
        """
        state = self._load_state()
        now = datetime.now(KST)
        today_allocation_time = now.replace(hour=self.allocation_hour, minute=0, second=0, microsecond=0)

        if not state or state.last_allocation_datetime < today_allocation_time <= now:
            amount = self.upbit_api.get_available_amount()
            self.slack_client.send_log(f"업비트 할당 금액을 업데이트 완료. amount: {amount}")
            self._save_state(amount)
            return amount

        return state.allocated_balance_per_ticker

    def _load_state(self) -> AllocatedAmount | None:
        """할당 상태 파일 로드"""
        try:
            with open(self.state_file_path, encoding=UTF_8) as f:
                data = json.load(f)
                return AllocatedAmount.model_validate(data)
        except Exception:
            return None

    def _save_state(self, allocated_balance: float) -> None:
        """할당 상태 파일 저장"""
        try:
            state = AllocatedAmount(allocated_balance_per_ticker=allocated_balance)

            with open(self.state_file_path, "w", encoding=UTF_8) as f:
                json.dump(state.model_dump(mode="json"), f, indent=2, ensure_ascii=False)

        except OSError as e:
            logger.error(f"할당 상태 저장 실패: {e}")
