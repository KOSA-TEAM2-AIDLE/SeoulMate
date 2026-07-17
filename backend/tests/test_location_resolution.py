import unittest
from types import SimpleNamespace

from application.recommendation.location_resolution import (
    SearchLocationResolver,
)


class SearchLocationResolverTests(unittest.IsolatedAsyncioTestCase):
    async def test_named_place_uses_exact_unbiased_lookup_before_current_center(self):
        selected = SimpleNamespace(
            place_name="경복궁",
            latitude=37.5776,
            longitude=126.9769,
            source="kakao_local",
        )

        class Resolver:
            def __init__(self):
                self.calls = []

            async def resolve(self, **kwargs):
                self.calls.append(kwargs)
                return SimpleNamespace(
                    selected=selected,
                    candidates=[selected],
                    requires_disambiguation=False,
                )

        resolver = Resolver()
        result = await SearchLocationResolver(resolver).resolve(
            location="경복궁",
            latitude=37.5665,
            longitude=126.978,
            current_location_name="서울시청",
        )

        self.assertEqual(37.5776, result.latitude)
        self.assertEqual(126.9769, result.longitude)
        self.assertEqual(
            [{"query": "경복궁"}],
            resolver.calls,
        )


if __name__ == "__main__":
    unittest.main()
