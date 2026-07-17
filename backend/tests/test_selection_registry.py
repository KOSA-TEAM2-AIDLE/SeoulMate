import unittest

from application.recommendation.selection_interface import (
    DomainCandidateSelectionService,
)
from application.recommendation.selection_models import (
    CandidateSelectionResult,
)
from application.recommendation.selection_registry import (
    DomainSelectionRegistry,
    build_default_selection_registry,
)
from domains.attraction.selection_service import AttractionSelectionService


class StubSelectionService:
    def __init__(self, domain: str) -> None:
        self.domain = domain

    async def select(self, request, candidates) -> CandidateSelectionResult:
        return CandidateSelectionResult(answer="stub", selections=[])


class DomainSelectionRegistryTests(unittest.TestCase):
    def test_default_registry_registers_only_attraction_dspy_selector(self):
        registry = build_default_selection_registry()

        attraction = registry.get_optional("attraction")
        self.assertIsInstance(attraction, AttractionSelectionService)
        self.assertIsInstance(attraction, DomainCandidateSelectionService)
        self.assertIsNone(registry.get_optional("restaurant"))
        self.assertIsNone(registry.get_optional("cafe"))
        self.assertIsNone(registry.get_optional("accommodation"))
        self.assertEqual(registry.registered_domains(), ("attraction",))

    def test_domain_is_normalized_and_duplicate_registration_is_rejected(self):
        registry = DomainSelectionRegistry()
        service = StubSelectionService(" Attraction ")

        registry.register(service)

        self.assertIs(registry.get_optional("ATTRACTION"), service)
        with self.assertRaisesRegex(ValueError, "이미 등록"):
            registry.register(StubSelectionService("attraction"))

    def test_replace_is_explicit_and_blank_domain_is_rejected(self):
        registry = DomainSelectionRegistry()
        first = StubSelectionService("attraction")
        replacement = StubSelectionService("attraction")
        registry.register(first)

        registry.register(replacement, replace=True)

        self.assertIs(registry.get_optional("attraction"), replacement)
        with self.assertRaisesRegex(ValueError, "비어"):
            registry.register(StubSelectionService("  "))


if __name__ == "__main__":
    unittest.main()
