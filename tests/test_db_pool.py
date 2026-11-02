"""DB pool tests. Need DATABASE_URL; only use TEMP tables / SELECTs (safe on any DB)."""
import os
import threading
import unittest

import psycopg2

if os.getenv("DATABASE_URL"):
    from agent import db


@unittest.skipUnless(os.getenv("DATABASE_URL"), "DATABASE_URL not set")
class PoolTests(unittest.TestCase):
    def setUp(self):
        self.pool = db._Pool()
        self.addCleanup(self.pool.close_all)

    def test_reuses_idle_connection(self):
        c1 = self.pool.acquire()
        self.pool.release(c1)
        c2 = self.pool.acquire()
        self.assertIs(c1, c2)
        self.pool.release(c2)

    def test_rows_are_dicts(self):
        c = self.pool.acquire()
        with c.cursor() as cur:
            cur.execute("SELECT 1 AS one")
            self.assertEqual(cur.fetchone(), {"one": 1})
        self.pool.release(c)

    def test_release_rolls_back_uncommitted_work(self):
        c = self.pool.acquire()
        with c.cursor() as cur:
            cur.execute("CREATE TEMP TABLE pooltest (x int)")
            cur.execute("INSERT INTO pooltest VALUES (1)")
        self.pool.release(c)  # nothing committed
        c2 = self.pool.acquire()
        self.assertIs(c, c2)
        with c2.cursor() as cur:
            cur.execute("SELECT to_regclass('pg_temp.pooltest') AS t")
            self.assertIsNone(cur.fetchone()["t"])
        self.pool.release(c2)

    def test_aborted_transaction_does_not_poison_pool(self):
        c = self.pool.acquire()
        with self.assertRaises(psycopg2.Error):
            with c.cursor() as cur:
                cur.execute("SELECT * FROM table_that_does_not_exist")
        self.pool.release(c)
        c2 = self.pool.acquire()
        with c2.cursor() as cur:
            cur.execute("SELECT 2 AS two")
            self.assertEqual(cur.fetchone()["two"], 2)
        self.pool.release(c2)

    def test_committed_work_is_kept(self):
        c = self.pool.acquire()
        with c.cursor() as cur:
            cur.execute("CREATE TEMP TABLE pooltest2 (x int)")
            cur.execute("INSERT INTO pooltest2 VALUES (7)")
        c.commit()
        self.pool.release(c)
        c2 = self.pool.acquire()
        with c2.cursor() as cur:
            cur.execute("SELECT x FROM pooltest2")
            self.assertEqual(cur.fetchone()["x"], 7)
        self.pool.release(c2)

    def test_dead_idle_connection_is_replaced(self):
        old_validate = db._VALIDATE_AFTER_SECONDS
        db._VALIDATE_AFTER_SECONDS = 0  # always ping idle connections
        self.addCleanup(setattr, db, "_VALIDATE_AFTER_SECONDS", old_validate)
        c = self.pool.acquire()
        with c.cursor() as cur:
            cur.execute("SELECT pg_backend_pid() AS pid")
            pid = cur.fetchone()["pid"]
        self.pool.release(c)
        killer = psycopg2.connect(db.DATABASE_URL)
        killer.autocommit = True
        with killer.cursor() as cur:
            cur.execute("SELECT pg_terminate_backend(%s)", (pid,))
        killer.close()
        c2 = self.pool.acquire()  # must notice c is dead and open a fresh one
        self.assertIsNot(c, c2)
        with c2.cursor() as cur:
            cur.execute("SELECT 1 AS one")
            self.assertEqual(cur.fetchone()["one"], 1)
        self.pool.release(c2)

    def test_idle_cap_closes_extras(self):
        old = db._POOL_MAX_IDLE
        db._POOL_MAX_IDLE = 2
        self.addCleanup(setattr, db, "_POOL_MAX_IDLE", old)
        conns = [self.pool.acquire() for _ in range(4)]
        for c in conns:
            self.pool.release(c)
        self.assertEqual(len(self.pool._idle), 2)
        self.assertEqual(sum(1 for c in conns if c.closed), 2)

    def test_old_connections_are_recycled(self):
        old = db._MAX_CONN_AGE_SECONDS
        db._MAX_CONN_AGE_SECONDS = -1
        self.addCleanup(setattr, db, "_MAX_CONN_AGE_SECONDS", old)
        c = self.pool.acquire()
        self.pool.release(c)
        c2 = self.pool.acquire()
        self.assertIsNot(c, c2)
        self.assertTrue(c.closed)
        self.pool.release(c2)


@unittest.skipUnless(os.getenv("DATABASE_URL"), "DATABASE_URL not set")
class GetConnectionTests(unittest.TestCase):
    def test_context_manager_roundtrip_and_reuse(self):
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 AS one")
                self.assertEqual(cur.fetchone()["one"], 1)
        with db.get_connection() as conn2:
            pass
        self.assertIs(conn, conn2)

    def test_operational_error_discards_connection(self):
        with self.assertRaises(psycopg2.OperationalError):
            with db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT pg_backend_pid() AS pid")
                    pid = cur.fetchone()["pid"]
                killer = psycopg2.connect(db.DATABASE_URL)
                killer.autocommit = True
                with killer.cursor() as kc:
                    kc.execute("SELECT pg_terminate_backend(%s)", (pid,))
                killer.close()
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
        self.assertTrue(conn.closed)
        self.assertNotIn(conn, [c for c, _ in db._pool._idle])
        with db.get_connection() as fresh:  # pool still works afterwards
            with fresh.cursor() as cur:
                cur.execute("SELECT 1 AS one")
                self.assertEqual(cur.fetchone()["one"], 1)

    def test_other_exception_keeps_connection_usable(self):
        with self.assertRaises(ValueError):
            with db.get_connection() as conn:
                raise ValueError("boom")
        with db.get_connection() as conn2:
            self.assertFalse(conn2.closed)

    def test_concurrent_use(self):
        errors = []

        def work():
            try:
                for _ in range(5):
                    with db.get_connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute("SELECT 1 AS one")
                            assert cur.fetchone()["one"] == 1
            except Exception as e:  # noqa
                errors.append(e)

        threads = [threading.Thread(target=work) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        self.assertLessEqual(len(db._pool._idle), db._POOL_MAX_IDLE)


if __name__ == "__main__":
    unittest.main()
