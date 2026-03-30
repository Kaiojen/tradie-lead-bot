from __future__ import annotations


class DomainError(Exception):
    def __init__(self, status_code: int, error: str, detail: str | None = None) -> None:
        super().__init__(detail or error)
        self.status_code = status_code
        self.error = error
        self.detail = detail
