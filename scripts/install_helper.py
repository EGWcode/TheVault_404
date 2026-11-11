# The Pirate Cove Campus Marketplace
# Created by Ethan Williams 11/9/26

"""
scripts/install_helper.py

The part of the installer that is the same on macOS and Windows.
install.command / install.bat create the venv, install requirements, then run:

    venv/bin/python scripts/install_helper.py        (macOS)
    venv\\Scripts\\python scripts\\install_helper.py   (Windows)

Steps:
1. Make .env (asks for the database settings, generates SECRET_KEY)
2. Connect to PostgreSQL (offers to install it with Homebrew on a Mac, and
   creates the database if it doesn't exist yet on this computer)
3. Create the tables (backend/init_db.py)
4. Offer to create an admin account (backend/create_admin.py)

It is safe to run again: an existing .env is kept unless you choose to replace it.
"""

import getpass
import os
import platform
import secrets
import shutil
import subprocess
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND = os.path.join(ROOT, "backend")
ENV_PATH = os.path.join(ROOT, ".env")
IS_MAC = platform.system() == "Darwin"
IS_WINDOWS = platform.system() == "Windows"
LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1")

sys.path.insert(0, BACKEND)
os.chdir(ROOT)


def say(message=""):
    print(message, flush=True)


def ask(question, default=""):
    suffix = f" [{default}]" if default else ""
    try:
        answer = input(f"{question}{suffix}: ").strip()
    except EOFError:
        answer = ""
    return answer or default


def ask_yes(question, default=True):
    hint = "Y/n" if default else "y/N"
    answer = ask(f"{question} ({hint})").lower()
    if not answer:
        return default
    return answer.startswith("y")


# ---------------------------------------------------------------------------
# Step 1: .env
# ---------------------------------------------------------------------------

def write_env(values):
    lines = [
        "# Made by the Pirate Cove installer. Keep this file private (it holds passwords).",
        "FLASK_ENV=development",
        f"SECRET_KEY={secrets.token_hex(32)}",
        "",
        "# PostgreSQL",
        f"DB_HOST={values['DB_HOST']}",
        f"DB_PORT={values['DB_PORT']}",
        f"DB_NAME={values['DB_NAME']}",
        f"DB_USER={values['DB_USER']}",
        f"DB_PASSWORD={values['DB_PASSWORD']}",
        f"DB_SSLMODE={values['DB_SSLMODE']}",
        "",
        "# Image uploads: leave AWS_S3_BUCKET empty to save images in static/uploads/",
        "AWS_ACCESS_KEY_ID=",
        "AWS_SECRET_ACCESS_KEY=",
        "AWS_REGION=us-east-2",
        "AWS_S3_BUCKET=",
        "",
        "# Optional: Stripe test key for card checkout, SMTP for forgot-username emails",
        "STRIPE_SECRET_KEY=",
        "SMTP_HOST=",
        "SMTP_PORT=587",
        "SMTP_USER=",
        "SMTP_PASSWORD=",
        "SMTP_FROM=",
        "",
    ]
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    try:
        os.chmod(ENV_PATH, 0o600)  # only this user can read it (no effect on Windows)
    except OSError:
        pass


def setup_env():
    say("\n== Step 1 of 4: settings (.env) ==")
    if os.path.exists(ENV_PATH):
        if ask_yes("A .env file already exists. Keep it?", default=True):
            say("Keeping the existing .env.")
            return
        backup = ENV_PATH + ".bak"
        shutil.copyfile(ENV_PATH, backup)
        say(f"Saved a copy of the old file as {os.path.basename(backup)}.")

    say("Where is the PostgreSQL database?")
    say("  1) On this computer (recommended for testing)")
    say("  2) Another server, e.g. the team's AWS RDS database")
    choice = ask("Choose 1 or 2", "1")

    if choice == "2":
        values = {
            "DB_HOST": ask("Database host (endpoint)"),
            "DB_PORT": ask("Port", "5432"),
            "DB_NAME": ask("Database name"),
            "DB_USER": ask("Username"),
            "DB_PASSWORD": getpass.getpass("Password: "),
            "DB_SSLMODE": ask("SSL mode", "require"),
        }
    else:
        # Homebrew's PostgreSQL uses your Mac username with no password;
        # the Windows installer creates a 'postgres' user with the password you chose.
        default_user = getpass.getuser() if IS_MAC else "postgres"
        values = {
            "DB_HOST": "localhost",
            "DB_PORT": ask("Port", "5432"),
            "DB_NAME": ask("Database name", "thevault"),
            "DB_USER": ask("PostgreSQL username", default_user),
            "DB_PASSWORD": getpass.getpass("PostgreSQL password (press Enter if none): "),
            "DB_SSLMODE": "",
        }

    write_env(values)
    say("Saved .env (with a new random SECRET_KEY).")


