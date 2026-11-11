# scripts/inspect_db.py
# Debug tool (not a test): prints every table in the database and its columns.
# Moved out of backend/tests by Anthony Jackson 11/11/26 so pytest doesn't run it as a test.
#
#   python scripts/inspect_db.py
#
# Uses the same .env settings as the app (local, Docker or RDS). It only reads.

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from config.db import connect, current_host, database_name  # noqa: E402


def main():
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        tables = [row[0] for row in cur.fetchall()]
        print(f"Database '{database_name()}' on {current_host()}: {len(tables)} tables\n")

        for table_name in tables:
            # Parameterized (the old version pasted the table name into the SQL string)
            cur.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = %s
                ORDER BY ordinal_position
            """, (table_name,))
            print(table_name)
            for column, data_type, nullable in cur.fetchall():
                print(f"  - {column} ({data_type}{'' if nullable == 'YES' else ', not null'})")
            print()
        cur.close()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
