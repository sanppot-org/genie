"""backtrader 데이터 피드 설정 인터페이스"""

from abc import ABC, abstractmethod

import backtrader as bt


class DataFeedConfig(ABC):
    """backtrader 데이터 피드 생성 인터페이스"""

    @abstractmethod
    def to_data_feed(self) -> bt.AbstractDataBase:
        """backtrader 데이터 피드로 변환

        Returns:
            bt.AbstractDataBase: backtrader 데이터 피드
        """
        pass
