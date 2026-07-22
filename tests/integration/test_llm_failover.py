import pytest
from unittest.mock import patch, MagicMock
from fapi.db.models import CandidateLlmApiKeyORM

def test_llm_detect_provider(client, admin_headers):
    # Test prefix format detection
    payload = {"api_key": "sk-ant-1234567890abcdef"}
    response = client.post("/api/coderpad/me/llm-keys/detect-provider", json=payload, headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["provider_name"] == "Claude"
    assert "models" in data

def test_llm_discover_models(client, admin_headers):
    payload = {"provider_name": "OpenAI"}
    response = client.post("/api/coderpad/me/llm-keys/discover-models", json=payload, headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert "models" in data
    assert len(data["models"]) > 0

@patch("fapi.utils.llm_execution_service.execute_llm_request_with_failover")
def test_llm_failover_routing(mock_execute, client, admin_headers):
    # Setup mock to return a standard structure
    mock_execute.return_value = {
        "passed": True,
        "summary": "Mock passed",
        "feedback": "Great code!",
        "confidence": 0.95
    }

    payload = {
        "problem_statement": "Write a function that returns double the input",
        "code": "def solution(n):\n    return n * 2",
        "language": "python",
        "test_cases": [
            {"input": "5", "expected_output": "10", "description": "Double 5"}
        ]
    }
    response = client.post("/api/coderpad/llm-validate", json=payload, headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["passed"] is True
    assert data["summary"] == "Mock passed"