# ---------------------------------------------------------------------------
# Step 2: database connection
# ---------------------------------------------------------------------------

def load_env():
    from dotenv import load_dotenv
    load_dotenv(ENV_PATH, override=True)


def connect(dbname=None):
    import psycopg2
    kwargs = dict(
        host=os.getenv("DB_HOST"),
        dbname=dbname or os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD") or None,
        port=int(os.getenv("DB_PORT") or 5432),
        connect_timeout=10,
    )
    if os.getenv("DB_SSLMODE"):
        kwargs["sslmode"] = os.getenv("DB_SSLMODE")
    return psycopg2.connect(**kwargs)


def is_local():
    return (os.getenv("DB_HOST") or "").strip().lower() in LOCAL_HOSTS


def offer_postgres_install():
    """Called when nothing answers on the local PostgreSQL port."""
    if IS_MAC and shutil.which("brew"):
        if not ask_yes("PostgreSQL isn't running on this Mac. Install and start it with Homebrew now?"):
            return False
        for cmd in (["brew", "install", "postgresql@16"], ["brew", "services", "start", "postgresql@16"]):
            say("Running: " + " ".join(cmd))
            if subprocess.call(cmd) != 0:
                say("That command failed. See the messages above.")
                return False
        say("Waiting for PostgreSQL to start...")
        time.sleep(5)
        return True

    if IS_MAC:
        say("PostgreSQL isn't running. Install it from https://postgresapp.com (or install Homebrew from https://brew.sh),")
    else:
        say("PostgreSQL isn't running. Install it from https://www.postgresql.org/download/windows/")
        say("(remember the password you pick for the 'postgres' user),")
    say("then run this installer again.")
    return False


def create_local_database():
    from psycopg2 import sql
    name = os.getenv("DB_NAME")
    conn = connect(dbname="postgres")
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    conn.close()
    say(f"Created the database '{name}'.")


def check_database(tries_left=2):
    import psycopg2
    try:
        connect().close()
        say(f"Connected to '{os.getenv('DB_NAME')}' on {os.getenv('DB_HOST')}.")
        return True
    except psycopg2.OperationalError as e:
        message = str(e).strip()

    if tries_left > 0 and is_local():
        if "does not exist" in message and "database" in message:
            try:
                create_local_database()
                return check_database(tries_left - 1)
            except Exception as e:
                say(f"Could not create the database: {e}")
                return False
        if "Connection refused" in message or "could not connect" in message or "No such file" in message:
            if offer_postgres_install():
                return check_database(tries_left - 1)
            return False

    say(f"Could not connect to the database:\n  {message}")
    say("Check the DB_ settings in .env (or run the installer again and choose not to keep it).")
    return False


# ---------------------------------------------------------------------------
# Steps 3 and 4: tables and admin account
# ---------------------------------------------------------------------------

def create_tables():
    say("\n== Step 3 of 4: tables ==")
    from init_db import create_vault_tables
    return create_vault_tables()


def admin_exists():
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM users WHERE LOWER(role) = 'admin' LIMIT 1")
            return cur.fetchone() is not None
    finally:
        conn.close()


def offer_admin():
    say("\n== Step 4 of 4: admin account ==")
    if admin_exists():
        say("An admin account already exists. (Add more with: python backend/create_admin.py)")
        return
    if ask_yes("Create an admin account now? (needed for /auth/admin-login)"):
        from create_admin import create_admin
        create_admin()
    else:
        say("Skipped. You can do it later with: python backend/create_admin.py")


def main():
    say("The Pirate Cove setup")
    setup_env()
    load_env()
    say("\n== Step 2 of 4: database connection ==")
    if not check_database():
        return 1
    if not create_tables():
        say("Creating the tables failed. See the SCHEMA ERROR above.")
        return 1
    offer_admin()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        say("\nStopped.")
        sys.exit(1)
