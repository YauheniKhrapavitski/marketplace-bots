class OzonError(Exception):
    pass


class OzonAuthError(OzonError):
    def __init__(self, message: str, status_code: int = 0, detail: str = "") -> None:
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


class OzonRateLimitError(OzonError):
    pass


class OzonRequestError(OzonError):
    def __init__(self, status_code: int, message: str, detail: str = "") -> None:
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail
