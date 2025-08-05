"""Main FastAPI application with modular architecture."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError

# Import configuration
from config.settings import settings

# Import services
from services.mlflow_service import mlflow_service

# Import middleware
from middleware.security import security_middleware

# Import routers
from routers.auth import router as auth_router
from routers.llm import router as llm_router
from routers.system import router as system_router

# Import exception handlers
from utils.exceptions import validation_exception_handler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage MLflow experiment tracking and security setup."""
    print("Starting LLMOps Secure API...")
    
    # Setup MLflow experiment
    await mlflow_service.setup_experiment()
    print("MLflow experiment setup completed")
    
    yield
    
    print("Shutting down LLMOps Secure API...")


# Create FastAPI application
app = FastAPI(
    title=settings.API_TITLE,
    description=settings.API_DESCRIPTION,
    version=settings.API_VERSION,
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_CREDENTIALS,
    allow_methods=settings.CORS_METHODS,
    allow_headers=settings.CORS_HEADERS,
)

# Add security middleware
app.middleware("http")(security_middleware)

# Add exception handlers
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# Include routers
app.include_router(auth_router)
app.include_router(llm_router)
app.include_router(system_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
