"""
测试 VectorStore 的 Gemini embedding 与 Chroma 检索集成行为。
运行方式：
    cd backend
    uv run python -m unittest discover -s tests -p 'test_memory_vector_store.py'
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR / "apps"))

from memory.vector_store import VectorStore


class FakeGoogleGeminiEmbeddingFunction:
    """用固定关键词向量替代真实 Gemini API，避免测试依赖外网。"""

    instances = []
    calls = []

    def __init__(
        self,
        model_name: str = "gemini-embedding-001",
        task_type: str | None = None,
        api_key_env_var: str = "GEMINI_API_KEY",
        **kwargs,
    ):
        self.model_name = model_name
        self.task_type = task_type
        self.api_key_env_var = api_key_env_var
        self.kwargs = kwargs
        type(self).instances.append(self)

    def __call__(self, input):
        texts = list(input)
        type(self).calls.append((self.task_type, texts))

        embeddings = []
        for text in texts:
            lowered = text.lower()
            embeddings.append(
                [
                    1.0 if ("猫" in text or "cat" in lowered) else 0.0,
                    1.0 if ("蛋糕" in text or "cake" in lowered) else 0.0,
                    1.0 if ("设备" in text or "device" in lowered) else 0.0,
                ]
            )
        return embeddings

    @staticmethod
    def name():
        return "fake_google_gemini"

    def is_legacy(self):
        return False

    def default_space(self):
        return "cosine"

    def supported_spaces(self):
        return ["cosine", "l2", "ip"]

    def get_config(self):
        return {
            "model_name": self.model_name,
            "task_type": self.task_type,
            "api_key_env_var": self.api_key_env_var,
        }

    @staticmethod
    def build_from_config(config):
        return FakeGoogleGeminiEmbeddingFunction(**config)

    @classmethod
    def reset(cls):
        cls.instances = []
        cls.calls = []


class VectorStoreEmbeddingTests(unittest.TestCase):
    def setUp(self):
        VectorStore._instance = None
        FakeGoogleGeminiEmbeddingFunction.reset()
        self.tempdir = tempfile.TemporaryDirectory()
        self.base_env = patch.dict(
            os.environ,
            {
                "CHROMA_PERSIST_DIR": self.tempdir.name,
            },
            clear=False,
        )
        self.base_env.start()

    def tearDown(self):
        self.base_env.stop()
        self.tempdir.cleanup()
        VectorStore._instance = None
        FakeGoogleGeminiEmbeddingFunction.reset()

    def test_init_builds_separate_embedding_functions_for_documents_and_queries(self):
        with patch.dict(
            os.environ,
            {
                "EMBEDDING_API_KEY": "test-embedding-key",
                "CHROMA_EMBEDDING_MODEL": "gemini-embedding-001",
            },
            clear=False,
        ):
            with patch(
                "chromadb.utils.embedding_functions.GoogleGeminiEmbeddingFunction",
                FakeGoogleGeminiEmbeddingFunction,
            ):
                store = VectorStore()

        self.assertIs(store._embedding_fn, store._document_embedding_fn)
        self.assertEqual(len(FakeGoogleGeminiEmbeddingFunction.instances), 2)
        self.assertEqual(
            [inst.task_type for inst in FakeGoogleGeminiEmbeddingFunction.instances],
            ["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"],
        )
        self.assertTrue(
            all(inst.api_key_env_var == "EMBEDDING_API_KEY" for inst in FakeGoogleGeminiEmbeddingFunction.instances)
        )
        self.assertTrue(
            all(inst.model_name == "gemini-embedding-001" for inst in FakeGoogleGeminiEmbeddingFunction.instances)
        )

    def test_search_memory_uses_query_embeddings_and_returns_ranked_results(self):
        with patch.dict(
            os.environ,
            {
                "EMBEDDING_API_KEY": "test-embedding-key",
                "CHROMA_EMBEDDING_MODEL": "gemini-embedding-001",
            },
            clear=False,
        ):
            with patch(
                "chromadb.utils.embedding_functions.GoogleGeminiEmbeddingFunction",
                FakeGoogleGeminiEmbeddingFunction,
            ):
                store = VectorStore()

        current_time = {"value": 1000.0}

        def fake_time():
            current_time["value"] += 0.001
            return current_time["value"]

        with patch("memory.vector_store.time.time", side_effect=fake_time):
            store.add_memory("alice@example.com", "我家猫咪喜欢在窗边晒太阳", {"role": "user"})
            store.add_memory("alice@example.com", "今天学会了做巧克力蛋糕", {"role": "assistant"})

        memories = store.search_memory("alice@example.com", "猫咪最近在做什么", top_k=2)

        self.assertEqual(len(memories), 2)
        self.assertEqual(memories[0]["text"], "我家猫咪喜欢在窗边晒太阳")
        self.assertEqual(memories[0]["metadata"]["role"], "user")
        self.assertLessEqual(memories[0]["distance"], memories[1]["distance"])
        self.assertIn(
            ("RETRIEVAL_QUERY", ["猫咪最近在做什么"]),
            FakeGoogleGeminiEmbeddingFunction.calls,
        )

    def test_search_memory_returns_empty_list_for_empty_collection(self):
        with patch.dict(
            os.environ,
            {
                "EMBEDDING_API_KEY": "",
            },
            clear=False,
        ):
            store = VectorStore()

        self.assertEqual(store.search_memory("empty@example.com", "任意查询"), [])


if __name__ == "__main__":
    unittest.main()
