from pilot import vector_store
from pilot.vector_store.base import VectorStoreBase

connector = {}


class VectorStoreConnector:
    """VectorStoreConnector, can connect different vector db provided load document api_v1 and similar search api_v1.
    1.load_document:knowledge document source into vector store.(Chroma, Milvus, Weaviate)
    2.similar_search: similarity search from vector_store
    how to use reference:https://db-gpt.readthedocs.io/en/latest/modules/vector.html
    how to integrate:https://db-gpt.readthedocs.io/en/latest/modules/vector/milvus/milvus.html

    """

    def __init__(self, vector_store_type, ctx: {}) -> None:
        """initialize vector store connector.
        Args:
            - vector_store_type: vector store type Milvus, Chroma, Weaviate
            - ctx: vector store config params.
        """
        self.ctx = ctx
        self._register()

        if self._match(vector_store_type):
            self.connector_class = connector.get(vector_store_type)
        else:
            raise Exception('Vector Type Not support. 0', vector_store_type)

        print(self.connector_class)
        self.client = self.connector_class(ctx)

    def load_document(self, docs):
        """load document in vector database."""
        return self.client.load_document(docs)

    def similar_search(self, doc: str, topk: int):
        """similar search in vector database.
        Args:
           - doc: query text
           - topk: topk
        """
        return self.client.similar_search(doc, topk)

    def vector_name_exists(self):
        """is vector store name exist."""
        return self.client.vector_name_exists()

    def delete_vector_name(self, vector_name):
        """vector store delete
        Args:
            - vector_name: vector store name
        """
        return self.client.delete_vector_name(vector_name)

    def delete_by_ids(self, ids):
        """vector store delete by ids.
        Args:
            - ids: vector ids
        """
        return self.client.delete_by_ids(ids=ids)

    def _match(self, vector_store_type) -> bool:
        return bool(connector.get(vector_store_type))

    def _register(self):
        for cls in vector_store.__all__:
            if issubclass(getattr(vector_store, cls), VectorStoreBase):
                _k, _v = cls, getattr(vector_store, cls)
                connector.update({_k: _v})
