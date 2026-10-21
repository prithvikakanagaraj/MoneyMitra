"""Tests for src/database.py - uses a throw-away database, never your real one."""
import os
import sqlite3
import tempfile
import unittest
from datetime import date

from src import config, database
from src.validation import validate_transaction


def make_txn(description="Test", amount="100", txn_type="expense", category="Food", d=date(2025, 1, 15)):
    cleaned, errors = validate_transaction(d, description, amount, txn_type, category)
    assert not errors, errors
    return cleaned


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "test.db")
        database.init_db(self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def test_new_database_is_empty(self):
        self.assertEqual(len(database.get_transactions(self.db)), 0)

    def test_init_db_is_safe_to_call_twice_and_keeps_data(self):
        database.add_transaction(make_txn(), self.db)
        database.init_db(self.db)
        self.assertEqual(len(database.get_transactions(self.db)), 1)

    def test_added_transaction_can_be_read_back(self):
        new_id = database.add_transaction(make_txn("Pizza", "349.99", "expense", "Food"), self.db)
        df = database.get_transactions(self.db)
        row = df.iloc[0]
        self.assertEqual(row["id"], new_id)
        self.assertEqual(row["description"], "Pizza")
        self.assertAlmostEqual(row["amount"], 349.99)
        self.assertEqual(row["type"], "expense")
        self.assertEqual(row["category"], "Food")
        self.assertEqual(row["date"].date(), date(2025, 1, 15))

    def test_data_persists_across_new_connections(self):
        """Simulates closing and restarting the app: a brand-new connection still sees the data."""
        database.add_transaction(make_txn("Persistent"), self.db)
        raw = sqlite3.connect(self.db)
        count = raw.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        raw.close()
        self.assertEqual(count, 1)

    def test_newest_transaction_comes_first(self):
        database.add_transaction(make_txn("Old", d=date(2025, 1, 1)), self.db)
        database.add_transaction(make_txn("New", d=date(2025, 2, 1)), self.db)
        self.assertEqual(database.get_transactions(self.db).iloc[0]["description"], "New")

    def test_database_itself_rejects_bad_rows(self):
        """Second line of defence: even if validation were skipped, SQLite refuses bad data."""
        conn = sqlite3.connect(self.db)
        bad_rows = [
            ("2025-01-01", "x", -5, "expense", "Food"),     # negative amount
            ("2025-01-01", "x", 0, "expense", "Food"),      # zero amount
            ("2025-01-01", "x", 5, "transfer", "Food"),     # unknown type
            ("2025-01-01", "   ", 5, "expense", "Food"),    # blank description
        ]
        for row in bad_rows:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("INSERT INTO transactions (date, description, amount, type, category) VALUES (?,?,?,?,?)", row)
        conn.close()

    def test_delete_transaction(self):
        new_id = database.add_transaction(make_txn(), self.db)
        self.assertTrue(database.delete_transaction(new_id, self.db))
        self.assertFalse(database.delete_transaction(new_id, self.db))  # already gone
        self.assertEqual(len(database.get_transactions(self.db)), 0)

    def test_delete_sample_transactions_only_removes_samples(self):
        database.add_transaction(make_txn(config.SAMPLE_PREFIX + "Fake coffee"), self.db)
        database.add_transaction(make_txn("Real coffee"), self.db)
        self.assertEqual(database.delete_sample_transactions(self.db), 1)
        remaining = database.get_transactions(self.db)
        self.assertEqual(list(remaining["description"]), ["Real coffee"])


if __name__ == "__main__":
    unittest.main()
