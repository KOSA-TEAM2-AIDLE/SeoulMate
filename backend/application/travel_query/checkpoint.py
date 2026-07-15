from langgraph.checkpoint.memory import InMemorySaver


def create_development_checkpointer() -> InMemorySaver:
    """로컬 개발·테스트용 checkpointer를 생성한다."""
    return InMemorySaver()
