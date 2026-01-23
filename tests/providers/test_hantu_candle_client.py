"""HantuCandleClient 테스트."""

from datetime import UTC, date, datetime, time, timedelta
from unittest.mock import MagicMock

import pytest

from src.common.candle_client import CandleClient, CandleInterval
from src.hantu.domestic_api import HantuDomesticAPI
from src.hantu.model.overseas.candle_period import OverseasCandlePeriod
from src.hantu.model.overseas.minute_interval import OverseasMinuteInterval
from src.hantu.overseas_api import HantuOverseasAPI
from src.providers.hantu_candle_client import HantuDomesticCandleClient, HantuOverseasCandleClient


class TestHantuCandleClientProtocol:
    """HantuCandleClient가 CandleClient Protocol을 만족하는지 테스트."""

    def test_is_candle_client(self) -> None:
        """CandleClient Protocol을 만족하는지 확인."""
        mock_api = MagicMock(spec=HantuOverseasAPI)
        client = HantuOverseasCandleClient(mock_api)

        assert isinstance(client, CandleClient)

    def test_has_get_candles_method(self) -> None:
        """get_candles 메서드가 있는지 확인."""
        mock_api = MagicMock(spec=HantuOverseasAPI)
        client = HantuOverseasCandleClient(mock_api)

        assert hasattr(client, "get_candles")
        assert callable(client.get_candles)

    def test_has_supported_intervals_property(self) -> None:
        """supported_intervals 프로퍼티가 있는지 확인."""
        mock_api = MagicMock(spec=HantuOverseasAPI)
        client = HantuOverseasCandleClient(mock_api)

        assert hasattr(client, "supported_intervals")
        intervals = client.supported_intervals
        assert isinstance(intervals, list)


class TestHantuCandleClientIntervalMapping:
    """CandleInterval 변환 테스트."""

    @pytest.fixture
    def client(self) -> HantuOverseasCandleClient:
        mock_api = MagicMock(spec=HantuOverseasAPI)
        return HantuOverseasCandleClient(mock_api)

    def test_minute_1_is_minute_interval(self, client: HantuOverseasCandleClient) -> None:
        """MINUTE_1은 분봉 타입으로 분류."""
        assert client._is_minute_interval(CandleInterval.MINUTE_1)

    def test_minute_5_is_minute_interval(self, client: HantuOverseasCandleClient) -> None:
        """MINUTE_5은 분봉 타입으로 분류."""
        assert client._is_minute_interval(CandleInterval.MINUTE_5)

    def test_hour_1_is_minute_interval(self, client: HantuOverseasCandleClient) -> None:
        """HOUR_1은 분봉 타입으로 분류 (MIN_60)."""
        assert client._is_minute_interval(CandleInterval.HOUR_1)

    def test_day_is_not_minute_interval(self, client: HantuOverseasCandleClient) -> None:
        """DAY는 일봉 타입으로 분류."""
        assert not client._is_minute_interval(CandleInterval.DAY)

    def test_to_minute_interval_mapping(self, client: HantuOverseasCandleClient) -> None:
        """분봉 간격 변환 테스트."""
        assert client._to_minute_interval(CandleInterval.MINUTE_1) == OverseasMinuteInterval.MIN_1
        assert client._to_minute_interval(CandleInterval.MINUTE_5) == OverseasMinuteInterval.MIN_5
        assert client._to_minute_interval(CandleInterval.MINUTE_10) == OverseasMinuteInterval.MIN_10
        assert client._to_minute_interval(CandleInterval.MINUTE_30) == OverseasMinuteInterval.MIN_30
        assert client._to_minute_interval(CandleInterval.HOUR_1) == OverseasMinuteInterval.MIN_60

    def test_to_daily_period_mapping(self, client: HantuOverseasCandleClient) -> None:
        """일봉 기간 변환 테스트."""
        assert client._to_daily_period(CandleInterval.DAY) == OverseasCandlePeriod.DAILY
        assert client._to_daily_period(CandleInterval.WEEK) == OverseasCandlePeriod.WEEKLY
        assert client._to_daily_period(CandleInterval.MONTH) == OverseasCandlePeriod.MONTHLY


