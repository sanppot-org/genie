"""업비트 CandleData 모델 테스트"""
import pandas as pd

from src.upbit.model.candle import CandleData


class TestCandleData:
    """CandleData 모델 테스트"""

    def test_CandleData_from_dataframe_row(self):
        """DataFrame row로부터 CandleData를 생성할 수 있다"""
        row = pd.Series({
            'open': 95000000,
            'high': 96000000,
            'low': 94000000,
            'close': 95500000,
            'volume': 15.75,
            'value': 1503750000.0
        })

        candle = CandleData.from_dataframe_row(row)

        assert candle.open == 95000000
        assert candle.high == 96000000
        assert candle.low == 94000000
        assert candle.close == 95500000
        assert candle.volume == 15.75
        assert candle.value == 1503750000.0
