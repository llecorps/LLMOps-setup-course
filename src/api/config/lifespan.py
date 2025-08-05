"""Application lifespan management."""

from contextlib import asynccontextmanager
from fastapi import FastAPI

from services.mlflow_service import mlflow_service
from services.cache_service import cache_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage MLflow experiment tracking and security setup."""
    print("Starting LLMOps Secure API...")
    
    # Setup MLflow experiment
    await mlflow_service.setup_experiment()
    print("MLflow experiment setup completed")
    
    # Setup Redis cache
    await cache_service.initialize()
    print("Redis cache service initialized")
    
    yield
    
    print("Shutting down LLMOps Secure API...")