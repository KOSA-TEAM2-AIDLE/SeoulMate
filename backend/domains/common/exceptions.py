class DomainNotRegisteredError(LookupError):
    """요청한 도메인이 Registry에 없을 때 발생한다."""


class DomainNotImplementedError(NotImplementedError):
    """팀 검색기 또는 외부 연동이 아직 연결되지 않았음을 명시한다."""


__all__ = ["DomainNotRegisteredError", "DomainNotImplementedError"]

