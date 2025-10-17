"""전략 베이스 클래스

모든 트레이딩 전략이 구현해야 하는 인터페이스를 정의합니다.
"""

from abc import ABC, abstractmethod


class BaseStrategy(ABC):
    """
    트레이딩 전략 베이스 클래스

    모든 트레이딩 전략이 구현해야 하는 공통 인터페이스입니다.
    데이터 수집, 시그널 계산, 매수/매도 실행 등 모든 전략 로직을 담당합니다.
    """

    @abstractmethod
    def run(self) -> None:
        """
        전략 실행

        전략의 스케줄링 로직을 구현합니다.
        각 전략은 자신의 요구사항에 맞는 스케줄러를 구현해야 합니다.
        """
        pass
