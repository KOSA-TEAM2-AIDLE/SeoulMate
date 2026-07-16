from domains.common.models import DomainSearchRequest
from vector_db.attraction.search import AttractionVectorSearch, VectorSearchHit


class AttractionRepository:
    """관광지·행사 Vector DB 검색 경계."""

    implemented = True

    def __init__(self, *, vector_search: AttractionVectorSearch | None = None) -> None:
        self._vector_search = vector_search or AttractionVectorSearch()

    def search(self, request: DomainSearchRequest) -> list[VectorSearchHit]:
        return self._vector_search.search(request)


__all__ = ["AttractionRepository"]
