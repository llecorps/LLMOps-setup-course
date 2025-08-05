"""LLM operations router."""

import time
import requests
import openai
import litellm
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status, Depends
from litellm import completion_cost

from models.llm_models import SecurePromptRequest, SecurePromptResponse, ModelsResponse
from services.auth_service import verify_token
from services.mlflow_service import mlflow_service
from services.security_service import security_metrics
from services.cache_service import cache_service
from config.settings import settings

router = APIRouter(prefix="/llm", tags=["llm"])

# Configure OpenAI client to use LiteLLM proxy
client = openai.OpenAI(
    base_url=f"{settings.LITELLM_URL}/v1",
    api_key="dummy-key"  # LiteLLM handles the real API keys
)


@router.post("/generate", response_model=SecurePromptResponse)
async def generate_secure_prompt(
    request: SecurePromptRequest, 
    current_user: Dict[str, Any] = Depends(verify_token)
):
    """Generate text using LLM with built-in security guardrails and MLflow tracing."""
    start_time = time.time()
    
    try:
        # Prepare messages for the LLM
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})
        
        # Prepare request parameters
        litellm_params = {
            "model": request.model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens
        }
        
        # Add structured output if specified
        if request.response_format:
            litellm_params["response_format"] = request.response_format
        
        # Note: guardrails are handled by our security validation, not passed to LiteLLM
        # The security validation happens in the Pydantic models and middleware
        
        print(f"DEBUG: Making LiteLLM request with model: {request.model}")
        print(f"DEBUG: Messages: {messages}")
        
        # Check cache first
        cache_key_params = {
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "system_prompt": request.system_prompt
        }
        cached_response, cache_latency = await cache_service.get_cached_response(
            prompt=request.prompt,
            model=request.model,
            **cache_key_params
        )
        
        if cached_response:
            # Use cached response
            response_time = cache_latency / 1000  # Convert to seconds
            
            # Trace cache hit in MLflow
            try:
                mlflow_service.trace_llm_request(
                    prompt=request.prompt,
                    model=request.model,
                    response=cached_response["response"],
                    tokens={
                        "prompt_tokens": cached_response["prompt_tokens"],
                        "completion_tokens": cached_response["completion_tokens"],
                        "total_tokens": cached_response["total_tokens"]
                    },
                    cost=cached_response["cost"],
                    start_time=start_time,
                    cache_hit=True,
                    cache_latency_ms=cache_latency
                )
            except Exception as trace_error:
                print(f"Warning: Could not trace cached response: {trace_error}")
            
            return SecurePromptResponse(
                response=cached_response["response"],
                model=request.model,
                prompt_tokens=cached_response["prompt_tokens"],
                completion_tokens=cached_response["completion_tokens"],
                total_tokens=cached_response["total_tokens"],
                cost=cached_response["cost"],
                security_status="protected",
                guardrails_triggered=cached_response.get("guardrails_triggered", [])
            )
        
        # No cache hit, make the LLM request via LiteLLM proxy
        response = client.chat.completions.create(**litellm_params)
        
        # Calculate metrics
        end_time = time.time()
        response_time = end_time - start_time
        
        # Extract response data
        response_text = response.choices[0].message.content
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens
        total_tokens = response.usage.total_tokens
        
        # Store response in cache
        response_data = {
            "response": response_text,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cost": None,  # Will be updated below
            "guardrails_triggered": []
        }
        
        # Calculate cost
        try:
            cost = completion_cost(
                completion_response=response,
                model=request.model
            )
            response_data["cost"] = cost
        except Exception as e:
            print(f"Warning: Could not calculate cost: {e}")
            cost = 0.0
            response_data["cost"] = cost
            
        # Store in cache now that we have the cost
        try:
            await cache_service.store_response(
                prompt=request.prompt,
                model=request.model,
                response=response_data,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                system_prompt=request.system_prompt
            )
        except Exception as cache_error:
            print(f"Warning: Could not cache response: {cache_error}")
        
        # Trace in MLflow
        try:
            mlflow_service.trace_llm_request(
                prompt=request.prompt,
                model=request.model,
                response=response_text,
                tokens={
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens
                },
                cost=cost,
                start_time=start_time
            )
        except Exception as trace_error:
            print(f"Warning: Could not trace LLM request: {trace_error}")
        
        # Check for triggered guardrails
        guardrails_triggered = []
        if hasattr(response, 'guardrails_triggered'):
            guardrails_triggered = response.guardrails_triggered
        
        return SecurePromptResponse(
            response=response_text,
            model=request.model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost=cost,
            security_status="protected",
            guardrails_triggered=guardrails_triggered
        )
        
    except openai.RateLimitError as e:
        security_metrics["blocked_requests"] += 1
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later."
        )
    except openai.BadRequestError as e:
        security_metrics["blocked_requests"] += 1
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid request: {str(e)}"
        )
    except Exception as e:
        security_metrics["blocked_requests"] += 1
        print(f"Error generating response: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate response. Please try again."
        )


@router.get("/models", response_model=ModelsResponse)
async def list_models():
    """List all available models from the LiteLLM router."""
    try:
        response = requests.get(f"{settings.LITELLM_URL}/models")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Error fetching models: {e}")


@router.get("/health")
async def llm_health():
    """LLM service health check."""
    return {"status": "healthy", "service": "llm"}