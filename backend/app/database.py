import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool
from dotenv import load_dotenv
from threading import Lock

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

logging.basicConfig(level=logging.INFO)
logging.getLogger("rxos.access").setLevel(logging.INFO)
logging.getLogger("rxos.error").setLevel(logging.ERROR)
logging.getLogger("rxos.auth").setLevel(logging.INFO)

logger = logging.getLogger("rxos.db")

_pool = None
_pool_lock = Lock()


class PooledConnection:
    """Return a psycopg2 connection to its pool when route code calls close()."""

    def __init__(self, connection, pool):
        self._connection = connection
        self._pool = pool
        self._returned = False

    def __getattr__(self, name):
        return getattr(self._connection, name)

    def close(self):
        if self._returned:
            return

        discard = False
        try:
            # Ensure an unsuccessful read or write never leaks its transaction
            # into the next request that borrows this connection.
            self._connection.rollback()
        except psycopg2.Error:
            discard = True

        self._pool.putconn(self._connection, close=discard)
        self._returned = True


def _get_pool():
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                if not DATABASE_URL:
                    raise RuntimeError("DATABASE_URL is not configured")
                # The dashboard can make five concurrent requests on first load.
                # Keep enough warm slots for that burst while remaining modest for
                # Supabase/free-tier deployments.
                max_connections = max(5, int(os.getenv("DB_POOL_MAX", "5")))
                _pool = ThreadedConnectionPool(
                    1,
                    max_connections,
                    DATABASE_URL,
                    cursor_factory=RealDictCursor,
                )
    return _pool


def get_db_connection():
    try:
        pool = _get_pool()
        return PooledConnection(pool.getconn(), pool)
    except Exception as e:
        logger.error("Database connection failed: %s", e)
        raise
