import pandas as pd
import pytest

from src.backtest.data_feed.pandas import PandasDataFeedConfig


class TestPandasDataFeedConfig:
    """PandasDataFeedConfig 클래스 테스트"""

    def test_정상적인_dataframe으로_생성_성공(self):
        """정상적인 DataFrame으로 PandasDataFeedConfig 생성"""
        df = pd.DataFrame(
            {
                "open": [100.0, 101.0],
                "high": [105.0, 106.0],
                "low": [99.0, 100.0],
                "close": [103.0, 104.0],
                "volume": [1000.0, 2000.0],
            },
            index=pd.DatetimeIndex(["2024-01-01", "2024-01-02"]),
        )

        config = PandasDataFeedConfig.create(df, name="TEST")
        data_feed = config.to_data_feed()

        assert data_feed.p.name == "TEST"
        assert isinstance(data_feed.p.dataname, pd.DataFrame)
        assert len(data_feed.p.dataname) == 2

    def test_대소문자_구분_없이_생성_가능(self):
        """컬럼명 대소문자 구분 없이 생성 가능"""
        df = pd.DataFrame(
            {
                "Open": [100.0],
                "High": [105.0],
                "Low": [99.0],
                "Close": [103.0],
                "Volume": [1000.0],
            },
            index=pd.DatetimeIndex(["2024-01-01"]),
        )

        config = PandasDataFeedConfig.create(df)
        data_feed = config.to_data_feed()

        assert data_feed is not None
        assert isinstance(data_feed.p.dataname, pd.DataFrame)

    def test_openinterest_선택_컬럼(self):
        """openinterest는 선택 컬럼"""
        df = pd.DataFrame(
            {
                "open": [100.0],
                "high": [105.0],
                "low": [99.0],
                "close": [103.0],
                "volume": [1000.0],
                "openinterest": [500.0],
            },
            index=pd.DatetimeIndex(["2024-01-01"]),
        )

        config = PandasDataFeedConfig.create(df)
        data_feed = config.to_data_feed()

        assert data_feed is not None

    def test_fromdate_todate_파라미터(self):
        """fromdate, todate 파라미터 전달"""
        df = pd.DataFrame(
            {
                "open": [100.0, 101.0, 102.0],
                "high": [105.0, 106.0, 107.0],
                "low": [99.0, 100.0, 101.0],
                "close": [103.0, 104.0, 105.0],
                "volume": [1000.0, 2000.0, 3000.0],
            },
            index=pd.DatetimeIndex(["2024-01-01", "2024-01-02", "2024-01-03"]),
        )

        fromdate = pd.Timestamp("2024-01-02")
        todate = pd.Timestamp("2024-01-03")

        config = PandasDataFeedConfig.create(df, from_date=fromdate, to_date=todate)
        data_feed = config.to_data_feed()

        assert data_feed.p.fromdate == fromdate
        assert data_feed.p.todate == todate


