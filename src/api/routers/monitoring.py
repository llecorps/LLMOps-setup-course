"""Monitoring endpoints for LLMOps system."""

import time
from datetime import datetime, timedelta
from typing import Dict, Any, List
import json
import os
import sqlite3
from fastapi import APIRouter, HTTPException, Depends
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response
import requests
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/monitoring", tags=["monitoring"])

# Import shared metrics from middleware
from middleware.metrics import REQUEST_COUNT, REQUEST_DURATION, REQUEST_SIZE, RESPONSE_SIZE

# Additional monitoring-specific metrics
LLM_COST = Gauge('llmops_llm_cost_total', 'Total LLM cost in USD')
LLM_TOKENS = Counter('llmops_llm_tokens_total', 'Total tokens used', ['type', 'model'])
CACHE_HITS = Counter('llmops_cache_hits_total', 'Cache hits', ['type'])

@router.get("/metrics")
async def get_prometheus_metrics():
    """Expose Prometheus metrics endpoint with enhanced error handling."""
    try:
        # Update metrics from MLflow asynchronously (non-blocking)
        try:
            await update_metrics_from_mlflow()
        except Exception as mlflow_error:
            logger.warning(f"MLflow metrics update failed (continuing anyway): {mlflow_error}")
        
        # Generate Prometheus format with fallback
        metrics_content = generate_latest()
        if not metrics_content:
            logger.warning("Generated empty metrics content")
            metrics_content = "# No metrics available\n"
        
        return Response(metrics_content, media_type=CONTENT_TYPE_LATEST)
    except Exception as e:
        logger.error(f"Critical error generating metrics: {e}", exc_info=True)
        # Return a basic error metric instead of failing completely
        error_metric = f"# Error generating metrics\nllmops_metrics_error{{error="{type(e).__name__}"}} 1\n"
        return Response(error_metric, media_type=CONTENT_TYPE_LATEST)

@router.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    services_status = {}
    
    # Check LiteLLM
    try:
        response = requests.get("http://litellm:4000/health", timeout=5)
        services_status["litellm"] = "healthy" if response.status_code == 200 else "unhealthy"
    except:
        services_status["litellm"] = "unhealthy"
    
    # Check MLflow
    try:
        response = requests.get("http://mlflow:5000/health", timeout=5)
        services_status["mlflow"] = "healthy" if response.status_code == 200 else "unhealthy"
    except:
        services_status["mlflow"] = "unhealthy"
    
    # Check Qdrant
    try:
        response = requests.get("http://qdrant:6333/", timeout=5)
        services_status["qdrant"] = "healthy" if response.status_code == 200 else "unhealthy"
    except:
        services_status["qdrant"] = "unhealthy"
    
    # Check TEI
    try:
        response = requests.get("http://tei-embeddings:80/health", timeout=5)
        services_status["tei"] = "healthy" if response.status_code == 200 else "unhealthy"
    except:
        services_status["tei"] = "unhealthy"
    
    overall_health = "healthy" if all(status == "healthy" for status in services_status.values()) else "degraded"
    
    return {
        "status": overall_health,
        "timestamp": datetime.now().isoformat(),
        "services": services_status
    }

@router.get("/stats")
async def get_system_stats():
    """Get comprehensive system statistics."""
    try:
        stats = {
            "timestamp": datetime.now().isoformat(),
            "mlflow_stats": await get_mlflow_stats(),
            "cache_stats": await get_cache_stats(),
            "cost_summary": await get_cost_summary()
        }
        return stats
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving stats")

async def update_metrics_from_mlflow():
    """Update Prometheus metrics from MLflow data."""
    try:
        # Get MLflow tracking URI
        mlflow_uri = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
        
        # Query MLflow for recent runs
        response = requests.get(f"{mlflow_uri}/api/2.0/mlflow/experiments/search", timeout=10)
        if response.status_code == 200:
            experiments = response.json().get("experiments", [])
            
            total_cost = 0
            total_tokens = 0
            
            for experiment in experiments:
                exp_id = experiment.get("experiment_id")
                if exp_id:
                    # Get runs for this experiment
                    runs_response = requests.get(
                        f"{mlflow_uri}/api/2.0/mlflow/runs/search",
                        json={"experiment_ids": [exp_id], "max_results": 100},
                        timeout=10
                    )
                    
                    if runs_response.status_code == 200:
                        runs = runs_response.json().get("runs", [])
                        for run in runs:
                            metrics = run.get("data", {}).get("metrics", {})
                            
                            # Extract cost and token metrics
                            if "cost" in metrics:
                                total_cost += float(metrics["cost"])
                            if "total_tokens" in metrics:
                                total_tokens += int(metrics["total_tokens"])
            
            # Update Prometheus metrics
            LLM_COST.set(total_cost)
            LLM_TOKENS._value._value = total_tokens
            
    except Exception as e:
        logger.error(f"Error updating metrics from MLflow: {e}")

