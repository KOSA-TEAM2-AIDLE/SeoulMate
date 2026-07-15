"""application/API에서 공통으로 처리할 서비스 오류."""


class SeoulMateError(Exception):
    pass


class ExternalServiceUnavailable(SeoulMateError):
    pass


class InvalidModelSelection(SeoulMateError):
    pass

