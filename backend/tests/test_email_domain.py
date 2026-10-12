#By Tykeara Hammond
import sys
import os

from unittest.mock import MagicMock

# Ensure Python can see backend folder and subfolders
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.auth_services import AuthService

def test_student_email_accepted():
    fake_conn = MagicMock()
    success, message = AuthService().register_user("tester", "Password123", "test@my.hamptonu.edu", fake_conn)
    assert success is True

def test_staff_email_accepted():
    fake_conn = MagicMock()
    success, message = AuthService().register_user("tester", "Password321", "test@hamptonu.edu", fake_conn)
    assert success is True

def test_gmail_rejected():
    fake_conn = MagicMock()
    success, message = AuthService().register_user("tester", "Password123", "test@nothamptonu.edu", fake_conn)
    assert success is False
    fake_conn.cursor.assert_not_called()

def test_fake_domain_rejected():
    fake_conn = MagicMock()
    success, message = AuthService().register_user("tester", "Password123", "test@gmail.com", fake_conn)
    assert success is False
    fake_conn.cursor.assert_not_called()