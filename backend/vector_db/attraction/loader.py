from scripts.data_pipeline.attraction.models import RAGDocument
from vector_db.attraction.embedder import embed_texts
from vector_db.attraction.repository import AttractionVectorRepository


def load_documents(documents: list[RAGDocument], *, repository: AttractionVectorRepository | None = None, batch_size: int = 100) -> dict[str, int]:
    if batch_size <= 0:
        raise ValueError("batch_size는 양수여야 합니다.")
    repository = repository or AttractionVectorRepository()
    repository.initialize()
    existing = repository.existing_hashes([document.document_id for document in documents])
    pending = [document for document in documents if existing.get(document.document_id) != document.content_hash]
    for start in range(0, len(pending), batch_size):
        batch = pending[start:start + batch_size]
        repository.upsert(batch, embed_texts([document.content for document in batch]))
    return {"total": len(documents), "embedded": len(pending), "skipped": len(documents) - len(pending)}
