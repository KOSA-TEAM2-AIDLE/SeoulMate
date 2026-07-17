"""관광 DSPy fallback 원인 코드.

이 코드는 사용자 응답에 노출하지 않고, 서버 로그에서
어느 단계가 문제였는지 구분하는 데만 사용한다.
"""

from enum import StrEnum


class AttractionFallbackReason(StrEnum):
    ARTIFACT_LOAD_FAILED = "artifact_load_failed"
    LM_CONFIGURATION_FAILED = "lm_configuration_failed"
    LM_CALL_FAILED = "lm_call_failed"
    LM_TIMEOUT = "lm_timeout"
    INVALID_SELECTED_IDS = "invalid_selected_ids"
    TOO_MANY_SELECTED_IDS = "too_many_selected_ids"
    DUPLICATE_SELECTED_IDS = "duplicate_selected_ids"
    UNKNOWN_SELECTED_ID = "unknown_selected_id"
    INVALID_REASONS_JSON = "invalid_reasons_json"
    REASONS_ID_MISMATCH = "reasons_id_mismatch"
    EMPTY_SELECTION_REASON = "empty_selection_reason"
    EMPTY_ANSWER = "empty_answer"
    ANSWER_CANDIDATE_MISMATCH = "answer_candidate_mismatch"
    UNSUPPORTED_QUIETNESS_CLAIM = "unsupported_quietness_claim"


class AttractionPredictionValidationError(ValueError):
    """DSPy 출력의 검증 실패를 기계 판독 가능한 코드로 전달한다."""

    def __init__(self, reason: AttractionFallbackReason) -> None:
        self.reason = reason
        super().__init__(reason.value)


__all__ = [
    "AttractionFallbackReason",
    "AttractionPredictionValidationError",
]
