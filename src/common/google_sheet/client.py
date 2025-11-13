"""Google Sheets API 클라이언트 모듈"""

import logging

import gspread
from gspread.exceptions import APIError
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
        여러 셀을 한 번의 API 호출로 업데이트합니다.

        Args:
            updates: CellUpdate 객체의 리스트

        Examples:
            >>> from src.common.google_sheet.cell_update import CellUpdate
            >>> client.batch_update([
            ...     CellUpdate(row=1, col=1, value=100),
            ...     CellUpdate(row=1, col=2, value="2025-01-15 10:30:00")
            ... ])
        """
        cells = []
        for update in updates:
            row, col, value = update.to_tuple()
            cells.append(gspread.cell.Cell(row, col, str(value)))
        self.sheet.update_cells(cells)
