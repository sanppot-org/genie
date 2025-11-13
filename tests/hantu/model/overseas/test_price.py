"""해외주식 시세 조회 모델 테스트"""

from pydantic import ValidationError
import pytest

from src.hantu.model.overseas.price import (
    OverseasMinuteCandleData,
    OverseasMinuteCandleResponse,
)


class TestOverseasMinuteCandleData:
    """OverseasMinuteCandleData 모델 테스트"""

    def test_valid_minute_candle_data(self):
        """유효한 분봉 데이터 생성"""
        # Given
        data = {
            "tymd": "20251013",
            "xymd": "20251013",
            "xhms": "195900",
            "kymd": "20251014",
            "khms": "085900",
            "open": "247.3185",
            "high": "247.3800",
            "low": "247.2600",
            "last": "247.3800",
            "evol": "1090",
            "eamt": "269525",
        }

        # When
        candle = OverseasMinuteCandleData(**data)

        # Then
        assert candle.tymd == "20251013"
        assert candle.xymd == "20251013"
        assert candle.xhms == "195900"
        assert candle.kymd == "20251014"
        assert candle.khms == "085900"
        assert candle.open == "247.3185"
        assert candle.high == "247.3800"
        assert candle.low == "247.2600"
        assert candle.last == "247.3800"
        assert candle.evol == "1090"
        assert candle.eamt == "269525"

    def test_missing_required_fields(self):
        """필수 필드 누락 시 검증 에러"""
        # Given
        data = {
            "tymd": "20251013",
            "xymd": "20251013",
            "open": "247.3185",
            # xhms, kymd, khms, high, low, last, evol, eamt 누락
        }

        # When & Then
        with pytest.raises(ValidationError):
            OverseasMinuteCandleData(**data)


class TestOverseasMinuteCandleResponse:
    """OverseasMinuteCandleResponse 모델 테스트"""

    def test_valid_minute_candle_response(self):
        """유효한 분봉 응답 생성"""
        # Given
        data = {
            "output1": {
                "rsym": "DNASAAPL",
                "zdiv": "4",
                "stim": "040000",
                "etim": "200000",
                "sktm": "170000",
                "ektm": "090000",
                "next": "1",
                "more": "0",
                "nrec": "120",
            },
            "output2": [
                {
                    "tymd": "20251013",
                    "xymd": "20251013",
                    "xhms": "195900",
                    "kymd": "20251014",
                    "khms": "085900",
                    "open": "247.3185",
                    "high": "247.3800",
                    "low": "247.2600",
                    "last": "247.3800",
                    "evol": "1090",
                    "eamt": "269525",
                },
                {
                    "tymd": "20251013",
                    "xymd": "20251013",
                    "xhms": "195800",
                    "kymd": "20251014",
                    "khms": "085800",
                    "open": "247.3301",
                    "high": "247.3500",
                    "low": "247.2700",
                    "last": "247.2700",
                    "evol": "858",
                    "eamt": "212187",
                },
            ],
        }

        # When
        response = OverseasMinuteCandleResponse(**data)

        # Then
        assert response.output1.rsym == "DNASAAPL"
        assert response.output1.nrec == "120"
        assert len(response.output2) == 2
        assert response.output2[0].xymd == "20251013"
        assert response.output2[0].xhms == "195900"
        assert response.output2[0].last == "247.3800"
        assert response.output2[1].xymd == "20251013"
        assert response.output2[1].xhms == "195800"
        assert response.output2[1].last == "247.2700"

    def test_empty_output2(self):
        """빈 output2 (조회 결과 없음)"""
        # Given
        data = {
            "output1": {
                "rsym": "DNASAAPL",
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

        # When
        response = OverseasMinuteCandleResponse(**data)

        # Then
        assert response.output1.rsym == "DNASAAPL"
        assert len(response.output2) == 0

    def test_default_output2(self):
        """output2 기본값 테스트"""
        # Given
        data = {
            "output1": {
                "rsym": "DNASAAPL",
                "zdiv": "4",
                "stim": "040000",
                "etim": "200000",
                "sktm": "170000",
                "ektm": "090000",
                "next": "0",
                "more": "0",
                "nrec": "0",
            }
        }

        # When
        response = OverseasMinuteCandleResponse(**data)

        # Then
        assert response.output1.rsym == "DNASAAPL"
        assert response.output2 == []
