import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

logging.basicConfig(level=logging.INFO)
logging.getLogger("rxos.access").setLevel(logging.INFO)
logging.getLogger("rxos.error").setLevel(logging.ERROR)
logging.getLogger("rxos.auth").setLevel(logging.INFO)

logger = logging.getLogger("rxos.db")


def get_db_connection():
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise e
