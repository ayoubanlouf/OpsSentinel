# ==============================================================================
# OpsSentinel Production Container Image
# ==============================================================================
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml requirements.txt requirements-dev.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r requirements-dev.txt

# Copy application source and documentation
COPY src/ ./src/
COPY docs/ ./docs/
COPY scripts/ ./scripts/
COPY README.md ./

# Install local package in editable mode
RUN pip install --no-cache-dir -e .

# Expose API port
EXPOSE 8000

# Run FastAPI server with Uvicorn
CMD ["uvicorn", "opssentinel.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
