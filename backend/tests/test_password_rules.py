#By Tykeara Hammond 10/12/2026
import sys
import os

from unittest.mock import MagicMock

# Ensure Python can see backend folder and subfolders
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.auth_services import AuthService

def test_strong_password_accepted():
    fake_conn = MagicMock()
    success, message = AuthService().register_user("tester", "Password123!", "test@my.hamptonu.edu", fake_conn)
    assert success is True

def test_weak_password_rejected():
    fake_conn = MagicMock()
    success, message = AuthService().register_user("tester", "password", "test@my.hamptonu.edu", fake_conn)
    assert success is False

def test_no_uppercase_rejected():
    fake_conn = MagicMock()
    success, message = AuthService().register_user("tester", "password123!", "test@my.hamptonu.edu", fake_conn)
    assert success is False

def test_no_lowercase_rejected():
    fake_conn = MagicMock()
    success, message = AuthService().register_user("tester", "PASSWORD123!", "test@my.hamptonu.edu", fake_conn)
    assert success is False

def test_no_number_rejected():
    fake_conn = MagicMock()
    success, message = AuthService().register_user("tester", "Password!", "test@my.hamptonu.edu", fake_conn)
    assert success is False

def test_no_symbol_rejected():
    fake_conn = MagicMock()
    success, message = AuthService().register_user("tester", "Password123", "test@my.hamptonu.edu", fake_conn)
    assert success is False
