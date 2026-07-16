"""카페·리뷰 pgvector 검색을 담당하는 repository."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
import json
from typing import Any, Literal, Protocol

from core.config import (
    DB_CONFIG,
    OPENAI_API_KEY,
    OPENAI_EMBED_DIM,
    OPENAI_EMBED_MODEL,
)


Language = Literal["ko", "en"]
DEFAULT_CAFE_VECTOR_LIMIT = 30
DEFAULT_REVIEW_VECTOR_POOL = 100
DEFAULT_REVIEWS_PER_CAFE = 3


class QueryEmbedder(Protocol):
    def embed(self, text: str) -> list[float]: ...


@dataclass(frozen=True)
class CafeVectorHit:
    cafe_id: int
    rank: int
    similarity: float


@dataclass(frozen=True)
class ReviewVectorHit:
    review_id: int
    cafe_id: int
    content: str
    rank: int
    similarity: float
    word_count: int


@dataclass(frozen=True)
class CafeRecord:
    id: int
    name: str
    category: str | None
    rating: float | None
    review_count: int
    address: str
    phone: str | None
    postal_code: str | None
    hours: str | None
    description: str | None
    image: str | None
    link: str | None
    lat: float
    lng: float


@dataclass(frozen=True)
class CafeRetrievalResult:
    query: str
    language: Language
    cafe_hits: tuple[CafeVectorHit, ...]
    review_hits_by_cafe: dict[int, tuple[ReviewVectorHit, ...]]
    cafes: dict[int, CafeRecord]


class OpenAIQueryEmbedder:
    """운영 설정과 동일한 모델·차원으로 검색어 임베딩을 생성한다."""

    def __init__(self) -> None:
        from openai import OpenAI

        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY가 설정되어 있지 않습니다.")
        self._client = OpenAI(api_key=OPENAI_API_KEY)

    def embed(self, text: str) -> list[float]:
        query = text.strip()
        if not query:
            raise ValueError("카페 벡터 검색어는 비어 있을 수 없습니다.")
        response = self._client.embeddings.create(
            model=OPENAI_EMBED_MODEL,
            input=query,
            dimensions=OPENAI_EMBED_DIM,
        )
        return response.data[0].embedding


def _default_connection_factory():
    import psycopg2

    return psycopg2.connect(**DB_CONFIG)


def normalize_cafe_language(language: str) -> Language:
    return "en" if str(language).strip().lower().startswith("en") else "ko"


def _tables(language: Language) -> dict[str, str]:
    suffix = normalize_cafe_language(language)
    return {
        "cafe": f"cafe_{suffix}",
        "cafe_embedding": f"cafe_embedding_{suffix}",
        "review_embedding": f"cafe_review_embedding_{suffix}",
    }


def _vector_literal(vector: Sequence[float]) -> str:
    if not vector:
        raise ValueError("검색 벡터는 비어 있을 수 없습니다.")
    return json.dumps([float(value) for value in vector], separators=(",", ":"))


def _positive_limit(value: int, *, name: str, maximum: int = 1000) -> int:
    if not 1 <= value <= maximum:
        raise ValueError(f"{name}은 1 이상 {maximum} 이하여야 합니다.")
    return value


class CafeRepository:
    """카페 검색에 필요한 DB 조회만 제공하며 점수 결합은 수행하지 않는다."""

    implemented = True

    def __init__(
        self,
        *,
        connection_factory: Callable[[], Any] | None = None,
        embedder: QueryEmbedder | None = None,
    ) -> None:
        self._connection_factory = connection_factory or _default_connection_factory
        self._embedder = embedder

    def embed_query(self, query: str) -> list[float]:
        if self._embedder is None:
            self._embedder = OpenAIQueryEmbedder()
        return self._embedder.embed(query)

    def search_cafe_vectors(
        self,
        vector: Sequence[float],
        *,
        language: str,
        limit: int = DEFAULT_CAFE_VECTOR_LIMIT,
    ) -> tuple[CafeVectorHit, ...]:
        """카페 설명 벡터의 전역 상위 후보를 순위와 유사도로 반환한다."""

        limit = _positive_limit(limit, name="카페 벡터 후보 수")
        tables = _tables(normalize_cafe_language(language))
        literal = _vector_literal(vector)
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT cafe_id, 1 - (embedding <=> %s::vector) AS similarity
                    FROM {tables['cafe_embedding']}
                    ORDER BY embedding <=> %s::vector, cafe_id
                    LIMIT %s
                    """,
                    (literal, literal, limit),
                )
                rows = cursor.fetchall()
        return tuple(
            CafeVectorHit(
                cafe_id=int(cafe_id),
                rank=rank,
                similarity=float(similarity),
            )
            for rank, (cafe_id, similarity) in enumerate(rows, start=1)
        )

    def search_review_vectors(
        self,
        vector: Sequence[float],
        *,
        language: str,
        pool: int = DEFAULT_REVIEW_VECTOR_POOL,
        per_cafe: int = DEFAULT_REVIEWS_PER_CAFE,
    ) -> dict[int, tuple[ReviewVectorHit, ...]]:
        """전역 리뷰 풀에서 카페별 상위 N개 검색 근거를 모은다."""

        pool = _positive_limit(pool, name="리뷰 벡터 검색 풀", maximum=10000)
        per_cafe = _positive_limit(
            per_cafe,
            name="카페별 리뷰 후보 수",
            maximum=20,
        )
        tables = _tables(normalize_cafe_language(language))
        literal = _vector_literal(vector)
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT
                        review_id,
                        cafe_id,
                        content,
                        1 - (embedding <=> %s::vector) AS similarity
                    FROM {tables['review_embedding']}
                    ORDER BY embedding <=> %s::vector, review_id
                    LIMIT %s
                    """,
                    (literal, literal, pool),
                )
                rows = cursor.fetchall()

        grouped: dict[int, list[ReviewVectorHit]] = {}
        for rank, (review_id, cafe_id, content, similarity) in enumerate(
            rows,
            start=1,
        ):
            cafe_hits = grouped.setdefault(int(cafe_id), [])
            if len(cafe_hits) >= per_cafe:
                continue
            normalized_content = str(content).strip()
            cafe_hits.append(
                ReviewVectorHit(
                    review_id=int(review_id),
                    cafe_id=int(cafe_id),
                    content=normalized_content,
                    rank=rank,
                    similarity=float(similarity),
                    word_count=len(normalized_content.split()),
                )
            )
        return {
            cafe_id: tuple(hits)
            for cafe_id, hits in grouped.items()
        }

    def fetch_cafes(
        self,
        cafe_ids: Sequence[int],
        *,
        language: str,
    ) -> dict[int, CafeRecord]:
        """벡터 검색으로 찾은 ID의 표시·필터링용 원본 정보를 조회한다."""

        normalized_ids = list(dict.fromkeys(int(cafe_id) for cafe_id in cafe_ids))
        if not normalized_ids:
            return {}
        tables = _tables(normalize_cafe_language(language))
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT
                        id, name, category, rating, review_count, address, phone,
                        postal_code, hours, description, image, link, lat, lng
                    FROM {tables['cafe']}
                    WHERE id = ANY(%s)
                    """,
                    (normalized_ids,),
                )
                rows = cursor.fetchall()
        return {
            int(row[0]): CafeRecord(
                id=int(row[0]),
                name=str(row[1]),
                category=row[2],
                rating=float(row[3]) if row[3] is not None else None,
                review_count=int(row[4]),
                address=str(row[5]),
                phone=row[6],
                postal_code=row[7],
                hours=row[8],
                description=row[9],
                image=row[10],
                link=row[11],
                lat=float(row[12]),
                lng=float(row[13]),
            )
            for row in rows
        }

    def fetch_supporting_reviews(
        self,
        vector: Sequence[float],
        cafe_ids: Sequence[int],
        *,
        language: str,
        per_cafe: int = DEFAULT_REVIEWS_PER_CAFE,
    ) -> dict[int, tuple[ReviewVectorHit, ...]]:
        """최종 후보 각각에 대해 질문과 가장 가까운 리뷰를 조회한다."""

        normalized_ids = list(dict.fromkeys(int(cafe_id) for cafe_id in cafe_ids))
        if not normalized_ids:
            return {}
        per_cafe = _positive_limit(
            per_cafe,
            name="카페별 근거 리뷰 수",
            maximum=20,
        )
        tables = _tables(normalize_cafe_language(language))
        literal = _vector_literal(vector)
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT review_id, cafe_id, content, similarity, cafe_rank
                    FROM (
                        SELECT
                            review_id,
                            cafe_id,
                            content,
                            1 - (embedding <=> %s::vector) AS similarity,
                            ROW_NUMBER() OVER (
                                PARTITION BY cafe_id
                                ORDER BY embedding <=> %s::vector, review_id
                            ) AS cafe_rank
                        FROM {tables['review_embedding']}
                        WHERE cafe_id = ANY(%s)
                    ) ranked
                    WHERE cafe_rank <= %s
                    ORDER BY cafe_id, cafe_rank
                    """,
                    (literal, literal, normalized_ids, per_cafe),
                )
                rows = cursor.fetchall()

        grouped: dict[int, list[ReviewVectorHit]] = {}
        for review_id, cafe_id, content, similarity, cafe_rank in rows:
            normalized_content = str(content).strip()
            grouped.setdefault(int(cafe_id), []).append(
                ReviewVectorHit(
                    review_id=int(review_id),
                    cafe_id=int(cafe_id),
                    content=normalized_content,
                    rank=int(cafe_rank),
                    similarity=float(similarity),
                    word_count=len(normalized_content.split()),
                )
            )
        return {
            cafe_id: tuple(hits)
            for cafe_id, hits in grouped.items()
        }

    def retrieve(
        self,
        query: str,
        *,
        language: str,
        cafe_limit: int = DEFAULT_CAFE_VECTOR_LIMIT,
        review_pool: int = DEFAULT_REVIEW_VECTOR_POOL,
        reviews_per_cafe: int = DEFAULT_REVIEWS_PER_CAFE,
    ) -> CafeRetrievalResult:
        """질문을 한 번 임베딩해 카페·리뷰 양쪽 검색 결과를 함께 반환한다."""

        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("카페 검색어는 비어 있을 수 없습니다.")
        normalized_language = normalize_cafe_language(language)
        vector = self.embed_query(normalized_query)
        cafe_hits = self.search_cafe_vectors(
            vector,
            language=normalized_language,
            limit=cafe_limit,
        )
        review_hits = self.search_review_vectors(
            vector,
            language=normalized_language,
            pool=review_pool,
            per_cafe=reviews_per_cafe,
        )
        candidate_ids = list(
            dict.fromkeys(
                [
                    *(hit.cafe_id for hit in cafe_hits),
                    *review_hits.keys(),
                ]
            )
        )
        return CafeRetrievalResult(
            query=normalized_query,
            language=normalized_language,
            cafe_hits=cafe_hits,
            review_hits_by_cafe=review_hits,
            cafes=self.fetch_cafes(candidate_ids, language=normalized_language),
        )


__all__ = [
    "CafeRecord",
    "CafeRepository",
    "CafeRetrievalResult",
    "CafeVectorHit",
    "OpenAIQueryEmbedder",
    "QueryEmbedder",
    "ReviewVectorHit",
    "normalize_cafe_language",
]
