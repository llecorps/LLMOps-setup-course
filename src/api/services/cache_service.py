"""Redis cache service with MLflow integration."""

import json
import time
from datetime import datetime
import redis.asyncio as redis
from typing import Optional, Dict, Any, Tuple

from config.settings import settings
from services.mlflow_service import mlflow_service

class CacheService:
    """Redis cache service for LLM responses."""
    
    def __init__(self):
        """Initialize Redis connection."""
        self.redis = None
        self.metrics = {
            "hits": 0,
            "misses": 0,
            "errors": 0,
            "cost_saved": 0.0,
            "start_time": datetime.now()
        }
        
    async def initialize(self):
        """Initialize Redis connection."""
        try:
            self.redis = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                password=settings.REDIS_PASSWORD,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                health_check_interval=30
            )
            
            # Test connection
            await self.redis.ping()
            print("✅ Redis cache service initialized")
            
        except Exception as e:
            print(f"❌ Redis cache initialization failed: {e}")
            self.redis = None
    
    def _generate_cache_key(self, prompt: str, model: str, **params) -> str:
        """Generate a unique cache key."""
        # Normalize prompt
        normalized_prompt = prompt.lower().strip()
        
        # Hash the parameters that affect the output
        param_hash = hash(json.dumps({
            "temperature": params.get("temperature", 0.7),
            "max_tokens": params.get("max_tokens", 100),
            "system_prompt": params.get("system_prompt", "")
        }, sort_keys=True))
        
        # Final key structure
        return f"llmops:cache:v1:{model}:{hash(normalized_prompt)}:{param_hash}"
    
    async def get_cached_response(self, prompt: str, model: str, **params) -> Tuple[Optional[Dict[str, Any]], Optional[float]]:
        """Get cached response with timing."""
        if not self.redis:
            return None, None
            
        try:
            start_time = time.time()
            cache_key = self._generate_cache_key(prompt, model, **params)
            cached_data = await self.redis.get(cache_key)
            
            if cached_data:
                self.metrics["hits"] += 1
                response = json.loads(cached_data)
                
                # Update access time
                await self.redis.expire(cache_key, settings.CACHE_TTL)
                
                # Calculate cache latency
                cache_latency_ms = (time.time() - start_time) * 1000
                
                print(f"🎯 Cache HIT: {cache_key[:20]}... ({cache_latency_ms:.2f}ms)")
                return response, cache_latency_ms
            else:
                self.metrics["misses"] += 1
                print(f"❌ Cache MISS: {cache_key[:20]}...")
                return None, None
                
        except Exception as e:
            self.metrics["errors"] += 1
            print(f"Cache retrieval error: {e}")
            return None, None
    
    async def store_response(self, prompt: str, model: str, response: Dict[str, Any], **params):
        """Store response in cache."""
        if not self.redis:
            return False
            
        try:
            cache_key = self._generate_cache_key(prompt, model, **params)
            
            # Store with TTL
            ttl = self._calculate_adaptive_ttl(response)
            await self.redis.setex(
                cache_key,
                ttl,
                json.dumps(response)
            )
            
            print(f"💾 Cache STORED: {cache_key[:20]}... TTL={ttl}s")
            return True
            
        except Exception as e:
            self.metrics["errors"] += 1
            print(f"Cache storage error: {e}")
            return False
    
    def _calculate_adaptive_ttl(self, response: Dict[str, Any]) -> int:
        """Calculate adaptive TTL based on response characteristics."""
        base_ttl = settings.CACHE_TTL
        
        # Adjust TTL based on response value
        cost = response.get("cost", 0)
        tokens = response.get("total_tokens", 0)
        
        if cost > 0.01:  # Expensive responses
            return base_ttl * 3
        elif cost > 0.005:  # Medium cost
            return base_ttl * 2
        elif tokens > 1000:  # Long responses
            return base_ttl * 2
        
        return base_ttl

# Global instance
cache_service = CacheService()
