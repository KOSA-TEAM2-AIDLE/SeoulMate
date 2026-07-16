__all__ = ["AttractionAgent", "AttractionSearchService"]


def __getattr__(name: str):
    if name == "AttractionAgent":
        from domains.attraction.agent import AttractionAgent
        return AttractionAgent
    if name == "AttractionSearchService":
        from domains.attraction.search_service import AttractionSearchService
        return AttractionSearchService
    raise AttributeError(name)
