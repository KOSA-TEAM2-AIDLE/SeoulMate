import unittest

from core.language import detect_input_language
from schemas.chat import ChatRequest


class LanguageDetectionTests(unittest.TestCase):
    def test_english_input_overrides_korean_fallback(self):
        self.assertEqual(
            "en",
            detect_input_language("Recommend quiet cafes near me", "ko"),
        )

    def test_korean_input_overrides_english_fallback(self):
        self.assertEqual(
            "ko",
            detect_input_language("여기 주변 카페 추천해줘", "en"),
        )

    def test_short_ambiguous_input_uses_fallback(self):
        self.assertEqual("en", detect_input_language("OK", "en"))
        self.assertEqual("ko", detect_input_language("OK", "ko"))

    def test_chat_request_normalizes_language_from_message(self):
        request = ChatRequest(
            message="Please recommend cafes near me",
            lang="ko",
        )

        self.assertEqual("en", request.lang)


if __name__ == "__main__":
    unittest.main()
