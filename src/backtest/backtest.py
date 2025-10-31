"""
Backtrader simple example
Reference: https://www.backtrader.com/docu/quickstart/quickstart
"""

import backtrader as bt
import pandas as pd

from src.backtest.backtest_builder import BacktestBuilder
from src.backtest.commission_config import CommissionConfig
from src.backtest.sizer_config import SizerConfig
from src.backtest.strategy.morning_afternoon_strategy import MorningAfternoonStrategy
from src.upbit.upbit_api import CandleInterval, UpbitAPI


def prepare_data(ticker: str = "KRW-BTC", interval: CandleInterval = CandleInterval.DAY, count: int = 200) -> pd.DataFrame:
    """
    백테스트를 위한 데이터 준비

    Args:
        ticker: 티커 코드 (기본값: 'KRW-BTC')
        interval: 캔들 간격 (기본값: CandleInterval.DAY)
        count: 조회할 캔들 개수 (기본값: 200)

    Returns:
        backtrader가 사용할 수 있는 형식의 DataFrame
    """
    # Upbit API로 데이터 가져오기
    df = UpbitAPI.get_candles(ticker=ticker, interval=interval, count=count)

    if df.empty:
        raise ValueError("데이터를 가져올 수 없습니다")

    # backtrader는 컬럼명을 소문자로 사용
    # index는 datetime이어야 함 (이미 설정되어 있음)
    df.columns = [col.lower() for col in df.columns]

    # backtrader는 최신 데이터가 마지막에 와야 함
    df = df.sort_index()

    return df


def load_csv_data(csv_path: str) -> pd.DataFrame:
    """
    CSV 파일에서 백테스트를 위한 데이터 준비

    Args:
        csv_path: CSV 파일 경로 (예: '~/data_gd/hour/KRW-BTC_minute60_candles_2017-09-25_2025-10-21.csv')

    Returns:
        backtrader가 사용할 수 있는 형식의 DataFrame
    """
    import os

    # 홈 디렉토리 경로 확장
    expanded_path = os.path.expanduser(csv_path)

    # CSV 파일 읽기
    try:
        df = pd.read_csv(expanded_path)
    except pd.errors.EmptyDataError as e:
        raise ValueError(f"CSV 파일이 비어있습니다: {csv_path}") from e

    if df.empty:
        raise ValueError(f"CSV 파일이 비어있습니다: {csv_path}")

    # datetime 컬럼을 index로 설정
    # CSV 파일의 datetime 컬럼명에 따라 조정 필요
    if 'candle_date_time_kst' in df.columns:
        df['candle_date_time_kst'] = pd.to_datetime(df['candle_date_time_kst'])
        df.set_index('candle_date_time_kst', inplace=True)
    elif 'datetime' in df.columns:
        df['datetime'] = pd.to_datetime(df['datetime'])
        df.set_index('datetime', inplace=True)
    else:
        # 첫 번째 컬럼을 datetime으로 가정
        df.iloc[:, 0] = pd.to_datetime(df.iloc[:, 0])
        df.set_index(df.columns[0], inplace=True)

    # backtrader는 컬럼명을 소문자로 사용
    df.columns = [col.lower() for col in df.columns]

    # backtrader는 최신 데이터가 마지막에 와야 함
    df = df.sort_index()

    return df


def create_csv_data_feed(csv_path: str) -> bt.feeds.PandasData:
    """
    CSV 파일로부터 데이터를 가져와 backtrader 데이터 피드 생성

    Args:
        csv_path: CSV 파일 경로 (예: '~/data_gd/hour/KRW-BTC_minute60_candles_2017-09-25_2025-10-21.csv')

    Returns:
        backtrader PandasData 피드
    """
    df = load_csv_data(csv_path)
    return bt.feeds.PandasData(dataname=df)


def create_upbit_data_feed(
        ticker: str = "KRW-BTC",
        interval: CandleInterval = CandleInterval.DAY,
        count: int = 200
) -> bt.feeds.PandasData:
    """
    Upbit API로부터 데이터를 가져와 backtrader 데이터 피드 생성

    Args:
        ticker: 티커 코드 (기본값: 'KRW-BTC')
        interval: 캔들 간격 (기본값: CandleInterval.DAY)
        count: 조회할 캔들 개수 (기본값: 200)

    Returns:
        backtrader PandasData 피드
    """
    df = prepare_data(ticker=ticker, interval=interval, count=count)
    return bt.feeds.PandasData(dataname=df)

"""
1. 전략 구현
2. 데이터 가져오기
- 전략의 구현은 데이터의 구조에 강하게 결합된다. 예를들어 데이터가 60분 봉이라면 60분봉을 가정하고 로직을 짜야 한다.
"""

if __name__ == "__main__":
    # Example 1: Basic backtest with external data
    data_feed = create_csv_data_feed('~/invest/data/KRW-BTC_minute60_candles_2017-09-25_2025-10-21.csv')

    result = (
        BacktestBuilder()
        .add_data(data_feed)
        .with_commission(CommissionConfig.stock(0.0005))  # Upbit 수수료 0.05%
        .with_initial_cash(200_000_000)
        .with_sizer(SizerConfig.percent(95))  # 95%로 변경 (수수료 고려)
        # .with_slippage()
        .with_strategy(strategy_class=MorningAfternoonStrategy)
        .with_analyzer(bt.analyzers.SharpeRatio, "sharpe")
        .with_analyzer(bt.analyzers.DrawDown, "drawdown")
        .with_analyzer(bt.analyzers.Returns, "returns")
        .build()
        .run()
    )

    print("\n=== Analysis Results ===")
    strategy = result[0]
    print(f"Sharpe Ratio: {strategy.analyzers.sharpe.get_analysis()}")
    print(f"DrawDown: {strategy.analyzers.drawdown.get_analysis()}")
    print(f"Returns: {strategy.analyzers.returns.get_analysis()}")
