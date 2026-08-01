import psycopg2
from psycopg2.extras import RealDictCursor
import os

DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    """Returns a standard psycopg2 connection, prioritizing DATABASE_URL if available."""
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL)
    
    return psycopg2.connect(
        dbname=os.getenv("PGDATABASE", "transcripts_warehouse"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", "password"),
        host=os.getenv("PGHOST", "localhost"),
        port=os.getenv("PGPORT", "5432")
    )

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