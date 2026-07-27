FROM ghcr.io/berriai/litellm:main-latest

# Install MLflow for integration.
# The litellm image ships a uv-managed venv without pip, so bootstrap pip first.
RUN python -m ensurepip --upgrade && \
    python -m pip install --no-cache-dir mlflow

# Copy any additional config if needed
WORKDIR /app