import psycopg2
from psycopg2.extras import RealDictCursor
import os

# UPDATED with your actual database credentials
DB_CONFIG = {
    "dbname": os.getenv("PGDATABASE", "transcripts_warehouse"),
    "user": os.getenv("PGUSER", "postgres"),
    "password": os.getenv("PGPASSWORD", "password"),
    "host": os.getenv("PGHOST", "localhost"),
    "port": os.getenv("PGPORT", "5432")
}

def get_db_connection():
    """Returns a standard psycopg2 connection."""
    return psycopg2.connect(**DB_CONFIG)

def execute_query(query, params=None, fetch=False):
    """
    A clean, reusable wrapper for executing DB queries.
    Prevents connection leaks by using context managers.
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            if fetch:
                result = cur.fetchall()
                conn.commit()
                return result
            conn.commit()
            return None
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()