"""
Semantic Cache System using Qdrant Vector Database
Supports both exact and semantic caching for LLM responses
"""

import hashlib
import json
import uuid
import time
import httpx
from typing import List, Dict, Any, Optional, Tuple
from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    PointStruct, 
    SearchParams, 
    VectorParams, 
    Distance,
    CollectionInfo
)
from qdrant_client.http.exceptions import ResponseHandlingException
import logging

logger = logging.getLogger(__name__)

class SemanticCache:
    """
    Semantic Cache implementation using Qdrant vector database
    
    Architecture:
    - exact_cache: Collection for exact hash-based caching
    - semantic_cache: Collection for semantic similarity caching (API usage)
    - litellm_semantic_cache: Collection managed by LiteLLM (separate)
    """
    
    def __init__(
        self,
        qdrant_url: str = "http://localhost:6333",
        tei_url: str = "http://localhost:8080",
        exact_similarity_threshold: float = 1.0,  # Exact match
        semantic_similarity_threshold: float = 0.85,
        embedding_dimension: int = 384,  # all-MiniLM-L6-v2 dimension
        ttl_seconds: int = 1800
    ):
        self.qdrant_client = QdrantClient(url=qdrant_url)
        self.tei_url = tei_url
        self.exact_threshold = exact_similarity_threshold
        self.semantic_threshold = semantic_similarity_threshold
        self.embedding_dim = embedding_dimension
        self.ttl = ttl_seconds
        
        # Collection names
        self.exact_collection = "exact_cache"
        self.semantic_collection = "semantic_cache"
        
        # Initialize collections
        self._init_collections()
    
    def _init_collections(self):
        """Initialize Qdrant collections if they don't exist"""
        try:
            # Check and create exact cache collection
            if not self._collection_exists(self.exact_collection):
                self.qdrant_client.create_collection(
                    collection_name=self.exact_collection,
                    vectors_config=VectorParams(
                        size=self.embedding_dim,
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"Created collection: {self.exact_collection}")
            
            # Check and create semantic cache collection
            if not self._collection_exists(self.semantic_collection):
                self.qdrant_client.create_collection(
                    collection_name=self.semantic_collection,
                    vectors_config=VectorParams(
                        size=self.embedding_dim,
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"Created collection: {self.semantic_collection}")
                
        except Exception as e:
            logger.error(f"Failed to initialize collections: {e}")
            raise
    
    def _collection_exists(self, collection_name: str) -> bool:
        """Check if a collection exists"""
        try:
            collections = self.qdrant_client.get_collections()
            return any(col.name == collection_name for col in collections.collections)
        except Exception:
            return False
    
    async def _get_embedding(self, text: str) -> List[float]:
        """Get embedding from TEI server"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.tei_url}/embed",
                    json={"inputs": text},
                    timeout=30.0
                )
                response.raise_for_status()
                embeddings = response.json()
                return embeddings[0]  # TEI returns list of embeddings
        except Exception as e:
            logger.error(f"Failed to get embedding: {e}")
            raise
    
    def _generate_hash(self, prompt: str, model: str, **kwargs) -> str:
        """Generate MD5 hash for exact caching"""
        cache_key_data = {
            "prompt": prompt,
            "model": model,
            **kwargs
        }
        cache_key_str = json.dumps(cache_key_data, sort_keys=True)
        return hashlib.md5(cache_key_str.encode()).hexdigest()
    
    async def get_exact_cache(
        self, 
        prompt: str, 
        model: str, 
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached response using exact hash matching
        """
        try:
            cache_hash = self._generate_hash(prompt, model, **kwargs)
            embedding = await self._get_embedding(cache_hash)
            
            search_result = self.qdrant_client.search(
                collection_name=self.exact_collection,
                query_vector=embedding,
                limit=1,
                score_threshold=self.exact_threshold
            )
            
            if search_result and search_result[0].score >= self.exact_threshold:
                payload = search_result[0].payload
                
                # Check TTL
                if self._is_expired(payload.get("timestamp", 0)):
                    await self._delete_point(self.exact_collection, search_result[0].id)
                    return None
                
                logger.info(f"Exact cache hit for hash: {cache_hash}")
                return payload.get("response")
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting exact cache: {e}")
            return None
    
    async def set_exact_cache(
        self,
        prompt: str,
        model: str,
        response: Dict[str, Any],
        **kwargs
    ) -> bool:
        """
        Store response in exact cache
        """
        try:
            cache_hash = self._generate_hash(prompt, model, **kwargs)
            embedding = await self._get_embedding(cache_hash)
            
            point = PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload={
                    "hash": cache_hash,
                    "prompt": prompt,
                    "model": model,
                    "response": response,
                    "timestamp": time.time(),
                    "cache_type": "exact"
                }
            )
            
            self.qdrant_client.upload_points(
                collection_name=self.exact_collection,
                points=[point]
            )
            
            logger.info(f"Stored exact cache for hash: {cache_hash}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting exact cache: {e}")
            return False
    
    async def get_semantic_cache(
        self,
        prompt: str,
        model: str,
        **kwargs
    ) -> Optional[Tuple[Dict[str, Any], float]]:
        """
        Get cached response using semantic similarity
        Returns (response, similarity_score) or None
        """
        try:
            embedding = await self._get_embedding(prompt)
            
            search_result = self.qdrant_client.search(
                collection_name=self.semantic_collection,
                query_vector=embedding,
                limit=1,
                score_threshold=self.semantic_threshold
            )
            
            if search_result and search_result[0].score >= self.semantic_threshold:
                payload = search_result[0].payload
                
                # Check TTL
                if self._is_expired(payload.get("timestamp", 0)):
                    await self._delete_point(self.semantic_collection, search_result[0].id)
                    return None
                
                # Check model compatibility
                if payload.get("model") != model:
                    return None
                
                similarity_score = search_result[0].score
                logger.info(f"Semantic cache hit with similarity: {similarity_score}")
                return payload.get("response"), similarity_score
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting semantic cache: {e}")
            return None
    
    async def set_semantic_cache(
        self,
        prompt: str,
        model: str,
        response: Dict[str, Any],
        **kwargs
    ) -> bool:
        """
        Store response in semantic cache
        """
        try:
            embedding = await self._get_embedding(prompt)
            
            point = PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload={
                    "prompt": prompt,
                    "model": model,
                    "response": response,
                    "timestamp": time.time(),
                    "cache_type": "semantic",
                    "metadata": kwargs
                }
            )
            
            self.qdrant_client.upload_points(
                collection_name=self.semantic_collection,
                points=[point]
            )
            
            logger.info(f"Stored semantic cache for prompt: {prompt[:50]}...")
            return True
            
        except Exception as e:
            logger.error(f"Error setting semantic cache: {e}")
            return False
    
    def _is_expired(self, timestamp: float) -> bool:
        """Check if cache entry is expired"""
        return time.time() - timestamp > self.ttl
    
    async def _delete_point(self, collection_name: str, point_id: str):
        """Delete expired point"""
        try:
            self.qdrant_client.delete(
                collection_name=collection_name,
                points_selector=[point_id]
            )
        except Exception as e:
            logger.error(f"Error deleting point {point_id}: {e}")
    
    async def clear_cache(self, cache_type: str = "all") -> bool:
        """
        Clear cache collections
        cache_type: "exact", "semantic", or "all"
        """
        try:
            collections_to_clear = []
            
            if cache_type in ["exact", "all"]:
                collections_to_clear.append(self.exact_collection)
            
            if cache_type in ["semantic", "all"]:
                collections_to_clear.append(self.semantic_collection)
            
            for collection in collections_to_clear:
                if self._collection_exists(collection):
                    self.qdrant_client.delete_collection(collection)
                    logger.info(f"Cleared collection: {collection}")
            
            # Reinitialize collections
            self._init_collections()
            return True
            
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return False
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        try:
            stats = {}
            
            for collection_name in [self.exact_collection, self.semantic_collection]:
                if self._collection_exists(collection_name):
                    info = self.qdrant_client.get_collection(collection_name)
                    stats[collection_name] = {
                        "points_count": info.points_count,
                        "vectors_count": info.vectors_count,
                        "status": info.status
                    }
                else:
                    stats[collection_name] = {"status": "not_found"}
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {"error": str(e)}
