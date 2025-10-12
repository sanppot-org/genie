from datetime import datetime, timedelta, timezone

from src.hantu.model.access_token import ResponseBody

# KST = UTC+9
KST = timezone(timedelta(hours=9))


class TestResponseBody:
    def test_is_expired_만료된_토큰(self):
        """만료된 토큰은 True 반환"""
        expired_time = datetime.now(KST) - timedelta(hours=1)
        response = ResponseBody(
            access_token="test_token",
            token_type="Bearer",
            expires_in=86400.0,
            access_token_token_expired=expired_time,
        )

        assert response.is_expired() is True

    def test_is_expired_만료되지_않은_토큰(self):
        """만료되지 않은 토큰은 False 반환"""
        future_time = datetime.now(KST) + timedelta(hours=1)
        response = ResponseBody(
            access_token="test_token",
            token_type="Bearer",
            expires_in=86400.0,
            access_token_token_expired=future_time,
        )

        assert response.is_expired() is False

    def test_is_expired_버퍼_시간_고려(self):
        """버퍼 시간 내 토큰은 만료로 간주"""
        # 3분 후 만료 (기본 버퍼 5분보다 작음)
        near_expiry_time = datetime.now(KST) + timedelta(minutes=3)
        response = ResponseBody(
            access_token="test_token",
            token_type="Bearer",
            expires_in=86400.0,
            access_token_token_expired=near_expiry_time,
        )

        assert response.is_expired() is True  # 기본 버퍼 300초(5분)
        assert response.is_expired(buffer_seconds=0) is False  # 버퍼 없으면 유효

    def test_is_expired_버퍼_시간_커스터마이징(self):
        """커스텀 버퍼 시간 적용"""
        # 10분 후 만료
        expiry_time = datetime.now(KST) + timedelta(minutes=10)
        response = ResponseBody(
            access_token="test_token",
            token_type="Bearer",
            expires_in=86400.0,
            access_token_token_expired=expiry_time,
        )

        assert response.is_expired(buffer_seconds=300) is False  # 5분 버퍼: 유효
        assert response.is_expired(buffer_seconds=900) is True  # 15분 버퍼: 만료
