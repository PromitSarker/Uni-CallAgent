import os
import threading
import time
import psycopg2
import psycopg2.extensions
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from typing import Generator

from agent.config import DATABASE_URL

# --- Connection pool -------------------------------------------------------
# Opening a fresh TLS connection to a remote Postgres (Neon) for every query
# costs several round trips. We keep a few idle connections per process and
# reuse them. Semantics for callers are unchanged: `with get_connection() as
# conn:` still yields a psycopg2 connection (RealDictCursor), and anything not
# committed is rolled back when the block exits (exactly what close() did).
#
# The pool never blocks or caps callers: if no idle connection is available a
# new one is opened (as before) and, on release, kept only if there is room.
_POOL_MAX_IDLE = int(os.getenv("DB_POOL_MAX_IDLE", "5"))
# Idle connections older than this are pinged before reuse (servers/poolers
# drop idle sessions silently).
_VALIDATE_AFTER_SECONDS = float(os.getenv("DB_POOL_VALIDATE_AFTER_SECONDS", "20"))
# Recycle connections after this long regardless.
_MAX_CONN_AGE_SECONDS = float(os.getenv("DB_POOL_MAX_AGE_SECONDS", "300"))
_CONNECT_TIMEOUT = int(os.getenv("DB_CONNECT_TIMEOUT", "10"))

# References to connections inherited across a fork() are parked here and never
# closed in the child (closing would send Terminate on a socket the parent uses).
_inherited_conns: list = []


class _PooledConnection(psycopg2.extensions.connection):
    """psycopg2 connection that can carry pool bookkeeping attributes."""


class _Pool:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._idle: list = []  # (conn, last_used_monotonic)
        self._pid = os.getpid()

    def _check_pid(self) -> None:
        # Caller holds the lock.
        if self._pid != os.getpid():
            _inherited_conns.extend(c for c, _ in self._idle)
            self._idle = []
            self._pid = os.getpid()

    @staticmethod
    def _new_connection():
        conn = psycopg2.connect(
            DATABASE_URL,
            cursor_factory=RealDictCursor,
            connection_factory=_PooledConnection,
            connect_timeout=_CONNECT_TIMEOUT,
            keepalives=1,
            keepalives_idle=30,
            keepalives_interval=10,
            keepalives_count=3,
        )
        conn._pool_created = time.monotonic()
        return conn

    @staticmethod
    def _close_quietly(conn) -> None:
        try:
            conn.close()
        except Exception:
            pass

    def acquire(self):
        while True:
            with self._lock:
                self._check_pid()
                item = self._idle.pop() if self._idle else None  # LIFO: warmest first
            if item is None:
                return self._new_connection()

            conn, last_used = item
            now = time.monotonic()
            if conn.closed or now - getattr(conn, "_pool_created", 0) > _MAX_CONN_AGE_SECONDS:
                self._close_quietly(conn)
                continue
            if now - last_used > _VALIDATE_AFTER_SECONDS:
                try:
                    with conn.cursor() as cur:
                        cur.execute("SELECT 1")
                    conn.rollback()
                except Exception:
                    self._close_quietly(conn)
                    continue
            return conn

    def release(self, conn, broken: bool = False) -> None:
        if conn.closed:
            return
        if broken:
            self._close_quietly(conn)
            return
        try:
            # Drop any open/aborted transaction. Callers commit explicitly, so
            # this matches the old "close without commit" behaviour.
            conn.rollback()
        except Exception:
            self._close_quietly(conn)
            return
        with self._lock:
            self._check_pid()
            if len(self._idle) < _POOL_MAX_IDLE:
                self._idle.append((conn, time.monotonic()))
                return
        self._close_quietly(conn)

    def close_all(self) -> None:
        with self._lock:
            idle, self._idle = self._idle, []
        for conn, _ in idle:
            self._close_quietly(conn)


_pool = _Pool()


def initialize_db():
    if not DATABASE_URL:
        print("DATABASE_URL is not set, skipping database initialization")
        return

    print(f"Initializing database from schema...")

    # We always run the schema to ensure IF NOT EXISTS tables are created
    schema_path = os.path.join(os.path.dirname(__file__), "..", "sql", "schema.sql")
    if os.path.exists(schema_path):
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_script = f.read()

        try:
            with psycopg2.connect(DATABASE_URL) as conn:
                with conn.cursor() as cur:
                    cur.execute(schema_script)
                conn.commit()
        except Exception as e:
            print(f"Failed to initialize schema: {e}")

@contextmanager
def get_connection() -> Generator:
    conn = _pool.acquire()
    broken = False
    try:
        yield conn
    except (psycopg2.OperationalError, psycopg2.InterfaceError):
        # The connection itself is suspect; don't return it to the pool.
        broken = True
        raise
    finally:
        _pool.release(conn, broken)

# Initialize schema when this module is loaded
initialize_db()
