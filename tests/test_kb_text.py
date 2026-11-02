import unittest

from agent import rag


class FakeStore:
    def __init__(self, docs):
        self.docs = docs
        self.calls = 0

    def get(self):
        self.calls += 1
        return {"documents": list(self.docs), "ids": [str(i) for i in range(len(self.docs))]}


class KbTextTests(unittest.TestCase):
    def setUp(self):
        self._store = rag._vectorstore
        self._ttl = rag.KB_CACHE_TTL_SECONDS
        rag.invalidate_kb_cache()
        self.addCleanup(self.restore)

    def restore(self):
        rag._vectorstore = self._store
        rag.KB_CACHE_TTL_SECONDS = self._ttl
        rag.invalidate_kb_cache()

    def test_joins_documents(self):
        rag._vectorstore = FakeStore(["alpha", "  beta  ", "", None])
        self.assertEqual(rag.get_kb_text(), "alpha\n\nbeta")

    def test_cached_within_ttl_then_refreshed(self):
        store = FakeStore(["a"])
        rag._vectorstore = store
        rag.KB_CACHE_TTL_SECONDS = 1000
        rag.get_kb_text(); rag.get_kb_text()
        self.assertEqual(store.calls, 1)
        rag.KB_CACHE_TTL_SECONDS = -1  # expired
        rag.get_kb_text()
        self.assertEqual(store.calls, 2)

    def test_invalidate_forces_reload(self):
        store = FakeStore(["a"])
        rag._vectorstore = store
        rag.KB_CACHE_TTL_SECONDS = 1000
        rag.get_kb_text()
        store.docs = ["a", "b"]
        rag.invalidate_kb_cache()
        self.assertEqual(rag.get_kb_text(), "a\n\nb")

    def test_too_large_returns_none(self):
        rag._vectorstore = FakeStore(["x" * 100])
        self.assertIsNone(rag.get_kb_text(max_chars=50))
        self.assertIsNotNone(rag.get_kb_text(max_chars=500))
        self.assertIsNotNone(rag.get_kb_text(max_chars=0))  # 0 = unlimited

    def test_empty_or_missing_store_returns_none(self):
        rag._vectorstore = FakeStore([])
        self.assertIsNone(rag.get_kb_text())
        rag._vectorstore = None
        self.assertIsNone(rag.get_kb_text())

    def test_store_error_returns_stale_cache_or_none(self):
        class Boom:
            def get(self):
                raise RuntimeError("chroma down")
        rag._vectorstore = FakeStore(["keep"])
        rag.KB_CACHE_TTL_SECONDS = 1000
        self.assertEqual(rag.get_kb_text(), "keep")
        rag.KB_CACHE_TTL_SECONDS = -1
        rag._vectorstore = Boom()
        self.assertEqual(rag.get_kb_text(), "keep")  # stale beats nothing
        rag.invalidate_kb_cache()
        self.assertIsNone(rag.get_kb_text())


class SearchTests(unittest.TestCase):
    def test_no_rewrite_llm_call_in_search_tool(self):
        from agent import tools
        self.assertFalse(hasattr(tools, "rewrite_query"))

    def test_query_embeddings_client_reused(self):
        calls = []

        class Emb:
            def embed_query(self, q):
                calls.append(q)
                return [0.0]

        class Store:
            def similarity_search_by_vector(self, v, k=5):
                return []

        old = (rag._query_embeddings, rag._vectorstore, rag._bm25_retriever)
        rag._query_embeddings, rag._vectorstore, rag._bm25_retriever = Emb(), Store(), None
        try:
            rag.search_documents("q1"); rag.search_documents("q2")
        finally:
            rag._query_embeddings, rag._vectorstore, rag._bm25_retriever = old
        self.assertEqual(calls, ["q1", "q2"])


if __name__ == "__main__":
    unittest.main()
