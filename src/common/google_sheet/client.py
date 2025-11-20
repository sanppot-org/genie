"""Google Sheets API 클라이언트 모듈"""

import logging

import gspread
from gspread.exceptions import APIError
import pandas as pd
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.common.google_sheet.cell_update import CellUpdate
from src.common.google_sheet.trade_record import TradeRecord
from src.config import GoogleSheetConfig
from src.strategy.order.execution_result import ExecutionResult

logger = logging.getLogger(__name__)


class GoogleSheetClient:
    """
    Google Sheets API를 사용하여 거래 기록을 관리하는 클라이언트.

    이 클라이언트는 Google Sheets에 거래 기록을 추가하는 기능을 제공합니다.

    Attributes:
        gc: gspread 클라이언트 인스턴스
        doc: Google Spreadsheet 문서
        sheet: 거래 기록 워크시트

    Examples:
        >>> from src.config import GoogleSheetConfig
        >>> from src.common.google_sheet.trade_record import TradeRecord
        >>>
        >>> config = GoogleSheetConfig()
        >>> client = GoogleSheetClient(config, sheet_name="trades")
        >>>
        >>> # 거래 기록 추가
        >>> record = TradeRecord(
        ...     timestamp="2025-01-15 10:30:00",
        ...     strategy_name="변동성돌파",
        ...     order_type="매수",
        ...     ticker="KRW-BTC",
        ...     executed_volume=0.001,
        ...     executed_price=50000000,
        ...     executed_amount=50000,
        ... )
        >>> client.append_row(record)
        True
    """

    def __init__(self, google_sheet_config: GoogleSheetConfig, sheet_name: str) -> None:
        """
        Google Sheet 클라이언트를 초기화합니다.

        Args:
            google_sheet_config: Google Sheet 설정 (URL, 인증 파일 경로)
            sheet_name: 사용할 워크시트 이름

        Raises:
            APIError: Google Sheets API 호출 실패 시
                - 인증 파일을 찾을 수 없을 때
                - 스프레드시트를 찾을 수 없을 때
                - 워크시트를 찾을 수 없을 때

        Examples:
            >>> config = GoogleSheetConfig()
            >>> client = GoogleSheetClient(config, sheet_name="trades")
        """
        self.gc = gspread.service_account(google_sheet_config.credentials_path)
        self.doc = self.gc.open_by_url(google_sheet_config.google_sheet_url)
        self.sheet = self.doc.worksheet(sheet_name)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(APIError),
        reraise=True,
    )
    def append_row(self, trade_record: TradeRecord) -> bool:
        """
        거래 기록을 시트에 추가합니다.

        네트워크 오류 발생 시 최대 3회까지 자동으로 재시도합니다.
        재시도 간격은 exponential backoff 전략을 사용합니다 (1초 ~ 10초).

        Args:
            trade_record: 추가할 거래 기록

        Returns:
            bool: 성공 여부 (True: 성공)

        Raises:
            APIError: Google Sheets API 호출 실패 시 (재시도 후에도 실패)

        Examples:
            >>> from src.common.google_sheet.trade_record import TradeRecord
            >>> record = TradeRecord(
            ...     timestamp="2025-01-15 10:30:00",
            ...     strategy_name="변동성돌파",
            ...     order_type="매수",
            ...     ticker="KRW-BTC",
            ...     executed_volume=0.001,
            ...     executed_price=50000000,
            ...     executed_amount=50000,
            ... )
            >>> client.append_row(record)
            True
        """
        self.sheet.append_row(trade_record.to_list())
        return True

    def append_order_result(self, result: ExecutionResult) -> None:
        record = TradeRecord.from_result(result)
        self.append_row(record)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(APIError),
        reraise=True,
    )
    def set(self, row: int, col: int, value: str | float | int) -> None:
        self.sheet.update_cell(row, col, value)

    def set_now(self, row: int, col: int) -> None:
        from datetime import datetime
        self.set(row, col, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(APIError),
        reraise=True,
    )
    def batch_update(self, updates: list[CellUpdate]) -> None:
        """
        여러 셀을 한 번의 API 호출로 업데이트합니다 (서식 유지).

        Args:
            updates: CellUpdate 객체의 리스트

        Examples:
            >>> from src.common.google_sheet.cell_update import CellUpdate
            >>> client.batch_update([
            ...     CellUpdate(row=1, col=1, value=100),
            ...     CellUpdate(row=1, col=2, value="2025-01-15 10:30:00")
            ... ])
        """
        batch_data = []
        for update in updates:
            row, col, value = update.to_tuple()
            # row, col을 A1 notation으로 변환 (예: 1, 1 -> "A1")
            cell_address = gspread.utils.rowcol_to_a1(row, col)
            batch_data.append({
                'range': cell_address,
                'values': [[value]]
            })
        self.sheet.batch_update(batch_data)

    def _convert_value(self, value: object) -> str | float | int:
        """
        NaN/None을 빈 문자열로 변환합니다.

        Args:
            value: 변환할 값

        Returns:
            str | float | int: NaN/None이면 빈 문자열, 아니면 원래 값
        """
        if pd.isna(value):
            return ""
        return value

    def _create_updates_from_series(
        self,
        series: pd.Series,
        start_row: int,
        start_col: int
    ) -> list[CellUpdate]:
        """
        Series를 CellUpdate 리스트로 변환합니다.

        Args:
            series: 변환할 Series
            start_row: 시작 행 번호
            start_col: 시작 열 번호

        Returns:
            list[CellUpdate]: 변환된 CellUpdate 리스트
        """
        updates: list[CellUpdate] = []

        for row_idx, (index_val, value) in enumerate(series.items()):
            current_row = start_row + row_idx

            # 인덱스를 첫 번째 열에 추가
            updates.append(CellUpdate(
                row=current_row,
                col=start_col,
                value=str(index_val)
            ))

            # 값을 두 번째 열에 추가
            updates.append(CellUpdate(
                row=current_row,
                col=start_col + 1,
                value=self._convert_value(value)
            ))

        return updates

    def _create_updates_from_dataframe(
        self,
        df: pd.DataFrame,
        start_row: int,
        start_col: int
    ) -> list[CellUpdate]:
        """
        DataFrame을 CellUpdate 리스트로 변환합니다.

        Args:
            df: 변환할 DataFrame
            start_row: 시작 행 번호
            start_col: 시작 열 번호

        Returns:
            list[CellUpdate]: 변환된 CellUpdate 리스트
        """
        updates: list[CellUpdate] = []

        for row_idx, (index_val, row_data) in enumerate(df.iterrows()):
            current_row = start_row + row_idx

            # 인덱스를 첫 번째 열에 추가
            updates.append(CellUpdate(
                row=current_row,
                col=start_col,
                value=str(index_val)
            ))

            # 데이터 값들을 다음 열부터 추가
            for col_idx, value in enumerate(row_data):
                current_col = start_col + 1 + col_idx

                updates.append(CellUpdate(
                    row=current_row,
                    col=current_col,
                    value=self._convert_value(value)
                ))

        return updates

    def batch_update_from_dataframe(
        self,
        df: pd.DataFrame | pd.Series,
        start_row: int,
        start_col: int
    ) -> None:
        """
        DataFrame 또는 Series를 지정된 시작 셀부터 batch update합니다.

        Args:
            df: 업데이트할 DataFrame 또는 Series (인덱스 포함, 컬럼명 제외)
            start_row: 시작 행 번호 (1부터 시작)
            start_col: 시작 열 번호 (1부터 시작)

        Examples:
            >>> import pandas as pd
            >>> # DataFrame 예시
            >>> df = pd.DataFrame({
            ...     'A': [1, 2, None],
            ...     'B': [4.5, 5.5, 6.5]
            ... }, index=['row1', 'row2', 'row3'])
            >>> client.batch_update_from_dataframe(df, start_row=2, start_col=1)
            >>>
            >>> # Series 예시
            >>> series = pd.Series([100, 200, None], index=['A', 'B', 'C'])
            >>> client.batch_update_from_dataframe(series, start_row=2, start_col=1)
        """
        if isinstance(df, pd.Series):
            updates = self._create_updates_from_series(df, start_row, start_col)
        else:
            updates = self._create_updates_from_dataframe(df, start_row, start_col)

        self.batch_update(updates)