class TestHantuCandleClientGetCandles:
    """get_candles 메서드 테스트."""

    def test_get_minute_candles_calls_api(self) -> None:
        """분봉 조회 시 get_minute_candles API 호출."""
        mock_api = MagicMock(spec=HantuOverseasAPI)
        mock_response = MagicMock()
        mock_response.output2 = []
        mock_api.get_minute_candles.return_value = mock_response

        client = HantuOverseasCandleClient(mock_api)
        client.get_candles(
            symbol="AAPL",
            interval=CandleInterval.MINUTE_1,
            count=100,
        )

        mock_api.get_minute_candles.assert_called_once()

    def test_get_daily_candles_calls_api(self) -> None:
        """일봉 조회 시 get_daily_candles API 호출."""
        mock_api = MagicMock(spec=HantuOverseasAPI)
        mock_response = MagicMock()
        mock_response.candles = []  # candles property 사용
        mock_api.get_daily_candles.return_value = mock_response

        client = HantuOverseasCandleClient(mock_api)
        end_time = datetime(2024, 1, 31, tzinfo=UTC)
        client.get_candles(
            symbol="AAPL",
            interval=CandleInterval.DAY,
            count=100,
            end_time=end_time,
        )

        mock_api.get_daily_candles.assert_called_once()

    def test_get_candles_returns_standardized_dataframe(self) -> None:
        """표준화된 DataFrame이 반환되는지 확인."""
        mock_api = MagicMock(spec=HantuOverseasAPI)

        # Mock 분봉 응답
        mock_candle = MagicMock()
        mock_candle.xymd = "20240101"  # 일자
        mock_candle.xhms = "093000"  # 시간
        mock_candle.open = "100.0"
        mock_candle.high = "110.0"
        mock_candle.low = "90.0"
        mock_candle.last = "105.0"
        mock_candle.evol = "1000"

        mock_response = MagicMock()
        mock_response.output2 = [mock_candle]
        mock_api.get_minute_candles.return_value = mock_response

        client = HantuOverseasCandleClient(mock_api)
        result = client.get_candles("AAPL", CandleInterval.MINUTE_1, count=1)

        # timestamp, local_time, OHLCV 컬럼 확인
        assert "timestamp" in result.columns
        assert "local_time" in result.columns
        assert "open" in result.columns
        assert "high" in result.columns
        assert "low" in result.columns
        assert "close" in result.columns
        assert "volume" in result.columns

    def test_get_candles_empty_response(self) -> None:
        """빈 응답 처리 확인."""
        mock_api = MagicMock(spec=HantuOverseasAPI)
        mock_response = MagicMock()
        mock_response.output2 = []
        mock_api.get_minute_candles.return_value = mock_response

        client = HantuOverseasCandleClient(mock_api)
        result = client.get_candles("AAPL", CandleInterval.MINUTE_1)

        assert result.empty


class TestHantuCandleClientSupportedIntervals:
    """supported_intervals 프로퍼티 테스트."""

    def test_supported_intervals_contains_minute_intervals(self) -> None:
        """분봉 간격이 포함되어 있는지 확인."""
        mock_api = MagicMock(spec=HantuOverseasAPI)
        client = HantuOverseasCandleClient(mock_api)

        intervals = client.supported_intervals

        assert CandleInterval.MINUTE_1 in intervals
        assert CandleInterval.MINUTE_5 in intervals
        assert CandleInterval.MINUTE_10 in intervals
        assert CandleInterval.MINUTE_30 in intervals
        assert CandleInterval.HOUR_1 in intervals

    def test_supported_intervals_contains_daily_intervals(self) -> None:
        """일봉 간격이 포함되어 있는지 확인."""
        mock_api = MagicMock(spec=HantuOverseasAPI)
        client = HantuOverseasCandleClient(mock_api)

        intervals = client.supported_intervals

        assert CandleInterval.DAY in intervals
        assert CandleInterval.WEEK in intervals
        assert CandleInterval.MONTH in intervals

    def test_hour_4_not_supported(self) -> None:
        """HOUR_4는 지원하지 않음."""
        mock_api = MagicMock(spec=HantuOverseasAPI)
        client = HantuOverseasCandleClient(mock_api)

        intervals = client.supported_intervals

        assert CandleInterval.HOUR_4 not in intervals


