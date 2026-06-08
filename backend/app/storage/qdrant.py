from qdrant_client import QdrantClient
from backend.app.config import settings
from backend.app.schemas.models import Passage

class QdrantManager:
    def __init__(self):
        self.client = QdrantClient(url=settings.QDRANT_URL)

    def init_collections(self):
        """Initializes collections in Qdrant."""
        raise NotImplementedError("init_collections not implemented")

    def upsert_passage(self, passage: Passage):
        """Upserts a passage into Qdrant."""
        raise NotImplementedError("upsert_passage not implemented")

    def search_passages(self, query_text: str, collection: str, filters: dict, limit: int, use_mmr: bool = False):
        """Searches for passages in Qdrant."""
        raise NotImplementedError("search_passages not implemented")