async def get_mlflow_stats():
    """Get statistics from MLflow."""
    try:
        mlflow_uri = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
        
        # Get experiments
        response = requests.get(f"{mlflow_uri}/api/2.0/mlflow/experiments/search", timeout=10)
        if response.status_code == 200:
            experiments = response.json().get("experiments", [])
            
            stats = {
                "total_experiments": len(experiments),
                "recent_runs": 0,
                "total_cost": 0.0,
                "total_tokens": 0
            }
            
            # Get recent runs (last 24h)
            since_timestamp = int((datetime.now() - timedelta(hours=24)).timestamp() * 1000)
            
            for experiment in experiments:
                exp_id = experiment.get("experiment_id")
                if exp_id:
                    runs_response = requests.get(
                        f"{mlflow_uri}/api/2.0/mlflow/runs/search",
                        json={
                            "experiment_ids": [exp_id],
                            "filter": f"attribute.start_time >= {since_timestamp}",
                            "max_results": 1000
                        },
                        timeout=10
                    )
                    
                    if runs_response.status_code == 200:
                        runs = runs_response.json().get("runs", [])
                        stats["recent_runs"] += len(runs)
                        
                        for run in runs:
                            metrics = run.get("data", {}).get("metrics", {})
                            if "cost" in metrics:
                                stats["total_cost"] += float(metrics["cost"])
                            if "total_tokens" in metrics:
                                stats["total_tokens"] += int(metrics["total_tokens"])
            
            return stats
        
    except Exception as e:
        logger.error(f"Error getting MLflow stats: {e}")
        return {"error": str(e)}

async def get_cache_stats():
    """Get cache statistics from Qdrant."""
    try:
        # Get Qdrant collection info
        response = requests.get("http://qdrant:6333/collections/litellm_semantic_cache", timeout=5)
        if response.status_code == 200:
            collection_info = response.json()
            return {
                "vectors_count": collection_info.get("result", {}).get("vectors_count", 0),
                "indexed_vectors_count": collection_info.get("result", {}).get("indexed_vectors_count", 0),
                "points_count": collection_info.get("result", {}).get("points_count", 0)
            }
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        return {"error": str(e)}

async def get_cost_summary():
    """Get cost summary for the last 24 hours."""
    try:
        mlflow_uri = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
        since_timestamp = int((datetime.now() - timedelta(hours=24)).timestamp() * 1000)
        
        response = requests.get(f"{mlflow_uri}/api/2.0/mlflow/experiments/search", timeout=10)
        if response.status_code == 200:
            experiments = response.json().get("experiments", [])
            
            cost_by_model = {}
            total_cost = 0.0
            total_requests = 0
            
            for experiment in experiments:
                exp_id = experiment.get("experiment_id")
                if exp_id:
                    runs_response = requests.get(
                        f"{mlflow_uri}/api/2.0/mlflow/runs/search",
                        json={
                            "experiment_ids": [exp_id],
                            "filter": f"attribute.start_time >= {since_timestamp}",
                            "max_results": 1000
                        },
                        timeout=10
                    )
                    
                    if runs_response.status_code == 200:
                        runs = runs_response.json().get("runs", [])
                        total_requests += len(runs)
                        
                        for run in runs:
                            metrics = run.get("data", {}).get("metrics", {})
                            params = run.get("data", {}).get("params", {})
                            
                            model = params.get("model", "unknown")
                            cost = float(metrics.get("cost", 0))
                            
                            if model not in cost_by_model:
                                cost_by_model[model] = 0.0
                            cost_by_model[model] += cost
                            total_cost += cost
            
            return {
                "total_cost_24h": round(total_cost, 4),
                "total_requests_24h": total_requests,
                "average_cost_per_request": round(total_cost / max(total_requests, 1), 4),
                "cost_by_model": cost_by_model
            }
    
    except Exception as e:
        logger.error(f"Error getting cost summary: {e}")
        return {"error": str(e)}
