# test_db.py
# First version by Ryan Grimes 2/27/2026 (a script that tried to connect to RDS).
# Rewritten as real pytest tests by Anthony Jackson - Iteration 4 (11/11/26).
#
# These check HOW the app builds its database connection (backend/config/db.py).
# No database is needed: they only look at the settings, so they always run.
# Test case IDs match the Test Specification (DB-01 ... DB-08).

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest  # noqa: E402

from config import db as dbconfig  # noqa: E402

DB_VARS = ("DATABASE_URL", "DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD",
           "DB_SSLMODE", "DB_SSLROOTCERT", "PIRATECOVE_LOCAL_DB")


@pytest.fixture
def clean_env(monkeypatch):
    """Start every test with none of the DB_ settings, then set only what the test needs."""
    for name in DB_VARS:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


# DB-01
def test_local_settings_are_used(clean_env):
    clean_env.setenv("DB_HOST", "localhost")
    clean_env.setenv("DB_PORT", "5544")
    clean_env.setenv("DB_NAME", "cove")
    clean_env.setenv("DB_USER", "me")
    clean_env.setenv("DB_PASSWORD", "pw")
    kw = dbconfig.connection_kwargs()
    assert kw["host"] == "localhost"
    assert kw["port"] == 5544            # the old init_db.py ignored DB_PORT
    assert kw["dbname"] == "cove"
    assert "sslmode" not in kw           # no SSL for a local database


# DB-02
def test_rds_ssl_settings_are_passed(clean_env):
    clean_env.setenv("DB_HOST", "piratecove.abc123.us-east-2.rds.amazonaws.com")
    clean_env.setenv("DB_SSLMODE", "require")
    clean_env.setenv("DB_SSLROOTCERT", "/certs/rds.pem")
    kw = dbconfig.connection_kwargs()
    assert kw["sslmode"] == "require"
    assert kw["sslrootcert"] == "/certs/rds.pem"


# DB-03
def test_database_url_wins(clean_env):
    clean_env.setenv("DB_HOST", "ignored-host")
    clean_env.setenv("DATABASE_URL", "postgresql://u:p@db:5432/vault")
    kw = dbconfig.connection_kwargs()
    assert kw == {"dsn": "postgresql://u:p@db:5432/vault", "connect_timeout": 10}
    assert dbconfig.current_host() == "db"
    assert dbconfig.database_name() == "vault"


# DB-04
def test_example_placeholder_url_is_ignored(clean_env):
    """.env.example ships DATABASE_URL=postgresql://username:password@host:5432/dbname."""
    clean_env.setenv("DATABASE_URL", "postgresql://username:password@host:5432/dbname")
    clean_env.setenv("DB_HOST", "localhost")
    assert "dsn" not in dbconfig.connection_kwargs()
    assert dbconfig.current_host() == "localhost"


# DB-05
def test_other_database_name_for_create_database(clean_env):
    clean_env.setenv("DB_NAME", "cove")
    assert dbconfig.connection_kwargs(dbname="postgres")["dbname"] == "postgres"


# DB-06
@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "::1", "db", "postgres"])
def test_local_and_docker_hosts_are_local(clean_env, host):
    clean_env.setenv("DB_HOST", host)
    assert dbconfig.is_local_host()


# DB-07: demo data / CREATE DATABASE must never touch AWS
@pytest.mark.parametrize("host", ["piratecove.abc123.us-east-2.rds.amazonaws.com", "10.0.0.5", ""])
def test_rds_is_never_local(clean_env, host):
    clean_env.setenv("DB_HOST", host)
    if host == "":
        clean_env.setenv("DB_HOST", " ")   # blank falls back to the default (localhost)
        assert dbconfig.is_local_host()
    else:
        assert not dbconfig.is_local_host()


# DB-08
def test_get_connection_returns_none_when_unreachable(clean_env):
    clean_env.setenv("DB_HOST", "localhost")
    clean_env.setenv("DB_PORT", "1")          # nothing listens on port 1
    clean_env.setenv("DB_CONNECT_TIMEOUT", "2")
    assert dbconfig.get_connection() is None
