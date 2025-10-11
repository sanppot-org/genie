class UpbitAPIError(Exception):
    """
    업비트 API 에러

    업비트 API 호출 시 발생하는 에러를 나타냅니다.
    """

    def __init__(self, error_info: dict[str, str]):
        self.message = error_info['message']
        self.name = error_info['name']
        super().__init__(f"Upbit API Error [{self.name}]: {self.message}")

    @classmethod
    def empty_response(cls) -> "UpbitAPIError":
        """API 응답이 비어있는 경우의 에러를 생성합니다."""
        return cls({'name': 'empty_response', 'message': 'API 응답이 비어있습니다'})
