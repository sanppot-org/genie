from datetime import datetime, timedelta, timezone

from pydantic import BaseModel

# KST = UTC+9
KST = timezone(timedelta(hours=9))


class RequestBody(BaseModel):
    appkey: str  # 앱키
    appsecret: str  # 앱시크릿키
    grant_type: str = "client_credentials"  # 권한부여 Type


class ResponseBody(BaseModel):
    access_token: str  # 접근토큰
    token_type: str  # 접근토큰유형
    expires_in: float  # 접근토큰 유효기간
    access_token_token_expired: datetime  # 접근토큰 유효기간(일시표시) 2022-08-30 08:10:10

    def is_expired(self, buffer_seconds: int = 300) -> bool:
        """토큰 만료 여부 확인 (KST 기준)

        Args:
            buffer_seconds: 만료 여유 시간 (초). 기본값 300초(5분)

        Returns:
            만료되었으면 True, 아니면 False
        """
        # 현재 시간을 KST로 가져옴
        now_kst = datetime.now(KST)
        # API 응답 시간을 KST로 간주
        expired_kst = self.access_token_token_expired.replace(tzinfo=KST)
        return now_kst >= expired_kst - timedelta(seconds=buffer_seconds)
