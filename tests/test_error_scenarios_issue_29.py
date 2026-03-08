
import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from src.api.main import create_checkout_session
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

@pytest.fixture
def mock_db():
    return MagicMock(spec=Session)

@pytest.fixture
def task_submission_payload():
    return {
        "domain": "accounting",
        "title": "Test Task",
        "description": "Test Description",
        "complexity": "medium",
        "urgency": "standard"
    }

@patch("src.api.payments.stripe.checkout.Session.create")
def test_stripe_network_timeout(mock_stripe_create, mock_db, task_submission_payload):
    """Test handling of Stripe API timeouts (Issue #29)"""
    import stripe
    mock_stripe_create.side_effect = stripe.error.APIConnectionError("Network timeout")
    
    with pytest.raises(HTTPException) as excinfo:
        import asyncio
        asyncio.run(create_checkout_session(task_submission_payload, mock_db))
    
    assert excinfo.value.status_code == 503
    assert "Stripe API is temporarily unavailable" in excinfo.value.detail

@patch("src.api.payments.stripe.checkout.Session.create")
def test_database_operational_error(mock_stripe_create, mock_db, task_submission_payload):
    """Test handling of database connection failures (Issue #29)"""
    mock_db.add.side_effect = OperationalError("connection failure", None, None)
    
    with pytest.raises(HTTPException) as excinfo:
        import asyncio
        asyncio.run(create_checkout_session(task_submission_payload, mock_db))
    
    assert excinfo.value.status_code == 500
    assert "Database error occurred" in excinfo.value.detail

@patch("src.api.payments.stripe.checkout.Session.create")
@patch("src.llm_service.LLMService.complete")
def test_llm_service_outage(mock_llm_complete, mock_stripe_create, mock_db, task_submission_payload):
    """Test handling of LLM service outages (Issue #29)"""
    mock_llm_complete.side_effect = Exception("LLM service down")
    
    # Note: price calculation might use LLM in some paths, 
    # but here we test the general failure handling
    with pytest.raises(Exception):
        import asyncio
        asyncio.run(create_checkout_session(task_submission_payload, mock_db))

def test_invalid_input_data(mock_db):
    """Test handling of invalid input data (Issue #29)"""
    from src.api.main import TaskSubmission
    from pydantic import ValidationError
    
    invalid_payload = {
        "domain": "invalid_domain", # Should fail validation
        "title": "", # Too short
    }
    
    with pytest.raises(ValidationError):
        TaskSubmission(**invalid_payload)

@patch("src.api.payments.stripe.checkout.Session.create")
def test_concurrency_conflict_retry(mock_stripe_create, mock_db, task_submission_payload):
    """Test handling of concurrency conflicts (Issue #29)"""
    from sqlalchemy.orm.exc import StaleDataError

    mock_db.commit.side_effect = StaleDataError("Conflict detected")
    
    with pytest.raises(HTTPException) as excinfo:
        import asyncio
        asyncio.run(create_checkout_session(task_submission_payload, mock_db))
    
    assert excinfo.value.status_code == 409
    assert "conflict" in excinfo.value.detail.lower() or "retry" in excinfo.value.detail.lower()
