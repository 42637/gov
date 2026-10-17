import numpy as np

try:
    from backend.app.rag.retriever import Retriever
except ModuleNotFoundError:
    from app.rag.retriever import Retriever


class FakeModel:
    def encode(self, values, **kwargs):
        return np.array([[1.0, 0.0]], dtype="float32")


class FakeIndex:
    d = 2

    def search(self, vector, count):
        return np.array([[0.9, 0.8]], dtype="float32"), np.array([[0, 1]])


class FakeStore:
    model = FakeModel()
    index = FakeIndex()
    chunks = [
        {"text": "A scheme record", "metadata": {"scheme_name": "A"}},
        {"text": "B scheme record", "metadata": {}},
    ]


def test_search_maps_faiss_results_to_real_chunks():
    results = Retriever(FakeStore()).search("farmer help", 2)
    assert [item.text for item in results] == ["A scheme record", "B scheme record"]
    assert results[0].metadata["scheme_name"] == "A"