class TestValidateDataFrame:
    """_validate_dataframe 검증 로직 테스트"""

    def test_빈_dataframe_예외(self):
        """빈 DataFrame은 예외 발생"""
        df = pd.DataFrame()

        with pytest.raises(ValueError, match="비어 있습니다"):
            PandasDataFeedConfig.create(df)

    def test_datetime_소스_없음_예외(self):
        """DatetimeIndex도 없고 datetime 컬럼도 없으면 예외 발생"""
        df = pd.DataFrame(
            {
                "open": [100.0],
                "high": [105.0],
                "low": [99.0],
                "close": [103.0],
                "volume": [1000.0],
            }
        )  # 일반 RangeIndex, datetime 컬럼도 없음

        with pytest.raises(ValueError, match="datetime 정보를 찾을 수 없습니다"):
            PandasDataFeedConfig.create(df)

    def test_필수_컬럼_누락_예외(self):
        """필수 컬럼이 누락되면 예외 발생"""
        df = pd.DataFrame(
            {
                "open": [100.0],
                "high": [105.0],
                # 'low' 누락
                "close": [103.0],
                "volume": [1000.0],
            },
            index=pd.DatetimeIndex(["2024-01-01"]),
        )

        with pytest.raises(ValueError, match="필수 컬럼이 누락"):
            PandasDataFeedConfig.create(df)

    def test_여러_컬럼_누락_예외_메시지(self):
        """여러 필수 컬럼 누락 시 명확한 에러 메시지"""
        df = pd.DataFrame(
            {
                "open": [100.0],
                # 'high', 'low', 'close', 'volume' 모두 누락
            },
            index=pd.DatetimeIndex(["2024-01-01"]),
        )

        with pytest.raises(ValueError) as exc_info:
            PandasDataFeedConfig.create(df)

        error_msg = str(exc_info.value)
        assert "필수 컬럼이 누락" in error_msg
        assert "high" in error_msg or "low" in error_msg

    def test_비숫자_컬럼_타입_예외(self):
        """숫자형이 아닌 컬럼은 예외 발생"""
        df = pd.DataFrame(
            {
                "open": ["100", "101"],  # 문자열
                "high": [105.0, 106.0],
                "low": [99.0, 100.0],
                "close": [103.0, 104.0],
                "volume": [1000.0, 2000.0],
            },
            index=pd.DatetimeIndex(["2024-01-01", "2024-01-02"]),
        )

        with pytest.raises(ValueError, match="숫자형이어야 합니다"):
            PandasDataFeedConfig.create(df)


class TestAutoSorting:
    """자동 정렬 기능 테스트"""

    def test_역순_데이터_자동_오름차순_정렬(self):
        """역순 데이터도 자동으로 오름차순 정렬"""
        df = pd.DataFrame(
            {
                "open": [101.0, 100.0],
                "high": [106.0, 105.0],
                "low": [100.0, 99.0],
                "close": [104.0, 103.0],
                "volume": [2000.0, 1000.0],
            },
            index=pd.DatetimeIndex(["2024-01-02", "2024-01-01"]),  # 역순
        )

        config = PandasDataFeedConfig.create(df)
        data_feed = config.to_data_feed()

        # 원본은 변경되지 않음
        assert df.index[0] == pd.Timestamp("2024-01-02")

        # 생성된 데이터는 정렬됨
        assert data_feed.p.dataname.index[0] == pd.Timestamp("2024-01-01")
        assert data_feed.p.dataname.index[1] == pd.Timestamp("2024-01-02")

    def test_이미_정렬된_데이터_복사(self):
        """이미 정렬된 데이터는 복사만 수행"""
        df = pd.DataFrame(
            {
                "open": [100.0, 101.0],
                "high": [105.0, 106.0],
                "low": [99.0, 100.0],
                "close": [103.0, 104.0],
                "volume": [1000.0, 2000.0],
            },
            index=pd.DatetimeIndex(["2024-01-01", "2024-01-02"]),  # 이미 정렬됨
        )

        config = PandasDataFeedConfig.create(df)
        data_feed = config.to_data_feed()

        # 원본과 별도 객체
        assert data_feed.p.dataname is not df

        # 정렬 순서는 동일
        assert data_feed.p.dataname.index[0] == pd.Timestamp("2024-01-01")


