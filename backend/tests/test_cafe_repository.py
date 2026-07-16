import unittest

from domains.cafe.repository import CafeRepository


class FakeEmbedder:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def embed(self, text: str) -> list[float]:
        self.queries.append(text)
        return [0.1, 0.2]


class FakeCursor:
    def __init__(self, responses):
        self.responses = responses
        self.executions: list[tuple[str, tuple]] = []
        self._rows = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, sql, params):
        self.executions.append((sql, params))
        self._rows = self.responses[len(self.executions) - 1]

    def fetchall(self):
        return self._rows


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def cursor(self):
        return self._cursor


class FakeConnectionFactory:
    def __init__(self, responses):
        self.cursor = FakeCursor(responses)

    def __call__(self):
        return FakeConnection(self.cursor)


class CafeRepositoryTests(unittest.TestCase):
    def test_retrieve_embeds_once_and_queries_korean_tables(self):
        factory = FakeConnectionFactory([
            [(10, 0.91), (20, 0.82)],
            [
                (101, 20, "조용하고 작업하기 좋아요", 0.95),
                (102, 20, "콘센트가 많아요", 0.90),
                (103, 20, "커피가 맛있어요", 0.85),
                (104, 20, "네 번째 리뷰", 0.80),
                (105, 30, "디저트가 좋아요", 0.75),
            ],
            [
                (
                    10, "카페 A", "카페", 4.5, 12, "서울 A", None, None,
                    "09:00-22:00", "설명 A", "a.jpg", "https://a", 37.5, 127.0,
                ),
                (
                    20, "카페 B", "베이커리", 4.8, 30, "서울 B", "02", "01234",
                    None, None, "b.jpg", "https://b", 37.6, 127.1,
                ),
                (
                    30, "카페 C", None, None, 1, "서울 C", None, None,
                    None, None, None, None, 37.7, 127.2,
                ),
            ],
        ])
        embedder = FakeEmbedder()
        repository = CafeRepository(
            connection_factory=factory,
            embedder=embedder,
        )

        result = repository.retrieve(
            " 조용한 작업 카페 ",
            language="ko-KR",
            cafe_limit=2,
            review_pool=5,
            reviews_per_cafe=3,
        )

        self.assertEqual(["조용한 작업 카페"], embedder.queries)
        self.assertEqual("ko", result.language)
        self.assertEqual((0.1, 0.2), result.query_vector)
        self.assertEqual([10, 20], [hit.cafe_id for hit in result.cafe_hits])
        self.assertEqual([1, 2], [hit.rank for hit in result.cafe_hits])
        self.assertEqual(3, len(result.review_hits_by_cafe[20]))
        self.assertEqual([10, 20, 30], list(result.cafes))
        self.assertEqual("카페 B", result.cafes[20].name)

        sql_statements = [sql for sql, _ in factory.cursor.executions]
        self.assertIn("cafe_embedding_ko", sql_statements[0])
        self.assertIn("cafe_review_embedding_ko", sql_statements[1])
        self.assertIn("FROM cafe_ko", sql_statements[2])
        self.assertEqual(("[0.1,0.2]", "[0.1,0.2]", 2), factory.cursor.executions[0][1])

    def test_english_supporting_reviews_use_partitioned_query(self):
        factory = FakeConnectionFactory([
            [
                (1, 10, "quiet seats", 0.92, 1),
                (2, 10, "many outlets", 0.88, 2),
                (3, 20, "great dessert", 0.80, 1),
            ]
        ])
        repository = CafeRepository(connection_factory=factory)

        reviews = repository.fetch_supporting_reviews(
            [0.3, 0.4],
            [10, 20],
            language="en-US",
            per_cafe=2,
        )

        self.assertEqual([1, 2], [hit.rank for hit in reviews[10]])
        self.assertEqual("great dessert", reviews[20][0].content)
        sql, params = factory.cursor.executions[0]
        self.assertIn("cafe_review_embedding_en", sql)
        self.assertIn("PARTITION BY cafe_id", sql)
        self.assertEqual(([10, 20], 2), params[2:])

    def test_empty_ids_skip_database_and_invalid_limits_fail(self):
        factory = FakeConnectionFactory([])
        repository = CafeRepository(connection_factory=factory)

        self.assertEqual({}, repository.fetch_cafes([], language="ko"))
        self.assertEqual(
            {},
            repository.fetch_supporting_reviews(
                [0.1],
                [],
                language="ko",
            ),
        )
        self.assertEqual([], factory.cursor.executions)
        with self.assertRaisesRegex(ValueError, "후보 수"):
            repository.search_cafe_vectors([0.1], language="ko", limit=0)
        with self.assertRaisesRegex(ValueError, "검색 벡터"):
            repository.search_cafe_vectors([], language="ko")


if __name__ == "__main__":
    unittest.main()
