from openai import OpenAI

from core.config import OPENAI_API_KEY, OPENAI_EMBED_DIM, OPENAI_EMBED_MODEL


def embed_texts(texts: list[str], *, client: OpenAI | None = None) -> list[list[float]]:
    if not texts:
        return []
    if client is None:
        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY가 설정되지 않았습니다.")
        client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.embeddings.create(
        model=OPENAI_EMBED_MODEL,
        input=texts,
        dimensions=OPENAI_EMBED_DIM,
    )
    vectors = [row.embedding for row in response.data]
    if any(len(vector) != OPENAI_EMBED_DIM for vector in vectors):
        raise RuntimeError("Embedding 차원이 OPENAI_EMBED_DIM과 다릅니다.")
    return vectors
