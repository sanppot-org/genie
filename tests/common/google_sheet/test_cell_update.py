"""CellUpdate 모델 테스트"""

from pydantic import ValidationError
import pytest

from src.common.google_sheet.cell_update import CellUpdate


class TestCellUpdate:
    """CellUpdate 모델 테스트"""

    def test_정상적인_값으로_생성_성공(self):
        """정상적인 row, col, value로 CellUpdate 생성"""
        cell_update = CellUpdate(row=1, col=2, value="test")
        assert cell_update.row == 1
        assert cell_update.col == 2
        assert cell_update.value == "test"

    def test_숫자_값으로_생성_성공(self):
        """숫자 value로 CellUpdate 생성"""
        cell_update = CellUpdate(row=1, col=2, value=123.45)
        assert cell_update.row == 1
        assert cell_update.col == 2
        assert cell_update.value == 123.45

    def test_정수_값으로_생성_성공(self):
        """정수 value로 CellUpdate 생성"""
        cell_update = CellUpdate(row=1, col=2, value=100)
        assert cell_update.row == 1
        assert cell_update.col == 2
        assert cell_update.value == 100

    def test_row가_0이하일때_검증_에러(self):
        """row가 0 이하일 때 ValidationError 발생"""
        with pytest.raises(ValidationError):
            CellUpdate(row=0, col=1, value="test")

        with pytest.raises(ValidationError):
            CellUpdate(row=-1, col=1, value="test")

    def test_col이_0이하일때_검증_에러(self):
        """col이 0 이하일 때 ValidationError 발생"""
        with pytest.raises(ValidationError):
            CellUpdate(row=1, col=0, value="test")

        with pytest.raises(ValidationError):
            CellUpdate(row=1, col=-1, value="test")

    def test_to_tuple_메서드(self):
        """to_tuple 메서드가 (row, col, value) 튜플 반환"""
        cell_update = CellUpdate(row=3, col=5, value="data")
        result = cell_update.to_tuple()
        assert result == (3, 5, "data")
        assert isinstance(result, tuple)
        assert len(result) == 3
