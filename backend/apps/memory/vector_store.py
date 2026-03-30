"""
语义向量记忆引擎 (Memory A - Assistant)
基于 ChromaDB 实现对话和操作日志的向量化存储与语义检索。
"""
import os
import time
import chromadb
from utils.logger import logger


class VectorStore:
    """
    封装 ChromaDB 客户端，提供统一的记忆写入和检索接口。
    ChromaDB 使用内置的 all-MiniLM-L6-v2 模型进行 Embedding。
    """
    _instance = None

    @classmethod
    def get_instance(cls):
        """单例模式，确保全局共享一个 ChromaDB 客户端实例。"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        persist_dir = os.getenv("CHROMA_PERSIST_DIR", "./chroma_data")
        logger.info(f"[VectorStore] 初始化 ChromaDB，持久化路径: {persist_dir}")
        self._client = chromadb.PersistentClient(path=persist_dir)

    def _get_collection(self, user_id: str):
        """为每个用户创建独立的 collection，实现数据隔离。"""
        safe_name = user_id.replace("@", "_at_").replace(".", "_")[:60]
        collection_name = f"user_{safe_name}"
        return self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )

    def add_memory(self, user_id: str, text: str, metadata: dict = None):
        """
        将一条记忆写入向量库。
        
        Args:
            user_id: 用户唯一标识
            text: 对话内容或操作日志
            metadata: 附加元数据 (role, source, timestamp 等)
        """
        collection = self._get_collection(user_id)
        doc_id = f"{user_id}_{int(time.time() * 1000)}"
        
        meta = {
            "timestamp": int(time.time()),
            "user_id": user_id,
        }
        if metadata:
            meta.update(metadata)

        collection.add(
            documents=[text],
            metadatas=[meta],
            ids=[doc_id]
        )
        logger.debug(f"[VectorStore] 写入记忆: user={user_id}, len={len(text)}, id={doc_id}")

    def search_memory(self, user_id: str, query: str, top_k: int = 5) -> list[dict]:
        """
        基于语义相似度检索相关记忆。
        
        Args:
            user_id: 用户唯一标识
            query: 查询文本
            top_k: 返回最相关的 N 条结果
            
        Returns:
            相关记忆列表，每条包含 text, metadata, distance
        """
        collection = self._get_collection(user_id)
        
        # 如果 collection 为空，直接返回
        if collection.count() == 0:
            return []

        results = collection.query(
            query_texts=[query],
            n_results=min(top_k, collection.count())
        )

        memories = []
        if results and results.get("documents"):
            for i, doc in enumerate(results["documents"][0]):
                memories.append({
                    "text": doc,
                    "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
                    "distance": results["distances"][0][i] if results.get("distances") else 0.0,
                })

        logger.debug(f"[VectorStore] 检索记忆: user={user_id}, query='{query[:30]}', 命中={len(memories)}条")
        return memories

    def get_recent_memories(self, user_id: str, hours: int = 24, limit: int = 50) -> list[dict]:
        """
        获取指定时间窗口内的最近记忆（用于 Daily Review）。
        
        Args:
            user_id: 用户唯一标识
            hours: 时间窗口（小时）
            limit: 最大返回条数
        """
        collection = self._get_collection(user_id)
        
        if collection.count() == 0:
            return []

        cutoff = int(time.time()) - (hours * 3600)
        
        results = collection.get(
            where={"timestamp": {"$gte": cutoff}},
            limit=limit
        )

        memories = []
        if results and results.get("documents"):
            for i, doc in enumerate(results["documents"]):
                memories.append({
                    "text": doc,
                    "metadata": results["metadatas"][i] if results.get("metadatas") else {},
                })

        logger.debug(f"[VectorStore] 获取最近 {hours}h 记忆: user={user_id}, 数量={len(memories)}")
        return memories
