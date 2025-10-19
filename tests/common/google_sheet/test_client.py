"""GoogleSheetClient 테스트"""

from unittest.mock import Mock, patch

import pytest
from gspread.exceptions import APIError

from src.common.google_sheet.client import GoogleSheetClient
from src.common.google_sheet.trade_record import TradeRecord
from src.config import GoogleSheetConfig


@pytest.fixture
def mock_config():
    """테스트용 GoogleSheetConfig"""
    return GoogleSheetConfig(
        google_sheet_url="https://docs.google.com/spreadsheets/test",
        credentials_path="tests/fixtures/test_credentials.json",
        sheet_name="test_sheet",
    )


@pytest.fixture
def mock_sheet():
    """테스트용 Mock Worksheet"""
    sheet = Mock()
    sheet.append_row.return_value = {"updates": {"updatedRows": 1}}
    return sheet


@pytest.fixture
def sample_trade_record():
    """테스트용 TradeRecord"""
    return TradeRecord(
        timestamp="2025-01-15 10:30:00",
        strategy_name="변동성돌파",
        order_type="매수",
        ticker="KRW-BTC",
        executed_volume=0.001,
        executed_price=50000000,
        executed_amount=50000,
    )


class TestGoogleSheetClientInit:
    """GoogleSheetClient 초기화 테스트"""

    def test_init_with_mock_sheet_success(self, mock_config, mock_sheet):
        """Mock 시트 주입으로 초기화 성공"""
        # Act
        client = GoogleSheetClient(mock_config, sheet=mock_sheet)

        # Assert (상태 검증)
        assert client.trades_sheet is mock_sheet

    @patch("src.common.google_sheet.client.gspread.service_account")
    def test_init_without_mock_creates_real_client(self, mock_service_account, mock_config):
        """Mock 없이 초기화 시 실제 클라이언트 생성"""
        # Arrange
        mock_gc = Mock()
        mock_doc = Mock()
        mock_worksheet = Mock()
        mock_service_account.return_value = mock_gc
        mock_gc.open_by_url.return_value = mock_doc
        mock_doc.worksheet.return_value = mock_worksheet

        # Act
        client = GoogleSheetClient(mock_config)

        # Assert (상태 검증)
        assert client.gc is mock_gc
        assert client.doc is mock_doc
        assert client.trades_sheet is mock_worksheet
        mock_service_account.assert_called_once_with(mock_config.credentials_path)
        mock_gc.open_by_url.assert_called_once_with(mock_config.google_sheet_url)
        mock_doc.worksheet.assert_called_once_with(mock_config.sheet_name)

    @patch("src.common.google_sheet.client.gspread.service_account")
    def test_init_with_api_error_raises_error(self, mock_service_account, mock_config):
        """API 오류 시 APIError 발생"""
        # Arrange
        mock_response = Mock()
        mock_response.json.return_value = {"error": {"code": 500, "message": "api error"}}
        mock_service_account.side_effect = APIError(mock_response)

        # Act & Assert
        with pytest.raises(APIError):
            GoogleSheetClient(mock_config)


class TestGoogleSheetClientAppendRow:
    """GoogleSheetClient.append_row 테스트"""

    def test_append_row_success(self, mock_config, mock_sheet, sample_trade_record):
        """거래 기록 추가 성공 (상태 검증)"""
        # Arrange
        client = GoogleSheetClient(mock_config, sheet=mock_sheet)

        # Act
        result = client.append_row(sample_trade_record)

        # Assert (상태 검증)
        assert result is True

    def test_append_row_calls_sheet_append_with_correct_data(self, mock_config, mock_sheet, sample_trade_record):
        """append_row가 올바른 데이터로 시트 메서드 호출"""
        # Arrange
        client = GoogleSheetClient(mock_config, sheet=mock_sheet)
        expected_data = sample_trade_record.to_list()

        # Act
        client.append_row(sample_trade_record)

        # Assert
        mock_sheet.append_row.assert_called_once_with(expected_data)

    def test_append_row_with_api_error_raises_error(self, mock_config, mock_sheet, sample_trade_record):
        """API 오류 시 APIError 발생"""
        # Arrange
        mock_response = Mock()
        mock_response.json.return_value = {"error": {"code": 500, "message": "api error"}}
        mock_sheet.append_row.side_effect = APIError(mock_response)
        client = GoogleSheetClient(mock_config, sheet=mock_sheet)

        # Act & Assert
        with pytest.raises(APIError):
            client.append_row(sample_trade_record)

    def test_append_row_retries_on_api_error_and_succeeds(self, mock_config, mock_sheet, sample_trade_record):
        """API 오류 발생 후 재시도하여 성공 (상태 검증)"""
        # Arrange
        mock_response = Mock()
        mock_response.json.return_value = {"error": {"code": 500, "message": "api error"}}
        # 처음 2번은 실패, 3번째는 성공
        mock_sheet.append_row.side_effect = [
            APIError(mock_response),
            APIError(mock_response),
            {"updates": {"updatedRows": 1}},
        ]
        client = GoogleSheetClient(mock_config, sheet=mock_sheet)

        # Act
        result = client.append_row(sample_trade_record)

        # Assert (상태 검증)
        assert result is True
        assert mock_sheet.append_row.call_count == 3

    def test_append_row_retries_max_attempts_then_raises(self, mock_config, mock_sheet, sample_trade_record):
        """최대 재시도 횟수 초과 시 APIError 발생 (상태 검증)"""
        # Arrange
        mock_response = Mock()
        mock_response.json.return_value = {"error": {"code": 500, "message": "api error"}}
        mock_sheet.append_row.side_effect = APIError(mock_response)
        client = GoogleSheetClient(mock_config, sheet=mock_sheet)

        # Act & Assert
        with pytest.raises(APIError):
            client.append_row(sample_trade_record)

        # 최대 3회 시도했는지 확인
        assert mock_sheet.append_row.call_count == 3
