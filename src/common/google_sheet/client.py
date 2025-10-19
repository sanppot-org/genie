"""Google Sheets API 클라이언트 모듈"""

import logging

import gspread
from gspread import Spreadsheet, Worksheet
from gspread.exceptions import APIError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.common.google_sheet.trade_record import TradeRecord
from src.config import GoogleSheetConfig
from src.strategy.order.execution_result import ExecutionResult

logger = logging.getLogger(__name__)


class GoogleSheetClient:
    """
    Google Sheets API를 사용하여 거래 기록을 관리하는 클라이언트.

    이 클라이언트는 Google Sheets에 거래 기록을 추가하는 기능을 제공합니다.
    테스트 환경에서는 Mock 객체를 주입하여 사용할 수 있습니다.

    Attributes:
        gc: gspread 클라이언트 인스턴스
        doc: Google Spreadsheet 문서
        trades_sheet: 거래 기록 워크시트

    Examples:
        >>> from src.config import GoogleSheetConfig
        >>> from src.models.trade_record import TradeRecord
        >>>
        >>> # 프로덕션 환경
        >>> config = GoogleSheetConfig()
        >>> client = GoogleSheetClient(config)
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
        >>>
        >>> # 테스트 환경 (Mock 주입)
        >>> from unittest.mock import Mock
        >>> mock_sheet = Mock()
        >>> test_client = GoogleSheetClient(config, sheet=mock_sheet)
    """

    gc: gspread.Client
    doc: Spreadsheet
    trades_sheet: Worksheet

    def __init__(self, google_sheet_config: GoogleSheetConfig, sheet: Worksheet | None = None) -> None:
        """
        Google Sheet 클라이언트를 초기화합니다.

        프로덕션 환경에서는 실제 Google Sheets API에 연결하고,
        테스트 환경에서는 Mock 객체를 주입받아 사용할 수 있습니다.

        Args:
            google_sheet_config: Google Sheet 설정 (URL, 인증 파일 경로, 시트 이름)
            sheet: 테스트용 Mock Worksheet (선택사항). None이면 실제 API 사용.

        Raises:
            APIError: Google Sheets API 호출 실패 시
                - 인증 파일을 찾을 수 없을 때
                - 스프레드시트를 찾을 수 없을 때
                - 워크시트를 찾을 수 없을 때

        Examples:
            >>> # 프로덕션 환경
            >>> config = GoogleSheetConfig()
            >>> client = GoogleSheetClient(config)
            >>>
            >>> # 테스트 환경
            >>> from unittest.mock import Mock
            >>> mock_sheet = Mock()
            >>> test_client = GoogleSheetClient(config, sheet=mock_sheet)
        """
        if sheet is None:
            self.gc = gspread.service_account(google_sheet_config.credentials_path)
            self.doc = self.gc.open_by_url(google_sheet_config.google_sheet_url)
            sheet = self.doc.worksheet(google_sheet_config.sheet_name)

        self.trades_sheet = sheet

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
            >>> from src.models.trade_record import TradeRecord
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
        self.trades_sheet.append_row(trade_record.to_list())
        return True

    def append_order_result(self, result: ExecutionResult) -> None:
        record = TradeRecord.from_result(result)
        self.append_row(record)
