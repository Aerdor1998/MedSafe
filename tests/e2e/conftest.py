"""
E2E Test Configuration with Playwright

PHASE 1: End-to-end testing setup
SKILLS: @debugging-strategies, @backend-dev-guidelines
"""

import pytest
import os
from playwright.sync_api import Page, expect

# Base URL for tests
BASE_URL = os.getenv("E2E_BASE_URL", "http://localhost:9001")


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Configure browser context for all tests"""
    return {
        **browser_context_args,
        "viewport": {"width": 1280, "height": 720},
        "ignore_https_errors": True,
    }


@pytest.fixture
def api_url():
    """Return the API base URL"""
    return BASE_URL


@pytest.fixture
def authenticated_page(page: Page, api_url: str):
    """
    Page fixture with authentication
    
    Note: This fixture assumes an auth system is in place.
    For now, returns unauthenticated page.
    """
    # TODO: Implement authentication when needed
    # For now, return the page directly
    return page


@pytest.fixture
def test_patient_data():
    """Sample patient data for E2E tests"""
    return {
        "age": 45,
        "weight": 70.0,
        "gender": "masculino",
        "conditions": ["hipertensão", "diabetes tipo 2"],
        "allergies": ["penicilina"],
        "current_medications": ["metformina", "losartana"],
        "pregnant": False,
        "renal_function": "normal",
        "hepatic_function": "normal",
    }


@pytest.fixture
def test_medication():
    """Sample medication for E2E tests"""
    return {
        "name": "Dipirona",
        "dosage": "500mg",
        "frequency": "8/8h",
    }
