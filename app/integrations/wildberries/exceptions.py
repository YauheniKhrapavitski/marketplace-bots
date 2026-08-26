class WildberriesError(Exception):
    pass


class WildberriesAuthError(WildberriesError):
    pass


class WildberriesRateLimitError(WildberriesError):
    def __init__(self, message: str, retry_after_seconds: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class WildberriesRequestError(WildberriesError):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
