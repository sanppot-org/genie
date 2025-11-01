"""backtrader PandasData 설정 클래스"""

import backtrader as bt
import pandas as pd

from src.backtest.data_feed.base import DataFeedConfig


class PandasDataFeedConfig(DataFeedConfig):
    """backtrader PandasData 생성을 위한 설정 클래스

    DataFrame을 검증하고 PandasData로 변환하는 책임을 담당합니다.

    Example:
        >>> # DataFrame 준비
        >>> df = pd.DataFrame({
        ...     'open': [100, 101],
        ...     'high': [105, 106],
        ...     'low': [99, 100],
        ...     'close': [103, 104],
        ...     'volume': [1000, 2000]
        ... }, index=pd.DatetimeIndex(['2024-01-01', '2024-01-02']))
        >>>
        >>> # PandasDataFeedConfig 생성
        >>> config = PandasDataFeedConfig.create(df, name='BTC-KRW')
        >>>
        >>> # PandasData로 변환
        >>> data_feed = config.to_data_feed()
    """

    def __init__(
            self,
            data_name: pd.DataFrame,
            name: str = "",
            from_date: pd.Timestamp | None = None,
            to_date: pd.Timestamp | None = None,
            datetime: str | None = None,
    ) -> None:
        """PandasDataFeedConfig 초기화

        Args:
            data_name: 검증되고 정렬된 OHLCV DataFrame
            name: 데이터 피드 이름 (플로팅용)
            from_date: 시작 날짜
            to_date: 종료 날짜
            datetime: datetime 컬럼명 (None이면 index 사용)
        """
        self.data_name = data_name
        self.name = name
        self.from_date = from_date
        self.to_date = to_date
        self.datetime = datetime

    @classmethod
    def create(
            cls,
            df: pd.DataFrame,
            name: str = "",
            from_date: pd.Timestamp | None = None,
            to_date: pd.Timestamp | None = None,
    ) -> "PandasDataFeedConfig":
        """DataFrame으로부터 PandasDataFeedConfig 생성 (팩터리 메서드)

        Args:
            df: OHLCV 데이터가 담긴 DataFrame
                - Datetime: DatetimeIndex 또는 datetime 계열 컬럼 필요
                  (index가 DatetimeIndex 또는 'datetime'/'date' 등의 컬럼 존재)
                - 필수 컬럼: open, high, low, close, volume
                - 선택 컬럼: openinterest
            name: 데이터 피드 이름 (플로팅용)
            from_date: 시작 날짜 (None이면 전체)
            to_date: 종료 날짜 (None이면 전체)

        Returns:
            PandasDataFeedConfig: 검증되고 정렬된 설정 객체

        Raises:
            ValueError: DataFrame 형식이 올바르지 않을 때

        Example:
            >>> # 방법 1: DatetimeIndex 사용
            >>> df = pd.DataFrame({
            ...     'open': [100, 101],
            ...     'high': [105, 106],
            ...     'low': [99, 100],
            ...     'close': [103, 104],
            ...     'volume': [1000, 2000]
            ... }, index=pd.DatetimeIndex(['2024-01-01', '2024-01-02']))
            >>> config = PandasDataFeedConfig.create(df, name='BTC-KRW')
            >>>
            >>> # 방법 2: datetime 컬럼 사용
            >>> df = pd.DataFrame({
            ...     'datetime': ['2024-01-01', '2024-01-02'],
            ...     'open': [100, 101],
            ...     'high': [105, 106],
            ...     'low': [99, 100],
            ...     'close': [103, 104],
            ...     'volume': [1000, 2000]
            ... })
            >>> config = PandasDataFeedConfig.create(df, name='BTC-KRW')
        """
        # 1. DataFrame 검증 (datetime 소스 확인)
        datetime_param = cls._validate_dataframe(df)

        # 2. 정렬 (index 또는 datetime 컬럼 기준)
        if datetime_param is None:
            # index가 datetime인 경우
            df_sorted = df.sort_index() if not df.index.is_monotonic_increasing else df.copy()
        else:
            # datetime 컬럼이 있는 경우
            df_sorted = (
                df.sort_values(by=datetime_param) if not cls._is_sorted_by_column(df, datetime_param) else df.copy()
            )

        # 3. PandasDataFeedConfig 인스턴스 생성
        return cls(
            data_name=df_sorted,
            name=name,
            from_date=from_date,
            to_date=to_date,
            datetime=datetime_param,
        )

    @classmethod
    def from_csv(
            cls,
            csv_path: str,
            name: str = "",
            from_date: pd.Timestamp | None = None,
            to_date: pd.Timestamp | None = None,
    ) -> "PandasDataFeedConfig":
        """CSV 파일에서 PandasDataFeedConfig 생성 (팩터리 메서드)

        CSV 파일의 컬럼명은 다음 중 하나여야 합니다:
        - datetime 컬럼: 'datetime', 'date', 'time', 'timestamp', 'dt' 중 하나
          또는 DatetimeIndex 사용
        - OHLCV 컬럼: 'open', 'high', 'low', 'close', 'volume' (대소문자 무관)

        특정 소스(예: Upbit)의 컬럼명이 다른 경우, 사용자가 직접 전처리 필요:
            >>> import pandas as pd
            >>> df = pd.read_csv('upbit_data.csv')
            >>> df.rename(columns={'candle_date_time_kst': 'datetime'}, inplace=True)
            >>> config = PandasDataFeedConfig.create(df)

        Args:
            csv_path: CSV 파일 경로 (예: '~/data_gd/hour/KRW-BTC_minute60_candles.csv')
            name: 데이터 피드 이름 (플로팅용)
            from_date: 시작 날짜 (None이면 전체)
            to_date: 종료 날짜 (None이면 전체)

        Returns:
            PandasDataFeedConfig: 검증되고 정렬된 설정 객체

        Raises:
            ValueError: CSV 파일이 비어있거나 형식이 올바르지 않을 때

        Example:
            >>> # 표준 컬럼명 사용
            >>> config = PandasDataFeedConfig.from_csv(
            ...     csv_path='~/data/btc_ohlcv.csv',
            ...     name='BTC-KRW'
            ... )
            >>> data_feed = config.to_data_feed()
        """
        import os

        # 1. 홈 디렉토리 경로 확장
        expanded_path = os.path.expanduser(csv_path)

        # 2. CSV 파일 읽기
        try:
            df = pd.read_csv(expanded_path)
        except pd.errors.EmptyDataError as e:
            raise ValueError(f"CSV 파일이 비어있습니다: {csv_path}") from e

        if df.empty:
            raise ValueError(f"CSV 파일이 비어있습니다: {csv_path}")

        # 3. create() 메서드를 사용하여 검증 및 정렬
        return cls.create(df=df, name=name, from_date=from_date, to_date=to_date)

    def to_data_feed(self) -> bt.feeds.PandasData:
        """PandasData로 변환

        Returns:
            bt.feeds.PandasData: backtrader 데이터 피드
        """
        pandas_data_params = {
            "dataname": self.data_name,
            "name": self.name,
            "fromdate": self.from_date,
            "todate": self.to_date,
        }

        # datetime 컬럼이 있으면 파라미터 추가
        if self.datetime is not None:
            pandas_data_params["datetime"] = self.datetime

        return bt.feeds.PandasData(**pandas_data_params)

    @staticmethod
    def _validate_dataframe(df: pd.DataFrame) -> str | None:
        """DataFrame이 PandasData 요구사항을 만족하는지 검증

        Returns:
            str | None: datetime 컬럼 이름 (index 사용 시 None)
        """

        # 1. 빈 DataFrame 체크
        if df.empty:
            raise ValueError("DataFrame이 비어 있습니다.")

        # 2. Datetime 소스 확인
        datetime_param = PandasDataFeedConfig._find_datetime_source(df)

        # 3. 필수 컬럼 체크 (대소문자 구분 없음)
        required_columns = {"open", "high", "low", "close", "volume"}
        df_columns_lower = {col.lower() for col in df.columns}

        missing_columns = required_columns - df_columns_lower
        if missing_columns:
            raise ValueError(
                f"필수 컬럼이 누락되었습니다: {missing_columns}\n"
                f"필요한 컬럼: {required_columns}\n"
                f"현재 컬럼: {set(df.columns)}"
            )

        # 4. 데이터 타입 체크 (숫자형이어야 함)
        for col in required_columns:
            # 대소문자 구분 없이 찾기
            actual_col = next((c for c in df.columns if c.lower() == col), None)
            if actual_col and not pd.api.types.is_numeric_dtype(df[actual_col]):
                raise ValueError(f"'{actual_col}' 컬럼은 숫자형이어야 합니다. " f"현재 타입: {df[actual_col].dtype}")

        return datetime_param

    @staticmethod
    def _find_datetime_source(df: pd.DataFrame) -> str | None:
        """DataFrame에서 datetime 소스를 찾음

        Returns:
            str | None: datetime 컬럼 이름 (index 사용 시 None)

        Raises:
            ValueError: datetime 소스를 찾을 수 없을 때
        """
        # 1. Index가 DatetimeIndex인 경우
        if isinstance(df.index, pd.DatetimeIndex):
            return None  # PandasData의 기본값 (datetime=None)

        # 2. datetime 계열 컬럼 찾기 (대소문자 구분 없음)
        datetime_candidates = ["datetime", "date", "time", "timestamp", "dt"]

        for candidate in datetime_candidates:
            # 대소문자 구분 없이 찾기
            actual_col = next((c for c in df.columns if c.lower() == candidate), None)
            if actual_col:
                # datetime 타입인지 확인
                if pd.api.types.is_datetime64_any_dtype(df[actual_col]):
                    return actual_col
                # 문자열이라면 변환 시도
                elif pd.api.types.is_string_dtype(df[actual_col]):
                    return actual_col  # PandasData가 자동 파싱

        # 3. 어떤 datetime 소스도 찾지 못함
        raise ValueError(
            "datetime 정보를 찾을 수 없습니다.\n"
            "다음 중 하나를 제공해야 합니다:\n"
            "  1. DatetimeIndex를 index로 사용\n"
            "  2. 'datetime', 'date', 'time', 'timestamp' 등의 이름을 가진 컬럼 추가\n"
            f"현재 index 타입: {type(df.index).__name__}\n"
            f"현재 컬럼: {list(df.columns)}"
        )

    @staticmethod
    def _is_sorted_by_column(df: pd.DataFrame, column: str) -> bool:
        """특정 컬럼 기준으로 정렬되어 있는지 확인"""
        return df[column].is_monotonic_increasing