class TestHantuCandleClientPagination:
    """페이징 처리 테스트.

    API가 자동 페이징을 통해 요청한 개수만큼 데이터를 반환하는지 검증합니다.
    """

    @staticmethod
    def _create_mock_candle(index: int) -> MagicMock:
        """테스트용 Mock 캔들 데이터 생성."""
        mock_candle = MagicMock()
        # index를 사용하여 유니크한 시간 생성 (시간 역순)
        hour = 15 - (index // 60)
        minute = 59 - (index % 60)
        mock_candle.xymd = "20240101"
        mock_candle.xhms = f"{hour:02d}{minute:02d}00"
        mock_candle.open = f"{100 + index}.0"
        mock_candle.high = f"{101 + index}.0"
        mock_candle.low = f"{99 + index}.0"
        mock_candle.last = f"{100.5 + index}"
        mock_candle.evol = f"{1000 + index}"
        return mock_candle

    def test_get_minute_candles_passes_count_to_api(self) -> None:
        """count가 API limit 파라미터로 전달되는지 확인."""
        mock_api = MagicMock(spec=HantuOverseasAPI)

        # API가 50개 데이터 반환하는 상황 시뮬레이션
        mock_candles = [self._create_mock_candle(i) for i in range(50)]
        mock_response = MagicMock()
        mock_response.output2 = mock_candles
        mock_api.get_minute_candles.return_value = mock_response

        client = HantuOverseasCandleClient(mock_api)
        client.get_candles("AAPL", CandleInterval.MINUTE_1, count=50)

        # API가 limit=50으로 호출되었는지 확인
        mock_api.get_minute_candles.assert_called_once()
        call_kwargs = mock_api.get_minute_candles.call_args.kwargs
        assert call_kwargs["limit"] == 50

    def test_get_minute_candles_passes_large_count_to_api(self) -> None:
        """120개 초과 요청 시 API에 전체 count가 전달되는지 확인."""
        mock_api = MagicMock(spec=HantuOverseasAPI)

        # API가 200개 데이터 반환하는 상황 시뮬레이션
        mock_candles = [self._create_mock_candle(i) for i in range(200)]
        mock_response = MagicMock()
        mock_response.output2 = mock_candles
        mock_api.get_minute_candles.return_value = mock_response

        client = HantuOverseasCandleClient(mock_api)
        client.get_candles("AAPL", CandleInterval.MINUTE_1, count=200)

        # API가 limit=200으로 호출되었는지 확인 (120 초과)
        mock_api.get_minute_candles.assert_called_once()
        call_kwargs = mock_api.get_minute_candles.call_args.kwargs
        assert call_kwargs["limit"] == 200

    def test_get_minute_candles_returns_api_result_as_is(self) -> None:
        """API 응답이 그대로 반환되는지 확인."""
        mock_api = MagicMock(spec=HantuOverseasAPI)

        # API가 30개 데이터 반환
        mock_candles = [self._create_mock_candle(i) for i in range(30)]
        mock_response = MagicMock()
        mock_response.output2 = mock_candles
        mock_api.get_minute_candles.return_value = mock_response

        client = HantuOverseasCandleClient(mock_api)
        result = client.get_candles("AAPL", CandleInterval.MINUTE_1, count=50)

        # API가 반환한 30개 그대로 반환
        assert len(result) == 30


class TestHantuDomesticCandleClientPagination:
    """국내 주식 분봉 페이징 처리 테스트."""

    @staticmethod
    def _create_mock_minute_candle(index: int, base_date: str = "20240101", base_hour: int = 15) -> MagicMock:
        """테스트용 Mock 분봉 캔들 데이터 생성.

        국내 주식 API 응답 형식에 맞춤:
        - stck_bsop_date: 영업 일자 (YYYYMMDD)
        - stck_cntg_hour: 체결 시간 (HHMMSS)
        """
        mock_candle = MagicMock()
        # index를 사용하여 유니크한 시간 생성 (시간 역순)
        hour = base_hour - (index // 60)
        minute = 59 - (index % 60)
        mock_candle.stck_bsop_date = base_date
        mock_candle.stck_cntg_hour = f"{hour:02d}{minute:02d}00"
        mock_candle.stck_oprc = f"{100 + index}"
        mock_candle.stck_hgpr = f"{101 + index}"
        mock_candle.stck_lwpr = f"{99 + index}"
        mock_candle.stck_prpr = f"{100 + index}"
        mock_candle.cntg_vol = f"{1000 + index}"
        return mock_candle

    def test_get_minute_candles_single_page(self) -> None:
        """count <= 120일 때 단일 API 호출."""
        mock_api = MagicMock(spec=HantuDomesticAPI)

        # 50개 데이터 반환
        mock_candles = [self._create_mock_minute_candle(i) for i in range(50)]
        mock_response = MagicMock()
        mock_response.output2 = mock_candles
        mock_api.get_minute_chart.return_value = mock_response

        client = HantuDomesticCandleClient(mock_api)
        result = client.get_candles("005930", CandleInterval.MINUTE_1, count=50, exclude_incomplete=False)

        # API가 1번만 호출되었는지 확인
        assert mock_api.get_minute_chart.call_count == 1
        assert len(result) == 50

    def test_get_minute_candles_multiple_pages(self) -> None:
        """count > 120일 때 여러 번 API 호출."""
        mock_api = MagicMock(spec=HantuDomesticAPI)

        # 첫 번째 호출: 120개 반환
        first_candles = [self._create_mock_minute_candle(i, base_hour=15) for i in range(120)]
        first_response = MagicMock()
        first_response.output2 = first_candles

        # 두 번째 호출: 80개 반환
        second_candles = [self._create_mock_minute_candle(i, base_hour=13) for i in range(80)]
        second_response = MagicMock()
        second_response.output2 = second_candles

        mock_api.get_minute_chart.side_effect = [first_response, second_response]

        client = HantuDomesticCandleClient(mock_api)
        result = client.get_candles("005930", CandleInterval.MINUTE_1, count=200, exclude_incomplete=False)

        # API가 2번 호출되었는지 확인
        assert mock_api.get_minute_chart.call_count == 2
        # 200개 반환 (120 + 80)
        assert len(result) == 200

    def test_get_minute_candles_handles_holiday_gap(self) -> None:
        """휴장일 갭 처리: 빈 응답 시 전날로 롤백하여 재시도."""
        mock_api = MagicMock(spec=HantuDomesticAPI)

        # 첫 번째 호출 (1/2 09:00~08:xx): 50개 반환
        # base_hour=8이면 가장 오래된 캔들이 08:10 → 08:09 → 9시 이전이므로 전날 23:59로 변경
        first_candles = [self._create_mock_minute_candle(i, base_date="20260102", base_hour=8) for i in range(50)]
        first_response = MagicMock()
        first_response.output2 = first_candles

        # 두 번째 호출 (1/1 23:59): 빈 응답 (신정 휴일)
        empty_response_1 = MagicMock()
        empty_response_1.output2 = []

        # 세 번째 호출 (12/31 23:59): 빈 응답 (연말 휴일)
        empty_response_2 = MagicMock()
        empty_response_2.output2 = []

        # 네 번째 호출 (12/30 23:59~): 50개 반환
        fourth_candles = [self._create_mock_minute_candle(i, base_date="20251230", base_hour=15) for i in range(50)]
        fourth_response = MagicMock()
        fourth_response.output2 = fourth_candles

        mock_api.get_minute_chart.side_effect = [
            first_response,
            empty_response_1,
            empty_response_2,
            fourth_response,
        ]

        client = HantuDomesticCandleClient(mock_api)
        result = client.get_candles("005930", CandleInterval.MINUTE_1, count=100, exclude_incomplete=False)

        # API가 4번 호출되었는지 확인
        assert mock_api.get_minute_chart.call_count == 4
        # 100개 반환 (50 + 50)
        assert len(result) == 100

        # 두 번째 호출 시 전날(1/1)로 롤백되었는지 확인
        second_call = mock_api.get_minute_chart.call_args_list[1]
        assert second_call.kwargs["target_date"] == date(2026, 1, 1)
        assert second_call.kwargs["target_time"] == time(23, 59, 0)

        # 세 번째 호출 시 12/31로 롤백되었는지 확인
        third_call = mock_api.get_minute_chart.call_args_list[2]
        assert third_call.kwargs["target_date"] == date(2025, 12, 31)
        assert third_call.kwargs["target_time"] == time(23, 59, 0)

        # 네 번째 호출 시 12/30로 롤백되었는지 확인
        fourth_call = mock_api.get_minute_chart.call_args_list[3]
        assert fourth_call.kwargs["target_date"] == date(2025, 12, 30)
        assert fourth_call.kwargs["target_time"] == time(23, 59, 0)

    def test_get_minute_candles_stops_after_max_empty_retries(self) -> None:
        """30번 이상 연속 빈 응답 시 페이징 중단."""
        mock_api = MagicMock(spec=HantuDomesticAPI)

        # 첫 번째 호출: 50개 반환
        first_candles = [self._create_mock_minute_candle(i) for i in range(50)]
        first_response = MagicMock()
        first_response.output2 = first_candles

        # 31번 빈 응답 (무한 루프 방지 테스트)
        empty_response = MagicMock()
        empty_response.output2 = []
        empty_responses = [empty_response] * 31

        mock_api.get_minute_chart.side_effect = [first_response] + empty_responses

        client = HantuDomesticCandleClient(mock_api)
        result = client.get_candles("005930", CandleInterval.MINUTE_1, count=200, exclude_incomplete=False)

        # 50개만 반환 (첫 번째 응답 + 31번 빈 응답 후 중단)
        assert len(result) == 50
        # API가 32번 호출되었는지 확인 (1 + 31)
        assert mock_api.get_minute_chart.call_count == 32

    def test_get_minute_candles_continues_on_partial_page(self) -> None:
        """120개 미만 응답 시에도 전날 데이터 조회 계속."""
        mock_api = MagicMock(spec=HantuDomesticAPI)

        # 첫 번째 호출: 60개 반환 (당일 장 시작 직후 09:00~09:59)
        # base_hour=9이면 가장 오래된 캔들이 09:00 → 08:59 → 전날 23:59로 변경
        first_candles = [self._create_mock_minute_candle(i, base_date="20240102", base_hour=9) for i in range(60)]
        first_response = MagicMock()
        first_response.output2 = first_candles

        # 두 번째 호출: 60개 반환 (전날 데이터)
        second_candles = [self._create_mock_minute_candle(i, base_date="20240101", base_hour=15) for i in range(60)]
        second_response = MagicMock()
        second_response.output2 = second_candles

        # 세 번째 호출: 80개 반환 (전전날 데이터)
        third_candles = [self._create_mock_minute_candle(i, base_date="20231231", base_hour=14) for i in range(80)]
        third_response = MagicMock()
        third_response.output2 = third_candles

        mock_api.get_minute_chart.side_effect = [first_response, second_response, third_response]

        client = HantuDomesticCandleClient(mock_api)
        result = client.get_candles("005930", CandleInterval.MINUTE_1, count=200, exclude_incomplete=False)

        # API가 3번 호출되었는지 확인 (120 미만이어도 계속 조회)
        assert mock_api.get_minute_chart.call_count == 3
        # 200개 반환 (60 + 60 + 80)
        assert len(result) == 200

        # 두 번째 호출 시 전날 날짜(20240101)와 23:59로 호출되었는지 확인
        second_call = mock_api.get_minute_chart.call_args_list[1]
        assert second_call.kwargs["target_date"] == date(2024, 1, 1)
        assert second_call.kwargs["target_time"] == time(23, 59, 0)

    def test_get_minute_candles_returns_requested_count(self) -> None:
        """요청한 count보다 많은 데이터가 있을 때 count만큼만 반환."""
        mock_api = MagicMock(spec=HantuDomesticAPI)

        # 첫 번째 호출: 120개 반환
        first_candles = [self._create_mock_minute_candle(i, base_hour=15) for i in range(120)]
        first_response = MagicMock()
        first_response.output2 = first_candles

        # 두 번째 호출: 120개 반환
        second_candles = [self._create_mock_minute_candle(i, base_hour=13) for i in range(120)]
        second_response = MagicMock()
        second_response.output2 = second_candles

        mock_api.get_minute_chart.side_effect = [first_response, second_response]

        client = HantuDomesticCandleClient(mock_api)
        result = client.get_candles("005930", CandleInterval.MINUTE_1, count=150)

        # 150개만 반환 (240개 중 최신 150개)
        assert len(result) == 150


class TestHantuDomesticCandleClientDailyCandles:
    """국내 주식 일봉 조회 테스트 - 휴장일 고려."""

    @staticmethod
    def _create_mock_daily_candle(index: int, base_date: str = "20240101") -> MagicMock:
        """테스트용 Mock 일봉 캔들 데이터 생성.

        국내 주식 일봉 API 응답 형식에 맞춤:
        - stck_bsop_date: 영업 일자 (YYYYMMDD)
        - stck_oprc, stck_hgpr, stck_lwpr, stck_clpr: OHLC
        - acml_vol: 누적 거래량
        """
        mock_candle = MagicMock()
        # 날짜를 역순으로 생성 (최신 → 과거)
        base = datetime.strptime(base_date, "%Y%m%d")
        candle_date = base - timedelta(days=index)
        mock_candle.stck_bsop_date = candle_date.strftime("%Y%m%d")
        mock_candle.stck_oprc = f"{100 + index}"
        mock_candle.stck_hgpr = f"{101 + index}"
        mock_candle.stck_lwpr = f"{99 + index}"
        mock_candle.stck_clpr = f"{100 + index}"
        mock_candle.acml_vol = f"{1000 + index}"
        return mock_candle

    def test_get_daily_candles_applies_trading_day_multiplier(self) -> None:
        """일봉 조회 시 휴장일을 고려한 1.5배 여유분이 적용되는지 확인."""
        mock_api = MagicMock(spec=HantuDomesticAPI)

        # 100개 요청하면 150일 범위로 API 호출해야 함 (1.5배)
        mock_candles = [self._create_mock_daily_candle(i) for i in range(100)]
        mock_response = MagicMock()
        mock_response.output2 = mock_candles
        mock_api.get_daily_chart.return_value = mock_response

        client = HantuDomesticCandleClient(mock_api)
        end_time = datetime(2024, 1, 31)
        client.get_candles("005930", CandleInterval.DAY, count=100, end_time=end_time, exclude_incomplete=False)

        # API 호출 확인
        call_kwargs = mock_api.get_daily_chart.call_args.kwargs
        start_date = call_kwargs["start_date"]
        end_date = call_kwargs["end_date"]

        # 날짜 범위 계산: 100일 * 1.5 = 150일
        expected_days = int(100 * 1.5)
        actual_days = (end_date - start_date).days

        # 150일 범위로 호출되었는지 확인
        assert actual_days == expected_days

    def test_get_daily_candles_trims_to_requested_count(self) -> None:
        """API가 요청보다 많이 반환해도 count만큼만 반환."""
        mock_api = MagicMock(spec=HantuDomesticAPI)

        # 150개 반환 (실제 거래일이 많은 경우)
        mock_candles = [self._create_mock_daily_candle(i) for i in range(150)]
        mock_response = MagicMock()
        mock_response.output2 = mock_candles
        mock_api.get_daily_chart.return_value = mock_response

        client = HantuDomesticCandleClient(mock_api)
        result = client.get_candles("005930", CandleInterval.DAY, count=100)

        # 100개만 반환되어야 함
        assert len(result) == 100

    def test_get_daily_candles_multiple_pages(self) -> None:
        """count > 100일 때 여러 번 API 호출하여 결과 병합."""
        mock_api = MagicMock(spec=HantuDomesticAPI)

        # 첫 번째 호출: 100개 반환
        first_candles = [self._create_mock_daily_candle(i, base_date="20240131") for i in range(100)]
        first_response = MagicMock()
        first_response.output2 = first_candles

        # 두 번째 호출: 100개 반환
        second_candles = [self._create_mock_daily_candle(i, base_date="20231023") for i in range(100)]
        second_response = MagicMock()
        second_response.output2 = second_candles

        mock_api.get_daily_chart.side_effect = [first_response, second_response]

        client = HantuDomesticCandleClient(mock_api)
        result = client.get_candles("005930", CandleInterval.DAY, count=200, exclude_incomplete=False)

        # API가 2번 호출되었는지 확인
        assert mock_api.get_daily_chart.call_count == 2
        # 200개 반환 (100 + 100)
        assert len(result) == 200

    def test_get_daily_candles_stops_on_empty_response(self) -> None:
        """빈 응답 시 페이징 중단."""
        mock_api = MagicMock(spec=HantuDomesticAPI)

        # 첫 번째 호출: 50개 반환
        first_candles = [self._create_mock_daily_candle(i, base_date="20240131") for i in range(50)]
        first_response = MagicMock()
        first_response.output2 = first_candles

        # 두 번째 호출: 빈 응답
        empty_response = MagicMock()
        empty_response.output2 = []

        mock_api.get_daily_chart.side_effect = [first_response, empty_response]

        client = HantuDomesticCandleClient(mock_api)
        result = client.get_candles("005930", CandleInterval.DAY, count=200, exclude_incomplete=False)

        # API가 2번 호출되었는지 확인 (빈 응답에서 중단)
        assert mock_api.get_daily_chart.call_count == 2
        # 50개만 반환 (첫 번째 호출 결과만)
        assert len(result) == 50


class TestHantuOverseasCandleClientDailyCandles:
    """해외주식 일봉 조회 테스트."""

    @staticmethod
    def _create_mock_daily_candle(index: int, base_date: str = "20240131") -> MagicMock:
        """테스트용 일봉 캔들 생성."""
        candle = MagicMock()
        # 날짜를 index만큼 과거로 (base_date에서 index일 전)
        base = datetime.strptime(base_date, "%Y%m%d")
        target_date = base - timedelta(days=index)
        candle.stck_bsop_date = target_date.strftime("%Y%m%d")
        candle.ovrs_nmix_oprc = "100.00"
        candle.ovrs_nmix_hgpr = "101.00"
        candle.ovrs_nmix_lwpr = "99.00"
        candle.ovrs_nmix_prpr = "100.50"
        candle.acml_vol = "1000000"
        return candle

    def test_get_daily_candles_applies_trading_day_multiplier(self) -> None:
        """일봉 조회 시 휴장일 여유분 1.5배 적용."""
        mock_api = MagicMock(spec=HantuOverseasAPI)
        mock_response = MagicMock()
        mock_response.candles = []  # 빈 응답
        mock_api.get_daily_candles.return_value = mock_response

        client = HantuOverseasCandleClient(mock_api)

        # count=100 요청
        client.get_candles("AAPL", CandleInterval.DAY, count=100)

        # API 호출 시 날짜 범위 확인
        call_args = mock_api.get_daily_candles.call_args
        start_date = call_args.kwargs["start_date"]
        end_date = call_args.kwargs["end_date"]

        # 날짜 차이 계산
        start = datetime.strptime(start_date, "%Y%m%d")
        end = datetime.strptime(end_date, "%Y%m%d")
        actual_days = (end - start).days

        # 100일 * 1.5 = 150일 범위 요청 확인
        expected_days = int(100 * 1.5)
        assert actual_days == expected_days

    def test_get_daily_candles_trims_to_requested_count(self) -> None:
        """결과를 요청한 count만큼 trim."""
        mock_api = MagicMock(spec=HantuOverseasAPI)

        # 150개 캔들 생성 (여유분 포함 응답)
        candles = [self._create_mock_daily_candle(i) for i in range(150)]

        mock_response = MagicMock()
        mock_response.candles = candles
        mock_api.get_daily_candles.return_value = mock_response

        client = HantuOverseasCandleClient(mock_api)
        result = client.get_candles("AAPL", CandleInterval.DAY, count=100)

        # 100개만 반환 확인
        assert len(result) == 100

    def test_get_daily_candles_multiple_pages(self) -> None:
        """count > 100일 때 여러 번 API 호출."""
        mock_api = MagicMock(spec=HantuOverseasAPI)

        # 첫 번째 호출: 100개 반환 (base_date에서 0-99일 전)
        first_candles = [self._create_mock_daily_candle(i, base_date="20240131") for i in range(100)]
        first_response = MagicMock()
        first_response.candles = first_candles

        # 두 번째 호출: 100개 반환 (첫 번째 조회의 가장 오래된 날짜 - 1일 기준)
        second_candles = [self._create_mock_daily_candle(i, base_date="20231023") for i in range(100)]
        second_response = MagicMock()
        second_response.candles = second_candles

        mock_api.get_daily_candles.side_effect = [first_response, second_response]

        client = HantuOverseasCandleClient(mock_api)
        result = client.get_candles("AAPL", CandleInterval.DAY, count=200)

        # API가 2번 호출되었는지 확인
        assert mock_api.get_daily_candles.call_count == 2
        # 200개 반환 (100 + 100)
        assert len(result) == 200

    def test_get_daily_candles_stops_on_empty_response(self) -> None:
        """빈 응답 시 페이징 중단."""
        mock_api = MagicMock(spec=HantuOverseasAPI)

        # 첫 번째 호출: 50개 반환
        first_candles = [self._create_mock_daily_candle(i, base_date="20240131") for i in range(50)]
        first_response = MagicMock()
        first_response.candles = first_candles

        # 두 번째 호출: 빈 응답
        empty_response = MagicMock()
        empty_response.candles = []

        mock_api.get_daily_candles.side_effect = [first_response, empty_response]

        client = HantuOverseasCandleClient(mock_api)
        result = client.get_candles("AAPL", CandleInterval.DAY, count=200)

        # API가 2번 호출되었는지 확인 (빈 응답에서 중단)
        assert mock_api.get_daily_candles.call_count == 2
        # 50개만 반환 (첫 번째 호출 결과만)
        assert len(result) == 50


class TestHantuOverseasCandleClientEndTime:
    """해외주식 분봉 조회 시 end_time 파라미터 전달 테스트."""

    def test_get_minute_candles_without_end_time_passes_none(self) -> None:
        """end_time 없이 호출 시 None 전달."""
        mock_api = MagicMock(spec=HantuOverseasAPI)
        mock_response = MagicMock()
        mock_response.output2 = []
        mock_api.get_minute_candles.return_value = mock_response

        client = HantuOverseasCandleClient(mock_api)
        client.get_candles(
            symbol="AAPL",
            interval=CandleInterval.MINUTE_1,
            count=100,
        )

        # end_time이 None으로 전달되었는지 확인
        call_kwargs = mock_api.get_minute_candles.call_args.kwargs
        assert call_kwargs["end_time"] is None

    def test_get_minute_candles_with_utc_end_time_converts_to_new_york(self) -> None:
        """UTC end_time이 New York 시간으로 변환되어 전달."""
        mock_api = MagicMock(spec=HantuOverseasAPI)
        mock_response = MagicMock()
        mock_response.output2 = []
        mock_api.get_minute_candles.return_value = mock_response

        client = HantuOverseasCandleClient(mock_api)

        # UTC naive datetime으로 2026-01-20 22:16:00 설정
        # → New York 시간으로는 2026-01-20 17:16:00 (EST, -5시간)
        end_time = datetime(2026, 1, 20, 22, 16, 0)  # UTC naive

        client.get_candles(
            symbol="AAPL",
            interval=CandleInterval.MINUTE_1,
            count=100,
            end_time=end_time,
        )

        # end_time이 New York 시간으로 변환되어 전달되었는지 확인
        call_kwargs = mock_api.get_minute_candles.call_args.kwargs
        actual_end_time = call_kwargs["end_time"]

        # EST 기준: 2026-01-20 17:16:00
        from zoneinfo import ZoneInfo
        expected_ny_time = datetime(2026, 1, 20, 17, 16, 0, tzinfo=ZoneInfo("America/New_York"))
        assert actual_end_time == expected_ny_time

    def test_get_minute_candles_with_end_time_handles_date_change(self) -> None:
        """UTC→New York 변환 시 날짜가 바뀌는 경우 처리."""
        mock_api = MagicMock(spec=HantuOverseasAPI)
        mock_response = MagicMock()
        mock_response.output2 = []
        mock_api.get_minute_candles.return_value = mock_response

        client = HantuOverseasCandleClient(mock_api)

        # UTC 2026-01-21 03:00:00 → New York 2026-01-20 22:00:00 (EST)
        end_time = datetime(2026, 1, 21, 3, 0, 0)  # UTC naive

        client.get_candles(
            symbol="TSLA",
            interval=CandleInterval.MINUTE_5,
            count=50,
            end_time=end_time,
        )

        call_kwargs = mock_api.get_minute_candles.call_args.kwargs
        actual_end_time = call_kwargs["end_time"]

        # EST 기준: 2026-01-20 22:00:00
        from zoneinfo import ZoneInfo
        expected_ny_time = datetime(2026, 1, 20, 22, 0, 0, tzinfo=ZoneInfo("America/New_York"))
        assert actual_end_time == expected_ny_time


class TestHantuDomesticCandleClientExcludeIncomplete:
    """미마감 캔들 제외 기능 테스트."""

    @staticmethod
    def _create_mock_minute_candle(index: int, base_date: str = "20240101", base_hour: int = 15) -> MagicMock:
        """테스트용 Mock 분봉 캔들 데이터 생성."""
        mock_candle = MagicMock()
        hour = base_hour - (index // 60)
        minute = 59 - (index % 60)
        mock_candle.stck_bsop_date = base_date
        mock_candle.stck_cntg_hour = f"{hour:02d}{minute:02d}00"
        mock_candle.stck_oprc = f"{100 + index}"
        mock_candle.stck_hgpr = f"{101 + index}"
        mock_candle.stck_lwpr = f"{99 + index}"
        mock_candle.stck_prpr = f"{100 + index}"
        mock_candle.cntg_vol = f"{1000 + index}"
        return mock_candle

    def test_exclude_incomplete_true_by_default(self) -> None:
        """exclude_incomplete 기본값은 True."""
        mock_api = MagicMock(spec=HantuDomesticAPI)

        # 51개 반환하면 마지막 1개 제외하여 50개 반환
        mock_candles = [self._create_mock_minute_candle(i) for i in range(51)]
        mock_response = MagicMock()
        mock_response.output2 = mock_candles
        mock_api.get_minute_chart.return_value = mock_response

        client = HantuDomesticCandleClient(mock_api)
        result = client.get_candles("005930", CandleInterval.MINUTE_1, count=50)

        # 50개만 반환 (마지막 1개 제외)
        assert len(result) == 50

    def test_exclude_incomplete_false_returns_all(self) -> None:
        """exclude_incomplete=False일 때 마지막 캔들 포함."""
        mock_api = MagicMock(spec=HantuDomesticAPI)

        mock_candles = [self._create_mock_minute_candle(i) for i in range(50)]
        mock_response = MagicMock()
        mock_response.output2 = mock_candles
        mock_api.get_minute_chart.return_value = mock_response

        client = HantuDomesticCandleClient(mock_api)
        result = client.get_candles("005930", CandleInterval.MINUTE_1, count=50, exclude_incomplete=False)

        # 50개 모두 반환 (마지막 캔들 포함)
        assert len(result) == 50

    def test_exclude_incomplete_empty_dataframe_returns_empty(self) -> None:
        """빈 DataFrame일 때 에러 없이 빈 DataFrame 반환."""
        mock_api = MagicMock(spec=HantuDomesticAPI)

        mock_response = MagicMock()
        mock_response.output2 = []
        mock_api.get_minute_chart.return_value = mock_response

        client = HantuDomesticCandleClient(mock_api)
        result = client.get_candles("005930", CandleInterval.MINUTE_1, count=50, exclude_incomplete=True)

        # 빈 DataFrame 반환
        assert result.empty


class TestHantuDomesticCandleClientEndTime:
    """국내주식 분봉 조회 시 end_time 파라미터 전달 테스트."""

    def test_get_minute_candles_without_end_time_uses_current_time(self) -> None:
        """end_time 없이 호출 시 현재 시간 사용."""
        mock_api = MagicMock(spec=HantuDomesticAPI)
        mock_response = MagicMock()
        mock_response.output2 = []
        mock_api.get_minute_chart.return_value = mock_response

        client = HantuDomesticCandleClient(mock_api)
        client.get_candles(
            symbol="005930",
            interval=CandleInterval.MINUTE_1,
            count=100,
        )

        # get_minute_chart가 호출되었는지 확인
        assert mock_api.get_minute_chart.called

    def test_get_minute_candles_with_utc_end_time_converts_to_kst(self) -> None:
        """UTC end_time이 KST로 변환되어 API에 전달."""
        mock_api = MagicMock(spec=HantuDomesticAPI)
        mock_response = MagicMock()
        # 충분한 데이터 반환 (빈 응답 시 전날 롤백 방지)
        mock_candle = MagicMock()
        mock_candle.stck_bsop_date = "20240115"
        mock_candle.stck_cntg_hour = "175900"
        mock_candle.stck_oprc = "100"
        mock_candle.stck_hgpr = "101"
        mock_candle.stck_lwpr = "99"
        mock_candle.stck_prpr = "100"
        mock_candle.cntg_vol = "1000"
        mock_response.output2 = [mock_candle] * 100
        mock_api.get_minute_chart.return_value = mock_response

        client = HantuDomesticCandleClient(mock_api)

        # UTC 시간으로 2024-01-15 09:00:00 설정
        # → KST 시간으로는 2024-01-15 18:00:00 (+9시간)
        end_time = datetime(2024, 1, 15, 9, 0, 0)  # UTC naive datetime

        client.get_candles(
            symbol="005930",
            interval=CandleInterval.MINUTE_1,
            count=100,
            end_time=end_time,
        )

        # 첫 번째 API 호출에 전달된 target_date와 target_time 확인
        first_call_kwargs = mock_api.get_minute_chart.call_args_list[0].kwargs
        assert first_call_kwargs["target_date"] == date(2024, 1, 15)  # KST 날짜
        assert first_call_kwargs["target_time"] == time(18, 0, 0)  # KST 시간

    def test_get_minute_candles_with_utc_end_time_handles_date_change(self) -> None:
        """UTC→KST 변환 시 날짜가 바뀌는 경우 처리."""
        mock_api = MagicMock(spec=HantuDomesticAPI)
        mock_response = MagicMock()
        # 충분한 데이터 반환 (빈 응답 시 전날 롤백 방지)
        mock_candle = MagicMock()
        mock_candle.stck_bsop_date = "20240116"
        mock_candle.stck_cntg_hour = "045900"
        mock_candle.stck_oprc = "100"
        mock_candle.stck_hgpr = "101"
        mock_candle.stck_lwpr = "99"
        mock_candle.stck_prpr = "100"
        mock_candle.cntg_vol = "1000"
        mock_response.output2 = [mock_candle] * 100
        mock_api.get_minute_chart.return_value = mock_response

        client = HantuDomesticCandleClient(mock_api)

        # UTC 2024-01-15 20:00:00 → KST 2024-01-16 05:00:00
        end_time = datetime(2024, 1, 15, 20, 0, 0)  # UTC naive datetime

        client.get_candles(
            symbol="005930",
            interval=CandleInterval.MINUTE_1,
            count=100,
            end_time=end_time,
        )

        # 첫 번째 API 호출에서 KST로 변환 시 날짜가 바뀌어야 함
        first_call_kwargs = mock_api.get_minute_chart.call_args_list[0].kwargs
        assert first_call_kwargs["target_date"] == date(2024, 1, 16)  # 다음날
        assert first_call_kwargs["target_time"] == time(5, 0, 0)  # KST 시간
