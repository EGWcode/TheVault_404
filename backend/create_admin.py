# The Pirate Cove Campus Marketplace
# Created by Ethan Williams 11/9/26

"""
create_admin.py

Creates an admin account, or turns an existing account into an admin.
Admins log in at /auth/admin-login.

Run from the project folder:
    python backend/create_admin.py                 (asks for everything)
    python backend/create_admin.py --promote NAME  (makes an existing user an admin)
    python backend/create_admin.py --demote NAME   (turns an admin back into a normal user)

The password must pass the same strength rule as sign up
(8+ characters with upper case, lower case, a number and a symbol).
"""

import argparse
import getpass
import os
import sys

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

from db import get_connection
from services.auth_services import AuthService
from utils.auth_utils import hash_password


def set_role(username, role):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET role = %s WHERE username = %s", (role, username))
            changed = cur.rowcount
        conn.commit()
    finally:
        conn.close()

    if changed:
        print(f"'{username}' is now role '{role}'.")
        return 0
    print(f"No user named '{username}'.")
    return 1


def create_admin():
    username = input("Admin username: ").strip()
    if not username:
        print("Username can't be empty.")
        return 1

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT role FROM users WHERE username = %s", (username,))
            existing = cur.fetchone()

        if existing:
            if (existing[0] or "").lower() == "admin":
                print(f"'{username}' is already an admin.")
                return 0
            answer = input(f"'{username}' already exists. Make this account an admin? [y/N] ").strip().lower()
            if answer != "y":
                print("Nothing changed.")
                return 1
            conn.close()
            return set_role(username, "admin")

        email = input("Admin email: ").strip()
        if "@" not in email:
            print("Please enter a valid email.")
            return 1

        password = getpass.getpass("Password: ")
        if not AuthService().validate_password(password):
            print("Password needs 8+ characters with upper case, lower case, a number and a symbol (#?!@$%^&*_-).")
            return 1
        if getpass.getpass("Password again: ") != password:
            print("Passwords don't match.")
            return 1

        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (username, password, email, role) VALUES (%s, %s, %s, 'admin')",
                (username, hash_password(password), email),
            )
        conn.commit()
        print(f"Admin '{username}' created. Log in at /auth/admin-login on the running site.")
        return 0
    except Exception as e:
        conn.rollback()
        print(f"Could not create the admin: {e}")
        return 1
    finally:
        if not conn.closed:
            conn.close()


def main():
    parser = argparse.ArgumentParser(description="Create or manage Pirate Cove admin accounts.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--promote", metavar="USERNAME", help="make an existing user an admin")
    group.add_argument("--demote", metavar="USERNAME", help="make an admin a normal user")
    args = parser.parse_args()

    try:
        if args.promote:
            return set_role(args.promote, "admin")
        if args.demote:
            return set_role(args.demote, "user")
        return create_admin()
    except Exception as e:
        print(f"Database error: {e}")
        print("Check the DB_ settings in your .env file.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
