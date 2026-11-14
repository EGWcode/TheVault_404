"""
Purchase History API Automated Tests
Created by Sidney Cerami - 11/13/2026

Purpose:
Tests the Purchase History API endpoint (/api/orders/my) to ensure
users must be logged in, authenticated users can retrieve their
purchase history, and API errors are handled correctly.

Testing approach:
Uses Flask's test client and mocked order service responses to test
the endpoint without modifying or accessing the AWS RDS database.
"""

import os
import sys
import pytest
from flask import Flask

# Allow imports from the backend directory
sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )
)

from controllers.checkout_controller import checkout_bp


@pytest.fixture
def client():
    # Create a minimal test app without importing app.py
    app = Flask(__name__)
    app.secret_key = "test-secret-key"
    app.config["TESTING"] = True

    app.register_blueprint(checkout_bp, url_prefix="/api")

    return app.test_client()


def test_purchase_history_requires_login(client):
    response = client.get("/api/orders/my")

    assert response.status_code == 401


def test_purchase_history_returns_orders(client, monkeypatch):
    expected_orders = [
        {
            "id": 1,
            "confirmation_number": "TEST123",
            "total_amount": 45.00
        }
    ]

    def mock_get_orders(user_id):
        assert user_id == 25
        return expected_orders

    monkeypatch.setattr(
        "controllers.checkout_controller.get_user_orders_service",
        mock_get_orders
    )

    with client.session_transaction() as session:
        session["user_id"] = 25

    response = client.get("/api/orders/my")

    assert response.status_code == 200
    assert response.get_json()["orders"] == expected_orders


def test_purchase_history_handles_service_error(client, monkeypatch):
    def mock_get_orders(user_id):
        raise Exception("Test database error")

    monkeypatch.setattr(
        "controllers.checkout_controller.get_user_orders_service",
        mock_get_orders
    )

    with client.session_transaction() as session:
        session["user_id"] = 25

    response = client.get("/api/orders/my")

    assert response.status_code == 500
    assert "error" in response.get_json()
