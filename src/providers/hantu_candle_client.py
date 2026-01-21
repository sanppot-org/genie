"""Hantu API를 CandleClient로 래핑하는 클라이언트."""

from datetime import datetime, timedelta
from datetime import time as time_obj
from typing import TYPE_CHECKING

import pandas as pd
from pandera.typing import DataFrame

from src.common.candle_client import CandleClient, CandleInterval
from src.common.candle_schema import CommonCandleSchema
from src.constants import TimeZone
from src.hantu.domestic_api import HantuDomesticAPI
from src.hantu.model.domestic.chart import ChartInterval
from src.hantu.model.overseas.candle_period import OverseasCandlePeriod
from src.hantu.model.overseas.minute_interval import OverseasMinuteInterval
from src.hantu.overseas_api import HantuOverseasAPI

if TYPE_CHECKING:
    from src.hantu.model.domestic.chart import (
        DailyChartResponseBody,
        MinuteChartResponseBody,
    )
    from src.hantu.model.overseas.price import (
        OverseasDailyCandleResponse,
        OverseasMinuteCandleResponse,
    )


class HantuOverseasCandleClient(CandleClient):
    """Hantu Overseas API를 CandleClient Protocol로 래핑.

    기존 HantuOverseasAPI를 수정하지 않고 CandleClient Protocol을 구현합니다.
    분봉과 일봉 API가 분리되어 있으므로 내부적으로 분기 처리합니다.

    Example:
        >>> from src.hantu.overseas_api import HantuOverseasAPI
        >>> from src.providers.hantu_candle_client import HantuOverseasCandleClient
        >>> from src.common.candle_client import CandleInterval
        >>>
        >>> api = HantuOverseasAPI(config)
        >>> client = HantuOverseasCandleClient(api)
        >>> df = client.get_candles("AAPL", CandleInterval.DAY, count=100)
    """

    _MINUTE_INTERVAL_MAP: dict[CandleInterval, OverseasMinuteInterval] = {
        CandleInterval.MINUTE_1: OverseasMinuteInterval.MIN_1,
        CandleInterval.MINUTE_5: OverseasMinuteInterval.MIN_5,
        CandleInterval.MINUTE_10: OverseasMinuteInterval.MIN_10,
        CandleInterval.MINUTE_30: OverseasMinuteInterval.MIN_30,
        CandleInterval.HOUR_1: OverseasMinuteInterval.MIN_60,
    }

    _DAILY_PERIOD_MAP: dict[CandleInterval, OverseasCandlePeriod] = {
        CandleInterval.DAY: OverseasCandlePeriod.DAILY,
        CandleInterval.WEEK: OverseasCandlePeriod.WEEKLY,
        CandleInterval.MONTH: OverseasCandlePeriod.MONTHLY,
    }

    # 휴장일(주말, 공휴일)을 고려한 날짜 범위 여유분
    _TRADING_DAY_MULTIPLIER: dict[CandleInterval, float] = {
        CandleInterval.DAY: 1.5,  # 주 5일 거래 + 공휴일 여유
        CandleInterval.WEEK: 1.1,  # 약간의 여유
        CandleInterval.MONTH: 1.0,  # 영향 없음
    }

    def __init__(self, api: HantuOverseasAPI) -> None:
        """HantuCandleClient 초기화.

        Args:
            api: Hantu Overseas API 인스턴스
        """
        self._api = api

    def get_candles(
            self,
            symbol: str,
            interval: CandleInterval,
            count: int = 100,
            end_time: datetime | None = None,
    ) -> DataFrame[CommonCandleSchema]:
        """캔들 데이터 조회.

        Args:
            symbol: 종목코드 (예: "AAPL", "TSLA")
            interval: 캔들 간격 (CandleInterval)
            count: 조회할 캔들 개수 (기본값: 100)
            end_time: 종료 시간 (해당 시간 이전 데이터 조회, UTC)

        Returns:
            표준 캔들 DataFrame[CommonCandleSchema]
            - index: DatetimeIndex (UTC)
            - columns: open, high, low, close, volume
        """
        if self._is_minute_interval(interval):
            df = self._get_minute_candles(symbol, interval, count)
        else:
            df = self._get_daily_candles(symbol, interval, count, end_time)

        return CommonCandleSchema.validate(df)

    @property
    def supported_intervals(self) -> list[CandleInterval]:
        """지원하는 캔들 간격 목록."""
        return list(self._MINUTE_INTERVAL_MAP.keys()) + list(self._DAILY_PERIOD_MAP.keys())

    def _is_minute_interval(self, interval: CandleInterval) -> bool:
        """분봉 타입인지 확인."""
        return interval in self._MINUTE_INTERVAL_MAP

    def _to_minute_interval(self, interval: CandleInterval) -> OverseasMinuteInterval:
        """CandleInterval을 OverseasMinuteInterval로 변환."""
        result = self._MINUTE_INTERVAL_MAP.get(interval)
        if result is None:
            raise ValueError(f"분봉으로 변환할 수 없는 간격입니다: {interval}")
        return result

    def _to_daily_period(self, interval: CandleInterval) -> OverseasCandlePeriod:
        """CandleInterval을 OverseasCandlePeriod로 변환."""
        result = self._DAILY_PERIOD_MAP.get(interval)
        if result is None:
            raise ValueError(f"일봉으로 변환할 수 없는 간격입니다: {interval}")
        return result

    def _get_minute_candles(
            self,
            symbol: str,
            interval: CandleInterval,
            count: int,
    ) -> pd.DataFrame:
        """분봉 데이터 조회.

        API가 연속조회를 통해 요청한 개수만큼 데이터를 반환합니다.
        """
        minute_interval = self._to_minute_interval(interval)

        response = self._api.get_minute_candles(
            symbol=symbol,
            minute_interval=minute_interval,
            limit=count,  # API가 자동 페이징으로 count만큼 조회
        )

        df = self._minute_response_to_dataframe(response)

        return df

    def _get_daily_candles(
            self,
            symbol: str,
            interval: CandleInterval,
            count: int,
            end_time: datetime | None,
    ) -> pd.DataFrame:
        """일봉/주봉/월봉 데이터 조회.

        API가 한 번에 최대 100건만 반환하므로,
        count > 100일 때 여러 번 호출하여 결과를 병합합니다.
        휴장일(주말, 공휴일)을 고려한 여유분도 적용합니다.
        """
        period = self._to_daily_period(interval)
        days_per_candle = self._get_days_per_candle(interval)
        multiplier = self._TRADING_DAY_MULTIPLIER.get(interval, 1.5)

        if end_time is None:
            current_end = datetime.now()
        else:
            current_end = end_time

        all_candles: list[pd.DataFrame] = []
        remaining = count

        while remaining > 0:
            # 이번 호출에서 목표 개수 (최대 100개)
            fetch_target = min(remaining, 100)

            # 휴장일 여유분 적용한 날짜 범위
            days_needed = int(fetch_target * days_per_candle * multiplier)
            start_date = current_end.date() - timedelta(days=days_needed)

            response = self._api.get_daily_candles(
                symbol=symbol,
                start_date=start_date.strftime("%Y%m%d"),
                end_date=current_end.strftime("%Y%m%d"),
                period=period,
            )

            df = self._daily_response_to_dataframe(response)

            if df.empty:
                break

            all_candles.append(df)
            remaining -= len(df)

            # 다음 조회를 위해 가장 오래된 캔들 날짜 - 1일
            oldest_date = df.index.min().to_pydatetime()
            current_end = oldest_date - timedelta(days=1)

        if not all_candles:
            return pd.DataFrame(
                columns=["timestamp", "local_time", "open", "high", "low", "close", "volume"]
            )

        result = pd.concat(all_candles)
        result = result.sort_index(ascending=True)

        if len(result) > count:
            result = result.tail(count)

        return result

    @staticmethod
    def _get_days_per_candle(interval: CandleInterval) -> int:
        """간격당 일수 계산."""
        if interval == CandleInterval.DAY:
            return 1
        elif interval == CandleInterval.WEEK:
            return 7
        elif interval == CandleInterval.MONTH:
            return 30
        return 1

    @staticmethod
    def _build_candle_dataframe(data: list[dict]) -> pd.DataFrame:
        """캔들 데이터 리스트를 DataFrame으로 변환하고 UTC 인덱스 설정."""
        df = pd.DataFrame(data)

        # local_time을 America/New_York으로 해석하여 UTC로 변환
        local_index = pd.DatetimeIndex(df["local_time"]).tz_localize(TimeZone.NEW_YORK.value)
        utc_index = local_index.tz_convert(TimeZone.UTC.value)

        df["timestamp"] = utc_index.to_pydatetime()
        df = df.set_index(utc_index)
        df = df.sort_index(ascending=True)

        return df[["timestamp", "local_time", "open", "high", "low", "close", "volume"]]

    @staticmethod
    def _minute_response_to_dataframe(
            response: "OverseasMinuteCandleResponse"
    ) -> pd.DataFrame:
        """분봉 응답을 DataFrame으로 변환."""
        if not response.output2:
            return pd.DataFrame(
                columns=["timestamp", "local_time", "open", "high", "low", "close", "volume"]
            )

        data = []
        for candle in response.output2:
            # xymd: 일자 (YYYYMMDD), xhms: 시간 (HHMMSS)
            timestamp_str = f"{candle.xymd}{candle.xhms}"
            local_time = datetime.strptime(timestamp_str, "%Y%m%d%H%M%S")

            data.append({
                "local_time": local_time,  # America/New_York naive datetime
                "open": float(candle.open),
                "high": float(candle.high),
                "low": float(candle.low),
                "close": float(candle.last),
                "volume": float(candle.evol),
            })

        return HantuOverseasCandleClient._build_candle_dataframe(data)

    @staticmethod
    def _daily_response_to_dataframe(
            response: "OverseasDailyCandleResponse"
    ) -> pd.DataFrame:
        """일봉 응답을 DataFrame으로 변환."""
        if not response.candles:
            return pd.DataFrame(
                columns=["timestamp", "local_time", "open", "high", "low", "close", "volume"]
            )

        data = []
        for candle in response.candles:
            # stck_bsop_date: 영업 일자 (YYYYMMDD)
            local_time = datetime.strptime(candle.stck_bsop_date, "%Y%m%d")

            data.append({
                "local_time": local_time,  # America/New_York naive datetime
                "open": float(candle.ovrs_nmix_oprc),
                "high": float(candle.ovrs_nmix_hgpr),
                "low": float(candle.ovrs_nmix_lwpr),
                "close": float(candle.ovrs_nmix_prpr),
                "volume": float(candle.acml_vol),
            })

        return HantuOverseasCandleClient._build_candle_dataframe(data)


