"""DSPy modules for the two-stage attraction recommendation flow."""

import dspy

from domains.attraction.dspy.signatures import (
    TourismAnswerSignature,
    TourismReasonSignature,
    TourismSelectionSignature,
)


class TourismSelectionProgram(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.generate = dspy.Predict(TourismSelectionSignature)

    def forward(self, **inputs):
        return self.generate(**inputs)


class TourismAnswerProgram(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.generate = dspy.Predict(TourismAnswerSignature)

    def forward(self, **inputs):
        return self.generate(**inputs)


class TourismReasonProgram(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.generate = dspy.Predict(TourismReasonSignature)

    def forward(self, **inputs):
        return self.generate(**inputs)


__all__ = ["TourismAnswerProgram", "TourismReasonProgram", "TourismSelectionProgram"]
