"""MLflow service for experiment tracking and security monitoring."""

import asyncio
import mlflow
import os
import time
from typing import Optional
from datetime import datetime
from mlflow.entities.span import SpanType
from mlflow.entities.span_event import SpanEvent

from config.settings import settings


class MLflowService:
    """MLflow service for managing experiments and tracking."""
    
    def __init__(self):
        self.experiment_id: Optional[str] = None
        self.experiment_name: str = "llmops-security"
        self.tracking_uri = settings.MLFLOW_TRACKING_URI
    
    async def setup_experiment(self):
        """Setup MLflow experiment."""
        # Initialize MLflow tracking
        mlflow.set_tracking_uri(self.tracking_uri)
        
        # Set the security experiment for API calls (should already exist from init)
        try:
            mlflow.set_experiment(self.experiment_name)
            print(f"✅ Using MLflow experiment: {self.experiment_name}")
        except Exception as e:
            print(f"⚠️ Warning: Could not set MLflow experiment: {e}")
            # Fallback - try to create it
            try:
                mlflow.create_experiment(self.experiment_name)
                mlflow.set_experiment(self.experiment_name)
                print(f"🆕 Created and set MLflow experiment: {self.experiment_name}")
            except Exception as create_error:
                print(f"❌ Failed to create experiment: {create_error}")
    
    async def log_metrics(self, metrics: dict):
        """Log metrics to MLflow."""
        print(f"Logging metrics: {metrics}")
        # This would contain actual MLflow logging code
        pass
    
    async def log_parameters(self, parameters: dict):
        """Log parameters to MLflow."""
        print(f"Logging parameters: {parameters}")
        # This would contain actual MLflow logging code
        pass

    @mlflow.trace(name="security_incident", span_type=SpanType.LLM)
    def trace_security_incident(self, incident_type: str, request_data: dict, pattern: str = None, error_message: str = None):
        """Trace security incidents in MLflow for blocked attacks."""
        try:
            # Get current span for this security incident
            current_span = mlflow.get_current_active_span()
            
            if current_span:
                # Set inputs (the malicious request)
                current_span.set_inputs({
                    "request_data": request_data,
                    "incident_type": incident_type,
                    "detected_pattern": pattern,
                    "blocked": True
                })
                
                # Set outputs (the security response)
                current_span.set_outputs({
                    "action_taken": "blocked",
                    "error_message": error_message,
                    "security_status": "threat_detected",
                    "blocked_at": "input_validation"
                })
                
                # Set security-specific attributes
                current_span.set_attributes({
                    "security.incident_type": incident_type,
                    "security.threat_level": "high",
                    "security.blocked": True,
                    "security.pattern_matched": pattern or "unknown",
                    "llm.request.blocked": True,
                    "mlflow.spanType": "LLM"  # Mark as LLM span for proper UI display
                })
                
                # Add security event
                current_span.add_event(SpanEvent("Security threat detected and blocked", attributes={
                    "incident_type": incident_type,
                    "pattern": pattern,
                    "timestamp": datetime.now().isoformat()
                }))
            
            print(f"🚨 Security incident traced in MLflow: {incident_type}")
            return True
            
        except Exception as e:
            print(f"⚠️ Failed to trace security incident: {e}")
            return False

    @mlflow.trace(name="llm_generation", span_type=SpanType.LLM)
    def trace_llm_request(self, prompt: str, model: str, response: str, tokens: dict, cost: float, start_time: float, cache_hit: bool = False, cache_latency_ms: Optional[float] = None):
        """Trace LLM generation requests with improved timing and cache awareness."""
        try:
            current_span = mlflow.get_current_active_span()
            current_time = time.time()
            duration_ms = (current_time - start_time) * 1000
            
            if current_span:
                # Set parent span inputs
                current_span.set_inputs({
                    "messages": [{
                        "role": "user",
                        "content": prompt
                    }],
                    "model": model,
                    "temperature": 0.7,
                    "cache_enabled": True
                })
                
                # Set parent span outputs
                current_span.set_outputs({
                    "choices": [{
                        "message": {
                            "role": "assistant",
                            "content": response
                        }
                    }],
                    "usage": tokens,
                    "cost": cost,
                    "latency_ms": duration_ms,
                    "cache_hit": cache_hit,
                    "cache_latency_ms": cache_latency_ms if cache_hit else None
                })
                
                # Set parent span attributes
                current_span.set_attributes({
                    "llm.model": model,
                    "llm.prompt_tokens": tokens.get("prompt_tokens", 0),
                    "llm.completion_tokens": tokens.get("completion_tokens", 0),
                    "llm.total_tokens": tokens.get("total_tokens", 0),
                    "llm.cost": cost,
                    "llm.latency_ms": duration_ms,
                    "cache.enabled": True,
                    "cache.hit": cache_hit,
                    "cache.latency_ms": cache_latency_ms if cache_hit else None,
                    "mlflow.spanType": "LLM"
                })
                
                # Stage 1: Input Validation (10% of time)
                with mlflow.start_span("1. Input Validation") as validation_span:
                    validation_span.set_attributes({
                        "stage": "validation",
                        "prompt_length": len(prompt),
                        "start_time": datetime.fromtimestamp(start_time).isoformat(),
                        "duration_ms": duration_ms * 0.1
                    })
                
                # Stage 2: Cache Check (20% of time)
                with mlflow.start_span("2. Cache Check") as cache_span:
                    cache_span.set_attributes({
                        "stage": "cache",
                        "cache_hit": cache_hit,
                        "latency_ms": cache_latency_ms if cache_hit else None,
                        "start_time": datetime.fromtimestamp(start_time + duration_ms * 0.1 / 1000).isoformat(),
                        "duration_ms": duration_ms * 0.2
                    })
                
                # Stage 3: LLM Processing (60% of time)
                with mlflow.start_span("3. LLM Processing") as process_span:
                    process_span.set_attributes({
                        "stage": "processing",
                        "tokens": tokens["total_tokens"],
                        "cost": cost,
                        "model": model,
                        "start_time": datetime.fromtimestamp(start_time + duration_ms * 0.3 / 1000).isoformat(),
                        "duration_ms": duration_ms * 0.6
                    })
                
                # Stage 4: Response Format (10% of time)
                with mlflow.start_span("4. Response Format") as format_span:
                    format_span.set_attributes({
                        "stage": "formatting",
                        "response_length": len(response),
                        "start_time": datetime.fromtimestamp(start_time + duration_ms * 0.9 / 1000).isoformat(),
                        "duration_ms": duration_ms * 0.1
                    })
                
                # Add timing event
                current_span.add_event(SpanEvent(
                    "timing_breakdown",
                    attributes={
                        "validation_ms": duration_ms * 0.1,
                        "cache_ms": duration_ms * 0.2,
                        "processing_ms": duration_ms * 0.6,
                        "formatting_ms": duration_ms * 0.1,
                        "total_ms": duration_ms,
                        "timestamp": datetime.fromtimestamp(current_time).isoformat()
                    }
                ))
            
            # Return information for MLflow visualization
            return {
                "prompt": prompt,
                "model": model,
                "response": response,
                "tokens": tokens,
                "cost": cost,
                "latency_ms": duration_ms,
                "cache_hit": cache_hit,
                "cache_latency_ms": cache_latency_ms
            }
            
        except Exception as e:
            print(f"⚠️ Failed to trace LLM request: {e}")
            return False


# Global instance
mlflow_service = MLflowService()
