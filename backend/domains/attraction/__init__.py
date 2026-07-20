__all__ = [
    "AttractionAgent",
    "AttractionAnswerGenerator",
    "AttractionRecommendationPipeline",
    "AttractionSearchService",
]


def __getattr__(name: str):
    if name == "AttractionAgent":
        from domains.attraction.agent import AttractionAgent
        return AttractionAgent
    if name == "AttractionAnswerGenerator":
        from domains.attraction.answer_generator import AttractionAnswerGenerator
        return AttractionAnswerGenerator
    if name == "AttractionRecommendationPipeline":
        from domains.attraction.recommendation_pipeline import AttractionRecommendationPipeline
        return AttractionRecommendationPipeline
    if name == "AttractionSearchService":
        from domains.attraction.search_service import AttractionSearchService
        return AttractionSearchService
    raise AttributeError(name)
