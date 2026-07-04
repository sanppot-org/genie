"""GoogleSheetDataCollector.collect_price 부분 업데이트 테스트.

KIS 점검 등 외부 소스 장애 시에도 크래시하지 않고 성공한 소스만 시트에 갱신하는지 검증.
"""
from unittest.mock import Mock

import pandas as pd

from src.collector.price_data_collector import (
    DOMESTIC_GOLD_PRICE_ROW,
    INTERNATIONAL_GOLD_PRICE_ROW,
    USD_KRW_PRICE_ROW,
    GoogleSheetDataCollector,
)
from src.hantu.exceptions import HantuConnectionError


def _close_df(value: float) -> pd.DataFrame:
    return pd.DataFrame({"Close": [value]})


class TestCollectPrice:
    def _make(self):
        hantu = Mock()
        sheet = Mock()
        return GoogleSheetDataCollector(hantu, sheet), hantu, sheet

    def test_kis_failure_still_updates_fx_and_international(self, mocker):
        """국내 금(KIS) 실패 → 환율·국제 금 셀은 갱신되고 국내 금만 스킵, 예외 전파 없음."""
        collector, hantu, sheet = self._make()
        mocker.patch("src.collector.price_data_collector.fetch_yfinance", return_value=_close_df(1300.0))
        mocker.patch("src.collector.price_data_collector.fetch_finance_data_reader", return_value=_close_df(2400.0))
        hantu.get_stock_price.side_effect = HantuConnectionError("KIS 점검")

        collector.collect_price()

        sheet.batch_update.assert_called_once()
        rows = {u.row for u in sheet.batch_update.call_args[0][0]}
        assert USD_KRW_PRICE_ROW in rows
        assert INTERNATIONAL_GOLD_PRICE_ROW in rows
        assert DOMESTIC_GOLD_PRICE_ROW not in rows

    def test_fx_failure_skips_international_without_unbound_error(self, mocker):
        """환율(yfinance) 실패 → 국제 금도 스킵되고 UnboundLocalError 없음. 국내 금만 갱신."""
        collector, hantu, sheet = self._make()
        mocker.patch("src.collector.price_data_collector.fetch_yfinance", side_effect=Exception("yfinance 장애"))
        fdr = mocker.patch("src.collector.price_data_collector.fetch_finance_data_reader")
        hantu.get_stock_price.return_value.output.stck_prpr = "500000"

        collector.collect_price()

        rows = {u.row for u in sheet.batch_update.call_args[0][0]}
        assert rows == {DOMESTIC_GOLD_PRICE_ROW}
        fdr.assert_not_called()  # 환율 실패 시 국제 금 계산을 시도하지 않음

    def test_all_sources_fail_skips_batch_update(self, mocker):
        """성공한 소스가 하나도 없으면 batch_update를 호출하지 않는다."""
        collector, hantu, sheet = self._make()
        mocker.patch("src.collector.price_data_collector.fetch_yfinance", side_effect=Exception("장애"))
        hantu.get_stock_price.side_effect = HantuConnectionError("KIS 점검")

        collector.collect_price()

        sheet.batch_update.assert_not_called()
