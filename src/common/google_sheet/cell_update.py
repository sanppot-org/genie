"""Google Sheets 셀 업데이트 모델"""
from datetime import datetime

from pydantic import BaseModel, Field

VALUE_COL = 2
LAST_MODIFIED_AT_COL = 3


class CellUpdate(BaseModel):
    """
    Google Sheets 셀 업데이트를 위한 데이터 모델

    Attributes:
        row: 행 번호 (1부터 시작)
        col: 열 번호 (1부터 시작)
        value: 셀에 입력할 값 (문자열, 숫자, 정수)

    Examples:
        >>> cell_update = CellUpdate(row=1, col=2, value="test")
        >>> cell_update.to_tuple()
        (1, 2, 'test')
    """

    row: int = Field(gt=0, description="행 번호 (1부터 시작)")
    col: int = Field(gt=0, description="열 번호 (1부터 시작)")
    value: str | float | int = Field(description="셀에 입력할 값")

    def to_tuple(self) -> tuple[int, int, str | float | int]:
        """
        (row, col, value) 튜플로 변환

        Returns:
            tuple[int, int, str | float | int]: (행, 열, 값) 튜플

        Examples:
            >>> cell_update = CellUpdate(row=3, col=5, value="data")
            >>> cell_update.to_tuple()
            (3, 5, 'data')
        """
        return self.row, self.col, self.value

    @staticmethod
    def data(row: int, value: int | str | float) -> "CellUpdate":
        return CellUpdate(row=row, col=VALUE_COL, value=value)

    @staticmethod
    def now(row: int) -> "CellUpdate":
        return CellUpdate(row=row, col=LAST_MODIFIED_AT_COL, value=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
