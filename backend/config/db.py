# backend/config/db.py
# Shared database connection settings for Pirate Cove.
# Originally by Ryan Grimes 3/3/2026 (AWS RDS credentials).
# Updated by Anthony Jackson - Iteration 4 (11/11/26):
#   - One place builds the connection settings, used by init_db.py, seed_demo_data.py and the app.
#   - Works with AWS RDS (DB_SSLMODE=require) AND a local or Docker Postgres (DB_HOST=localhost or db).
#   - DATABASE_URL is supported too (it wins if it is set).
#   - is_local_host() tells scripts when it is safe to create a database or add demo data.
#   - No longer prints "Connected to AWS RDS" on every single connection.

import os
import psycopg2
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '../../.env'))   # project-root .env
load_dotenv()                                        # .env in the current folder, if any

# Hosts that count as "your own computer" or the Docker Postgres container.
# Demo data and CREATE DATABASE are only ever allowed on these.
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "db", "postgres", "host.docker.internal"}

_PLACEHOLDER_URL = "username:password@host"   # the example value in .env.example


def _env(name, default=None):
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def _database_url():
    url = _env("DATABASE_URL")
    if url and _PLACEHOLDER_URL not in url:
        return url
    return None


def connection_kwargs(dbname=None):
    """Build psycopg2.connect() arguments from the environment.

    dbname lets a caller connect to a different database on the same server
    (init_db.py uses 'postgres' to create the app database if it is missing).
    """
    url = _database_url()
    if url:
        kwargs = {"dsn": url}
        if dbname:
            kwargs["dbname"] = dbname
    else:
        kwargs = {
            "host": _env("DB_HOST", "localhost"),
            "dbname": dbname or _env("DB_NAME", "thevault"),
            "user": _env("DB_USER", "postgres"),
            "password": _env("DB_PASSWORD", ""),
            "port": int(_env("DB_PORT", "5432")),
        }
    sslmode = _env("DB_SSLMODE")
    if sslmode:
        kwargs["sslmode"] = sslmode
    sslrootcert = _env("DB_SSLROOTCERT")
    if sslrootcert:
        kwargs["sslrootcert"] = sslrootcert
    kwargs.setdefault("connect_timeout", int(_env("DB_CONNECT_TIMEOUT", "10")))
    return kwargs


def database_name():
    """The name of the app database (from DATABASE_URL or DB_NAME)."""
    url = _database_url()
    if url:
        from psycopg2.extensions import parse_dsn
        return parse_dsn(url).get("dbname") or "thevault"
    return _env("DB_NAME", "thevault")


def current_host():
    """The database host the app will use, lower-case."""
    url = _database_url()
    if url:
        from psycopg2.extensions import parse_dsn
        try:
            return (parse_dsn(url).get("host") or "localhost").lower()
        except Exception:
            return ""
    return (_env("DB_HOST", "localhost") or "").lower()


def is_local_host(host=None):
    """True when the database is on this computer or in our Docker container (never AWS RDS).
    Set PIRATECOVE_LOCAL_DB=1 to force this on for an unusual local setup."""
    if _env("PIRATECOVE_LOCAL_DB") == "1":
        return True
    return (host if host is not None else current_host()) in LOCAL_HOSTS


def connect(dbname=None):
    """Open a connection or raise psycopg2.Error. Use this when you want to see the real error."""
    return psycopg2.connect(**connection_kwargs(dbname))


def get_connection():
    """Open a connection, or return None if the database can't be reached.
    (Older code checks for None, so this keeps that behavior.)"""
    try:
        return connect()
    except Exception as e:
        print(f"Database connection error: {e}")
        return None
