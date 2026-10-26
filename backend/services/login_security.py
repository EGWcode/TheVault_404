
# THE VAULT - Login Attempt Protection
# Added by Nicholas Smith - October 25, 2026
# Limits failed logins to 3 attempts, then locks for 60 seconds.

LOCK_SECONDS = 60
MAX_ATTEMPTS = 3


def initialize_login_security(conn):
    """Create the login security table if it does not exist."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS login_attempt_limits (
                username TEXT PRIMARY KEY,
                failed_attempts INTEGER NOT NULL DEFAULT 0,
                locked_until TIMESTAMPTZ
            )
        """)
    conn.commit()


def get_remaining_lock(conn, username):
    """Return lockout seconds remaining for this username."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT GREATEST(
                0,
                CEIL(EXTRACT(EPOCH FROM
                    (locked_until - CURRENT_TIMESTAMP)
                ))
            )::INTEGER
            FROM login_attempt_limits
            WHERE username = %s
        """, (username.lower(),))
        row = cur.fetchone()

    return row[0] if row and row[0] is not None else 0


def record_failed_login(conn, username):
    """Record a failed login and apply the lockout."""
    username = username.lower()

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO login_attempt_limits
                (username, failed_attempts, locked_until)
            VALUES (%s, 1, NULL)
            ON CONFLICT (username)
            DO UPDATE SET
                failed_attempts = CASE
                    WHEN login_attempt_limits.locked_until
                         IS NOT NULL
                         AND login_attempt_limits.locked_until
                             <= CURRENT_TIMESTAMP
                    THEN 1
                    ELSE login_attempt_limits.failed_attempts + 1
                END,
                locked_until = CASE
                    WHEN login_attempt_limits.locked_until
                         IS NOT NULL
                         AND login_attempt_limits.locked_until
                             <= CURRENT_TIMESTAMP
                    THEN NULL
                    WHEN login_attempt_limits.failed_attempts + 1
                         >= %s
                    THEN CURRENT_TIMESTAMP + INTERVAL '60 seconds'
                    ELSE NULL
                END
            RETURNING failed_attempts, locked_until
        """, (username, MAX_ATTEMPTS))

        attempts, locked_until = cur.fetchone()

    conn.commit()

    if locked_until is not None:
        return 0

    return max(0, MAX_ATTEMPTS - attempts)


def reset_login_attempts(conn, username):
    """Reset attempts when the user logs in successfully."""
    with conn.cursor() as cur:
        cur.execute("""
            DELETE FROM login_attempt_limits
            WHERE username = %s
        """, (username.lower(),))

    conn.commit()
