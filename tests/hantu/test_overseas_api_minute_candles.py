"""해외주식 API - 분봉 조회 테스트"""

import pytest

from src.config import HantuConfig
from src.hantu import HantuOverseasAPI
from src.hantu.model.domestic import AccountType
from src.hantu.model.overseas import OverseasMarketCode, OverseasMinuteInterval


class TestGetMinuteCandles:
    """get_minute_candles 메서드 테스트"""

    def test_get_minute_candles_single_page(self, mocker):
        """단일 페이지 응답 (연속 조회 불필요)"""
        # Given
        config = HantuConfig()
        api = HantuOverseasAPI(config, AccountType.VIRTUAL)

        # _get_token mock
        mocker.patch.object(api, '_get_token', return_value='mock_token')

        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.headers = {'tr_cont': 'D'}  # 마지막 페이지
        mock_response.json.return_value = {
            "rt_cd": "0",
            "msg_cd": "MCA00000",
            "msg1": "정상처리 되었습니다.",
            "output1": {
                "rsym": "DNASTSLA",
                "zdiv": "4",
                "stim": "040000",
                "etim": "200000",
                "sktm": "170000",
                "ektm": "090000",
                "next": "0",
                "more": "0",
                "nrec": "2",
            },
            "output2": [
                {
                    "tymd": "20240101",
                    "xymd": "20240101",
                    "xhms": "153000",
                    "kymd": "20240101",
                    "khms": "163000",
                    "open": "150.50",
                    "high": "151.00",
                    "low": "150.00",
                    "last": "150.75",
                    "evol": "1000000",
                    "eamt": "150000000",
                },
                {
                    "tymd": "20240101",
                    "xymd": "20240101",
                    "xhms": "152900",
                    "kymd": "20240101",
                    "khms": "162900",
                    "open": "149.00",
                    "high": "150.00",
                    "low": "148.50",
                    "last": "150.00",
                    "evol": "800000",
                    "eamt": "120000000",
                },
            ],
        }

        mocker.patch('requests.get', return_value=mock_response)

        # When
        result = api.get_minute_candles(symb="TSLA", nmin=OverseasMinuteInterval.MIN_1)

        # Then
        assert result.output1.rsym == "DNASTSLA"
        assert result.output1.nrec == "2"
        assert len(result.output2) == 2
        assert result.output2[0].xymd == "20240101"
        assert result.output2[0].xhms == "153000"
        assert result.output2[0].last == "150.75"
        assert result.output2[1].xymd == "20240101"
        assert result.output2[1].xhms == "152900"
        assert result.output2[1].last == "150.00"

    def test_get_minute_candles_multiple_pages(self, mocker):
        """다중 페이지 응답 (연속 조회 필요)"""
        # Given
        config = HantuConfig()
        api = HantuOverseasAPI(config, AccountType.VIRTUAL)

        # _get_token mock
        mocker.patch.object(api, '_get_token', return_value='mock_token')

        # 첫 번째 페이지 응답
        first_response = mocker.Mock()
        first_response.status_code = 200
        first_response.headers = {'tr_cont': 'M'}  # 다음 페이지 존재
        first_response.json.return_value = {
            "rt_cd": "0",
            "msg_cd": "MCA00000",
            "msg1": "정상처리 되었습니다.",
            "output1": {
                "rsym": "DNASTSLA",
                "zdiv": "4",
                "stim": "040000",
                "etim": "200000",
                "sktm": "170000",
                "ektm": "090000",
                "next": "1",
                "more": "1",
                "nrec": "1",
            },
            "output2": [
                {
                    "tymd": "20240101",
                    "xymd": "20240101",
                    "xhms": "153000",
                    "kymd": "20240101",
                    "khms": "163000",
                    "open": "150.50",
                    "high": "151.00",
                    "low": "150.00",
                    "last": "150.75",
                    "evol": "1000000",
                    "eamt": "150000000",
                }
            ],
        }

        # 두 번째 페이지 응답
        second_response = mocker.Mock()
        second_response.status_code = 200
        second_response.headers = {'tr_cont': 'D'}  # 마지막 페이지
        second_response.json.return_value = {
            "rt_cd": "0",
            "msg_cd": "MCA00000",
            "msg1": "정상처리 되었습니다.",
            "output1": {
                "rsym": "DNASTSLA",
                "zdiv": "4",
                "stim": "040000",
                "etim": "200000",
                "sktm": "170000",
                "ektm": "090000",
                "next": "0",
                "more": "0",
                "nrec": "1",
            },
            "output2": [
                {
                    "tymd": "20240101",
                    "xymd": "20240101",
                    "xhms": "152900",
                    "kymd": "20240101",
                    "khms": "162900",
                    "open": "149.00",
                    "high": "150.00",
                    "low": "148.50",
                    "last": "150.00",
                    "evol": "800000",
                    "eamt": "120000000",
                }
            ],
        }

        mock_get = mocker.patch('requests.get')
        mock_get.side_effect = [first_response, second_response]

        # When
        result = api.get_minute_candles(symb="TSLA", nmin=OverseasMinuteInterval.MIN_1)

        # Then
        assert result.output1.rsym == "DNASTSLA"
        assert len(result.output2) == 2
        assert result.output2[0].xymd == "20240101"
        assert result.output2[0].xhms == "153000"
        assert result.output2[0].last == "150.75"
        assert result.output2[1].xymd == "20240101"
        assert result.output2[1].xhms == "152900"
        assert result.output2[1].last == "150.00"

        # 두 번째 호출 확인
        assert mock_get.call_count == 2

    def test_get_minute_candles_with_parameters(self, mocker):
        """파라미터가 올바르게 전달되는지 확인"""
        # Given
        config = HantuConfig()
        api = HantuOverseasAPI(config, AccountType.VIRTUAL)

        # _get_token mock
        mocker.patch.object(api, '_get_token', return_value='mock_token')

        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.headers = {'tr_cont': 'D'}
        mock_response.json.return_value = {
            "rt_cd": "0",
            "msg_cd": "MCA00000",
            "msg1": "정상처리 되었습니다.",
            "output1": {
                "rsym": "DNYSAAPL",
                "zdiv": "4",
                "stim": "040000",
                "etim": "200000",
                "sktm": "170000",
                "ektm": "090000",
                "next": "0",
                "more": "0",
                "nrec": "0",
            },
            "output2": [],
        }

        mock_get = mocker.patch('requests.get', return_value=mock_response)

        # When
        api.get_minute_candles(
            symb="AAPL",
            excd=OverseasMarketCode.NYS,
            nmin=OverseasMinuteInterval.MIN_5,
            include_previous=True,
            limit=60
        )

        # Then
        call_params = mock_get.call_args[1]['params']
        assert call_params['SYMB'] == "AAPL"
        assert call_params['EXCD'] == "NYS"
        assert call_params['NMIN'] == "5"
        assert call_params['PINC'] == "1"
        assert call_params['NREC'] == "60"

    def test_get_minute_candles_error(self, mocker):
        """API 에러 응답"""
        # Given
        config = HantuConfig()
        api = HantuOverseasAPI(config, AccountType.VIRTUAL)

        # _get_token mock
        mocker.patch.object(api, '_get_token', return_value='mock_token')

        mock_response = mocker.Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"

        mocker.patch('requests.get', return_value=mock_response)

        # When & Then
        with pytest.raises(Exception, match="Error: Bad Request"):
            api.get_minute_candles(symb="TSLA", nmin=OverseasMinuteInterval.MIN_1)
