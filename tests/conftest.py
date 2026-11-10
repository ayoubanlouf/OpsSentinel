"""Pytest configuration and test fixtures for OpsSentinel."""

import os
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

# Ensure test environment variables
os.environ["ENVIRONMENT"] = "testing"
os.environ["GEMINI_API_KEY"] = os.environ.get("GEMINI_API_KEY", "test-mock-api-key")
os.environ["POSTGRES_DB"] = "opssentinel"

from opssentinel.api.main import app


@pytest.fixture(scope="session")
def test_client():
    """FastAPI test client fixture."""
    with TestClient(app) as client:
        yield client


@pytest.fixture
def mock_gemini_client():
    """Mock Google GenAI client returning realistic embedding vectors and completions."""
    mock_client = MagicMock()

    # Mock embed_content
    mock_embedding = MagicMock()
    mock_embedding.values = [0.01 * (i % 50) for i in range(768)]
    mock_response = MagicMock()
    mock_response.embeddings = [mock_embedding]
    mock_client.models.embed_content.return_value = mock_response

    # Mock generate_content
    mock_gen_response = MagicMock()
    mock_candidate = MagicMock()
    mock_part = MagicMock()
    mock_part.text = "Root cause analyzed. Remediation applied."
    mock_part.function_call = None
    mock_candidate.content.parts = [mock_part]
    mock_gen_response.candidates = [mock_candidate]
    mock_client.models.generate_content.return_value = mock_gen_response

    return mock_client
