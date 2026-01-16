"""Hantu Overseas API를 CandleClient Protocol로 래핑하는 클라이언트."""

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import pandas as pd
from pandera.typing import DataFrame

from src.common.candle_client import CandleInterval
from src.common.candle_schema import CommonCandleSchema
from src.hantu.model.overseas.candle_period import OverseasCandlePeriod
from src.hantu.model.overseas.minute_interval import OverseasMinuteInterval
from src.hantu.overseas_api import HantuOverseasAPI

if TYPE_CHECKING:
    from src.hantu.model.overseas.price import (
        OverseasDailyCandleResponse,
        OverseasMinuteCandleResponse,
    )


class HantuCandleClient:
    """Hantu Overseas API를 CandleClient Protocol로 래핑.

    기존 HantuOverseasAPI를 수정하지 않고 CandleClient Protocol을 구현합니다.
    분봉과 일봉 API가 분리되어 있으므로 내부적으로 분기 처리합니다.

    Example:
        >>> from src.hantu.overseas_api import HantuOverseasAPI
        >>> from src.providers.hantu_candle_client import HantuCandleClient
        >>> from src.common.candle_client import CandleInterval
        >>>
        >>> api = HantuOverseasAPI(config)
        >>> client = HantuCandleClient(api)
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
        """분봉 데이터 조회."""
        minute_interval = self._to_minute_interval(interval)

        response = self._api.get_minute_candles(
            symbol=symbol,
            minute_interval=minute_interval,
            limit=min(count, 120),  # 최대 120개
        )

        return self._minute_response_to_dataframe(response)

    def _get_daily_candles(
            self,
            symbol: str,
            interval: CandleInterval,
            count: int,
            end_time: datetime | None,
    ) -> pd.DataFrame:
        """일봉/주봉/월봉 데이터 조회."""
        period = self._to_daily_period(interval)

        # end_time이 없으면 오늘
        if end_time is None:
            end_time = datetime.now()

        # count 기반으로 start_date 계산
        days_per_candle = self._get_days_per_candle(interval)
        start_time = end_time - timedelta(days=count * days_per_candle)

        response = self._api.get_daily_candles(
            symbol=symbol,
            start_date=start_time.strftime("%Y%m%d"),
            end_date=end_time.strftime("%Y%m%d"),
            period=period,
        )

        return self._daily_response_to_dataframe(response)

    def _get_days_per_candle(self, interval: CandleInterval) -> int:
        """간격당 일수 계산."""
        if interval == CandleInterval.DAY:
            return 1
        elif interval == CandleInterval.WEEK:
            return 7
        elif interval == CandleInterval.MONTH:
            return 30
        return 1

    def _minute_response_to_dataframe(
            self, response: "OverseasMinuteCandleResponse"
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

        df = pd.DataFrame(data)

        # local_time을 America/New_York으로 해석하여 UTC로 변환
        local_index = pd.DatetimeIndex(df["local_time"]).tz_localize("America/New_York")
        utc_index = local_index.tz_convert("UTC")

        df["timestamp"] = utc_index.to_pydatetime()
        df = df.set_index(utc_index)
        df = df.sort_index(ascending=True)

        return df[["timestamp", "local_time", "open", "high", "low", "close", "volume"]]

    def _daily_response_to_dataframe(
            self, response: "OverseasDailyCandleResponse"
    ) -> pd.DataFrame:
        """일봉 응답을 DataFrame으로 변환."""
        if not response.output1:
            return pd.DataFrame(
                columns=["timestamp", "local_time", "open", "high", "low", "close", "volume"]
            )

        data = []
        for candle in response.output1:
            # xymd: 일자 (YYYYMMDD)
            local_time = datetime.strptime(candle.xymd, "%Y%m%d")

            data.append({
                "local_time": local_time,  # America/New_York naive datetime
                "open": float(candle.open),
                "high": float(candle.high),
                "low": float(candle.low),
                "close": float(candle.clos),
                "volume": float(candle.tvol),
            })

        df = pd.DataFrame(data)

        # local_time을 America/New_York으로 해석하여 UTC로 변환
        local_index = pd.DatetimeIndex(df["local_time"]).tz_localize("America/New_York")
        utc_index = local_index.tz_convert("UTC")

        df["timestamp"] = utc_index.to_pydatetime()
        df = df.set_index(utc_index)
        df = df.sort_index(ascending=True)

        return df[["timestamp", "local_time", "open", "high", "low", "close", "volume"]]