class HantuDomesticCandleClient(CandleClient):
    """Hantu Domestic API를 CandleClient로 래핑.

    기존 HantuDomesticAPI를 수정하지 않고 CandleClient를 구현합니다.
    분봉과 일봉 API가 분리되어 있으므로 내부적으로 분기 처리합니다.

    Example:
        >>> from src.hantu.domestic_api import HantuDomesticAPI
        >>> from src.providers.hantu_candle_client import HantuDomesticCandleClient
        >>> from src.common.candle_client import CandleInterval
        >>>
        >>> api = HantuDomesticAPI(config)
        >>> client = HantuDomesticCandleClient(api)
        >>> df = client.get_candles("005930", CandleInterval.DAY, count=100)
    """

    _DAILY_INTERVAL_MAP: dict[CandleInterval, ChartInterval] = {
        CandleInterval.DAY: ChartInterval.DAY,
        CandleInterval.WEEK: ChartInterval.WEEK,
        CandleInterval.MONTH: ChartInterval.MONTH,
    }

    # 분봉은 1분봉만 지원 (API 특성)
    _MINUTE_INTERVALS: set[CandleInterval] = {CandleInterval.MINUTE_1}

    # 휴장일(주말, 공휴일)을 고려한 날짜 범위 여유분
    _TRADING_DAY_MULTIPLIER: dict[CandleInterval, float] = {
        CandleInterval.DAY: 1.5,  # 주 5일 거래 + 공휴일 여유
        CandleInterval.WEEK: 1.1,  # 약간의 여유
        CandleInterval.MONTH: 1.0,  # 영향 없음
    }

    def __init__(self, api: HantuDomesticAPI) -> None:
        """HantuDomesticCandleClient 초기화.

        Args:
            api: Hantu Domestic API 인스턴스
        """
        self._api = api

    def get_candles(
            self,
            symbol: str,
            interval: CandleInterval,
            count: int = 100,
            end_time: datetime | None = None,
    ) -> DataFrame[CommonCandleSchema]:
        """캔들 데이터 조회.

        Args:
            symbol: 종목코드 (예: "005930")
            interval: 캔들 간격 (CandleInterval)
            count: 조회할 캔들 개수 (기본값: 100)
            end_time: 종료 시간 (해당 시간 이전 데이터 조회, UTC)

        Returns:
            표준 캔들 DataFrame[CommonCandleSchema]
            - index: DatetimeIndex (UTC)
            - columns: open, high, low, close, volume
        """
        if self._is_minute_interval(interval):
            df = self._get_minute_candles(symbol, count, end_time)
        else:
            df = self._get_daily_candles(symbol, interval, count, end_time)

        return CommonCandleSchema.validate(df)

    @property
    def supported_intervals(self) -> list[CandleInterval]:
        """지원하는 캔들 간격 목록."""
        return list(self._MINUTE_INTERVALS) + list(self._DAILY_INTERVAL_MAP.keys())

    def _is_minute_interval(self, interval: CandleInterval) -> bool:
        """분봉 타입인지 확인."""
        return interval in self._MINUTE_INTERVALS

    def _to_chart_interval(self, interval: CandleInterval) -> ChartInterval:
        """CandleInterval을 ChartInterval로 변환."""
        result = self._DAILY_INTERVAL_MAP.get(interval)
        if result is None:
            raise ValueError(f"일봉으로 변환할 수 없는 간격입니다: {interval}")
        return result

    def _get_minute_candles(
            self,
            symbol: str,
            count: int,
            end_time: datetime | None,
    ) -> pd.DataFrame:
        """분봉 데이터 조회.

        API가 한 번에 최대 120건만 반환하므로,
        count > 120일 때 여러 번 호출하여 결과를 병합합니다.

        페이징 방식:
        1. 첫 번째 조회: end_time부터 최대 120개
        2. 두 번째 조회: 첫 번째 조회의 가장 오래된 캔들 시간 - 1분 부터 120개
        3. 필요한 개수만큼 반복
        """
        # end_time이 없으면 현재 시간 (이미 KST)
        # end_time이 있으면 UTC이므로 KST로 변환 (+9시간)
        if end_time is None:
            current_kst_time = datetime.now()
        else:
            current_kst_time = end_time + timedelta(hours=9)

        all_candles: list[pd.DataFrame] = []
        remaining = count

        while remaining > 0:
            response = self._api.get_minute_chart(
                ticker=symbol,
                target_date=current_kst_time.date(),
                target_time=time_obj(current_kst_time.hour, current_kst_time.minute, current_kst_time.second),
            )

            df = self._minute_response_to_dataframe(response)

            if df.empty:
                break  # 더 이상 데이터 없음

            all_candles.append(df)
            remaining -= len(df)

            # 다음 조회를 위해 가장 오래된 캔들 시간 - 1분 설정
            # df.index는 UTC이므로 KST로 변환 (+9시간)
            oldest_utc = df.index.min().to_pydatetime()
            oldest_kst = oldest_utc + timedelta(hours=9)
            next_query_kst = oldest_kst - timedelta(minutes=1)

            # 장 시작 시간(09:00) 이전이면 전날 23:59로 설정
            # (시간만 바꾸면 안 되고, 전날 날짜 + 23:59로 해야 전날 데이터 조회 가능)
            if next_query_kst.hour < 9:
                prev_day = oldest_kst.date() - timedelta(days=1)
                current_kst_time = datetime.combine(prev_day, time_obj(23, 59, 0))
            else:
                current_kst_time = next_query_kst

        if not all_candles:
            return pd.DataFrame(
                columns=["timestamp", "local_time", "open", "high", "low", "close", "volume"]
            )

        # 모든 결과 병합 후 요청한 count만큼 반환
        result = pd.concat(all_candles)
        result = result.sort_index(ascending=True)  # 시간순 정렬

        if len(result) > count:
            result = result.tail(count)  # 최신 count개 반환

        return result

    def _get_daily_candles(
            self,
            symbol: str,
            interval: CandleInterval,
            count: int,
            end_time: datetime | None,
    ) -> pd.DataFrame:
        """일봉/주봉/월봉 데이터 조회.

        API가 한 번에 최대 100건만 반환하므로,
        count > 100일 때 여러 번 호출하여 결과를 병합합니다.
        휴장일(주말, 공휴일)을 고려한 여유분도 적용합니다.
        """
        chart_interval = self._to_chart_interval(interval)
        days_per_candle = self._get_days_per_candle(interval)
        multiplier = self._TRADING_DAY_MULTIPLIER.get(interval, 1.5)

        if end_time is None:
            current_end = datetime.now()
        else:
            current_end = end_time

        all_candles: list[pd.DataFrame] = []
        remaining = count

        while remaining > 0:
            # 이번 호출에서 목표 개수 (최대 100개)
            fetch_target = min(remaining, 100)

            # 휴장일 여유분 적용한 날짜 범위
            days_needed = int(fetch_target * days_per_candle * multiplier)
            start_date = current_end.date() - timedelta(days=days_needed)

            response = self._api.get_daily_chart(
                ticker=symbol,
                start_date=start_date,
                end_date=current_end.date(),
                interval=chart_interval,
            )

            df = self._daily_response_to_dataframe(response)

            if df.empty:
                break

            all_candles.append(df)
            remaining -= len(df)

            # 다음 조회를 위해 가장 오래된 캔들 날짜 - 1일
            oldest_date = df.index.min().to_pydatetime()
            current_end = oldest_date - timedelta(days=1)

        if not all_candles:
            return pd.DataFrame(
                columns=["timestamp", "local_time", "open", "high", "low", "close", "volume"]
            )

        result = pd.concat(all_candles)
        result = result.sort_index(ascending=True)

        if len(result) > count:
            result = result.tail(count)

        return result

    @staticmethod
    def _get_days_per_candle(interval: CandleInterval) -> int:
        """간격당 일수 계산."""
        if interval == CandleInterval.DAY:
            return 1
        elif interval == CandleInterval.WEEK:
            return 7
        elif interval == CandleInterval.MONTH:
            return 30
        return 1

    @staticmethod
    def _build_candle_dataframe(data: list[dict]) -> pd.DataFrame:
        """캔들 데이터 리스트를 DataFrame으로 변환하고 UTC 인덱스 설정."""
        df = pd.DataFrame(data)

        # local_time을 Asia/Seoul로 해석하여 UTC로 변환
        local_index = pd.DatetimeIndex(df["local_time"]).tz_localize("Asia/Seoul")
        utc_index = local_index.tz_convert("UTC")

        df["timestamp"] = utc_index.to_pydatetime()
        df = df.set_index(utc_index)
        df = df.sort_index(ascending=True)

        return df[["timestamp", "local_time", "open", "high", "low", "close", "volume"]]

    @staticmethod
    def _minute_response_to_dataframe(
            response: "MinuteChartResponseBody",
    ) -> pd.DataFrame:
        """분봉 응답을 DataFrame으로 변환."""
        if not response.output2:
            return pd.DataFrame(
                columns=["timestamp", "local_time", "open", "high", "low", "close", "volume"]
            )

        data = []
        for candle in response.output2:
            # stck_bsop_date: 영업 일자 (YYYYMMDD), stck_cntg_hour: 체결 시간 (HHMMSS)
            timestamp_str = f"{candle.stck_bsop_date}{candle.stck_cntg_hour}"
            local_time = datetime.strptime(timestamp_str, "%Y%m%d%H%M%S")

            data.append({
                "local_time": local_time,  # Asia/Seoul naive datetime
                "open": float(candle.stck_oprc),
                "high": float(candle.stck_hgpr),
                "low": float(candle.stck_lwpr),
                "close": float(candle.stck_prpr),
                "volume": float(candle.cntg_vol),
            })

        return HantuDomesticCandleClient._build_candle_dataframe(data)

    @staticmethod
    def _daily_response_to_dataframe(
            response: "DailyChartResponseBody",
    ) -> pd.DataFrame:
        """일봉 응답을 DataFrame으로 변환."""
        if not response.output2:
            return pd.DataFrame(
                columns=["timestamp", "local_time", "open", "high", "low", "close", "volume"]
            )

        data = []
        for candle in response.output2:
            # stck_bsop_date: 영업 일자 (YYYYMMDD)
            local_time = datetime.strptime(candle.stck_bsop_date, "%Y%m%d")

            data.append({
                "local_time": local_time,  # Asia/Seoul naive datetime
                "open": float(candle.stck_oprc),
                "high": float(candle.stck_hgpr),
                "low": float(candle.stck_lwpr),
                "close": float(candle.stck_clpr),
                "volume": float(candle.acml_vol),
            })

        return HantuDomesticCandleClient._build_candle_dataframe(data)
