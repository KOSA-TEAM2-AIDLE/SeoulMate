"""API 명세서 3-3 /places 참고. 1단계: mock JSON 스코어링. 2단계: 벡터 DB(RAG) 연결."""
from schemas.common import Place


def search_places(query: str, lang: str = "ko") -> list[Place]:
    """query와 관련도 높은 장소를 score 내림차순으로 반환."""
    raise NotImplementedError
