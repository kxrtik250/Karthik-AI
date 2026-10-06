from abc import ABC, abstractmethod
from typing import List
from fastembed import TextEmbedding

from app.config import settings


class BaseEmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""

    @abstractmethod
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embedding vectors for a list of texts."""
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Vector dimensionality."""
        pass


class FastEmbedProvider(BaseEmbeddingProvider):
    """Local, lightweight embedding provider using FastEmbed."""

    _instance: "FastEmbedProvider" = None
    _model: TextEmbedding = None

    def __init__(self, model_name: str = settings.embedding_model_name):
        self.model_name = model_name
        self._init_model()

    def _init_model(self):
        if FastEmbedProvider._model is None:
            FastEmbedProvider._model = TextEmbedding(model_name=self.model_name)
            # Run one probe embedding to verify dimension matches configuration
            test_vector = list(FastEmbedProvider._model.embed(["probe"]))[0]
            actual_dim = len(test_vector)
            if actual_dim != settings.embedding_dimension:
                raise ValueError(
                    f"Configured embedding dimension ({settings.embedding_dimension}) does not match "
                    f"model '{self.model_name}' output dimension ({actual_dim})!"
                )

    @property
    def dimension(self) -> int:
        return settings.embedding_dimension

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        embeddings_generator = FastEmbedProvider._model.embed(texts)
        return [vec.tolist() for vec in embeddings_generator]


def get_embedding_provider() -> BaseEmbeddingProvider:
    """Factory to retrieve configured embedding provider."""
    return FastEmbedProvider()


embedding_provider = get_embedding_provider()
