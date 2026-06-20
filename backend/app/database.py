import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_load

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    try:
        # Connect to your Supabase PostgreSQL instance
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        raise e