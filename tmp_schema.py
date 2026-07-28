import psycopg2
import sys

db_url = "postgresql://neondb_owner:npg_Kf5ytejvpX4F@ep-floral-mountain-aiyb97qr-pooler.c-4.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

try:
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    cur.execute("""
        SELECT table_name, column_name, data_type 
        FROM information_schema.columns 
        WHERE table_schema = 'public' 
        ORDER BY table_name, ordinal_position;
    """)
    rows = cur.fetchall()
    
    current_table = None
    with open("tmp_schema_out.txt", "w") as f:
        for row in rows:
            if current_table != row[0]:
                current_table = row[0]
                f.write(f"\n--- TABLE: {current_table} ---\n")
            f.write(f"  {row[1]} ({row[2]})\n")
    print("Schema exported successfully.")
except Exception as e:
    print(f"Error: {e}")