class TestDatetimeColumn:
    """datetime 컬럼을 사용하는 경우 테스트"""

    def test_datetime_컬럼_사용(self):
        """datetime 컬럼이 있으면 DatetimeIndex 없어도 성공"""
        df = pd.DataFrame(
            {
                "datetime": pd.to_datetime(["2024-01-01", "2024-01-02"]),
                "open": [100.0, 101.0],
                "high": [105.0, 106.0],
                "low": [99.0, 100.0],
                "close": [103.0, 104.0],
                "volume": [1000.0, 2000.0],
            }
        )  # 일반 RangeIndex지만 datetime 컬럼 있음

        config = PandasDataFeedConfig.create(df, name="TEST")
        data_feed = config.to_data_feed()

        assert data_feed.p.name == "TEST"
        assert isinstance(data_feed.p.dataname, pd.DataFrame)
        # datetime 파라미터가 설정되어야 함
        assert data_feed.p.datetime == "datetime"

    def test_date_컬럼_사용(self):
        """'date' 이름의 컬럼도 인식"""
        df = pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-01-01", "2024-01-02"]),
                "open": [100.0, 101.0],
                "high": [105.0, 106.0],
                "low": [99.0, 100.0],
                "close": [103.0, 104.0],
                "volume": [1000.0, 2000.0],
            }
        )

        config = PandasDataFeedConfig.create(df)
        data_feed = config.to_data_feed()

        assert data_feed.p.datetime == "date"

    def test_timestamp_컬럼_사용(self):
        """'timestamp' 이름의 컬럼도 인식"""
        df = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(["2024-01-01", "2024-01-02"]),
                "open": [100.0, 101.0],
                "high": [105.0, 106.0],
                "low": [99.0, 100.0],
                "close": [103.0, 104.0],
                "volume": [1000.0, 2000.0],
            }
        )

        config = PandasDataFeedConfig.create(df)
        data_feed = config.to_data_feed()

        assert data_feed.p.datetime == "timestamp"

    def test_datetime_컬럼_대소문자_구분_없음(self):
        """DateTime, DATETIME 등도 인식"""
        df = pd.DataFrame(
            {
                "DateTime": pd.to_datetime(["2024-01-01", "2024-01-02"]),
                "open": [100.0, 101.0],
                "high": [105.0, 106.0],
                "low": [99.0, 100.0],
                "close": [103.0, 104.0],
                "volume": [1000.0, 2000.0],
            }
        )

        config = PandasDataFeedConfig.create(df)
        data_feed = config.to_data_feed()

        assert data_feed.p.datetime == "DateTime"

    def test_datetime_컬럼_문자열_자동_파싱(self):
        """문자열 datetime도 backtrader가 파싱"""
        df = pd.DataFrame(
            {
                "datetime": ["2024-01-01", "2024-01-02"],  # 문자열
                "open": [100.0, 101.0],
                "high": [105.0, 106.0],
                "low": [99.0, 100.0],
                "close": [103.0, 104.0],
                "volume": [1000.0, 2000.0],
            }
        )

        config = PandasDataFeedConfig.create(df)
        data_feed = config.to_data_feed()

        assert data_feed.p.datetime == "datetime"

    def test_datetime_컬럼_자동_정렬(self):
        """datetime 컬럼 기준으로 자동 정렬"""
        df = pd.DataFrame(
            {
                "datetime": pd.to_datetime(["2024-01-02", "2024-01-01"]),  # 역순
                "open": [101.0, 100.0],
                "high": [106.0, 105.0],
                "low": [100.0, 99.0],
                "close": [104.0, 103.0],
                "volume": [2000.0, 1000.0],
            }
        )

        config = PandasDataFeedConfig.create(df)
        data_feed = config.to_data_feed()

        # 원본은 변경되지 않음
        assert df["datetime"].iloc[0] == pd.Timestamp("2024-01-02")

        # 생성된 데이터는 정렬됨
        assert data_feed.p.dataname["datetime"].iloc[0] == pd.Timestamp("2024-01-01")
        assert data_feed.p.dataname["datetime"].iloc[1] == pd.Timestamp("2024-01-02")

    def test_datetimeindex_우선순위(self):
        """DatetimeIndex와 datetime 컬럼이 둘 다 있으면 index 우선"""
        df = pd.DataFrame(
            {
                "datetime": pd.to_datetime(["2024-01-01", "2024-01-02"]),
                "open": [100.0, 101.0],
                "high": [105.0, 106.0],
                "low": [99.0, 100.0],
                "close": [103.0, 104.0],
                "volume": [1000.0, 2000.0],
            },
            index=pd.DatetimeIndex(["2024-01-03", "2024-01-04"]),
        )

        config = PandasDataFeedConfig.create(df)
        data_feed = config.to_data_feed()

        # index를 사용하므로 datetime 파라미터는 None
        assert data_feed.p.datetime is None
