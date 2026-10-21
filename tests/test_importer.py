"""Tests for CSV and Excel transaction import and atomic batch processing."""
from datetime import date, timedelta
from io import BytesIO, StringIO
import os
import sqlite3
import tempfile
import unittest

import pandas as pd

from src import config, database
from src.importer import (
    ImportValidationError,
    map_columns,
    parse_and_validate_file,
    parse_raw_date,
    read_uploaded_file,
)
from src.validation import validate_transaction


class ImporterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "test_import.db")
        database.init_db(self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def test_map_columns_standard_and_aliases(self):
        # Exact names
        exact = ["date", "description", "amount", "type", "category"]
        mapping, missing = map_columns(exact)
        self.assertEqual(missing, [])
        self.assertEqual(mapping["date"], "date")

        # Mixed casing and aliases
        varied = ["Transaction_Date", "Details", "AMT", "Direction", "Category"]
        mapping, missing = map_columns(varied)
        self.assertEqual(missing, [])
        self.assertEqual(mapping["date"], "Transaction_Date")
        self.assertEqual(mapping["description"], "Details")
        self.assertEqual(mapping["amount"], "AMT")

        # Missing required column
        incomplete = ["Date", "Description", "Category"]
        mapping, missing = map_columns(incomplete)
        self.assertIn("Amount", missing)
        self.assertIn("Type", missing)

    def test_parse_raw_date(self):
        self.assertEqual(parse_raw_date("2025-01-15"), date(2025, 1, 15))
        self.assertEqual(parse_raw_date("15/01/2025"), date(2025, 1, 15))
        self.assertEqual(parse_raw_date("15-01-2025"), date(2025, 1, 15))
        self.assertEqual(parse_raw_date(pd.Timestamp("2025-01-15")), date(2025, 1, 15))
        self.assertIsNone(parse_raw_date(""))
        self.assertIsNone(parse_raw_date(None))

    def test_valid_csv_import(self):
        csv_content = (
            "Date,Description,Amount,Type,Category\n"
            "2025-01-10,Grocery shopping,1500.50,expense,Food\n"
            "2025-01-11,Monthly Salary,50000,income,Salary\n"
        )
        buf = BytesIO(csv_content.encode("utf-8"))
        result = parse_and_validate_file(buf, filename="transactions.csv", db_path=self.db)

        self.assertEqual(result["total_rows"], 2)
        self.assertEqual(result["valid_count"], 2)
        self.assertEqual(result["invalid_count"], 0)
        self.assertEqual(result["duplicate_count"], 0)
        self.assertEqual(len(result["rows_to_import"]), 2)

        # Batch insert
        count = database.add_transactions_batch(result["rows_to_import"], db_path=self.db)
        self.assertEqual(count, 2)
        saved = database.get_transactions(self.db)
        self.assertEqual(len(saved), 2)
        self.assertEqual(saved.iloc[0]["description"], "Monthly Salary")

    def test_valid_excel_xlsx_import(self):
        df = pd.DataFrame([
            {"Date": "2025-01-15", "Description": "Bus Pass", "Amount": "800", "Type": "expense", "Category": "Travel"},
            {"Date": "2025-01-16", "Description": "Freelance", "Amount": "12000", "Type": "income", "Category": "Freelance"},
        ])
        buf = BytesIO()
        df.to_excel(buf, index=False, engine="openpyxl")
        buf.seek(0)

        result = parse_and_validate_file(buf, filename="transactions.xlsx", db_path=self.db)
        self.assertEqual(result["total_rows"], 2)
        self.assertEqual(result["valid_count"], 2)
        self.assertEqual(result["invalid_count"], 0)

        inserted = database.add_transactions_batch(result["rows_to_import"], db_path=self.db)
        self.assertEqual(inserted, 2)

    def test_invalid_rows_isolated_and_reported(self):
        future_date = (date.today() + timedelta(days=2)).isoformat()
        csv_content = (
            "Date,Description,Amount,Type,Category\n"
            "2025-01-10,Valid Dinner,450.00,expense,Food\n"
            "2025-01-10,Negative amount,-50,expense,Food\n"
            "2025-01-10,,200,expense,Food\n"
            f"{future_date},Future movie,300,expense,Entertainment\n"
            "2025-01-10,Invalid Category,100,expense,NotACategory\n"
        )
        buf = BytesIO(csv_content.encode("utf-8"))
        result = parse_and_validate_file(buf, filename="mixed.csv", db_path=self.db)

        self.assertEqual(result["total_rows"], 5)
        self.assertEqual(result["valid_count"], 1)
        self.assertEqual(result["invalid_count"], 4)
        self.assertEqual(len(result["rows_to_import"]), 1)
        self.assertEqual(result["rows_to_import"][0]["description"], "Valid Dinner")

        # Ensure only the valid row imports
        database.add_transactions_batch(result["rows_to_import"], db_path=self.db)
        saved = database.get_transactions(self.db)
        self.assertEqual(len(saved), 1)

    def test_duplicate_detection_in_file_and_database(self):
        # 1. Add a transaction already into the database
        cleaned, _ = validate_transaction(date(2025, 1, 10), "Pizza lunch", "500", "expense", "Food")
        database.add_transaction(cleaned, db_path=self.db)

        # 2. Upload CSV with:
        #    Row 1: matches database (duplicate in DB)
        #    Row 2: fresh row (valid)
        #    Row 3: fresh row identical to Row 2 (duplicate in file)
        csv_content = (
            "Date,Description,Amount,Type,Category\n"
            "2025-01-10,Pizza lunch,500,expense,Food\n"
            "2025-01-11,Train ticket,150,expense,Travel\n"
            "2025-01-11,Train ticket,150,expense,Travel\n"
        )
        buf = BytesIO(csv_content.encode("utf-8"))

        # Default skip_duplicates=True
        result = parse_and_validate_file(buf, filename="dups.csv", db_path=self.db, skip_duplicates=True)
        self.assertEqual(result["total_rows"], 3)
        self.assertEqual(result["duplicate_count"], 2)
        self.assertEqual(len(result["rows_to_import"]), 1)
        self.assertEqual(result["rows_to_import"][0]["description"], "Train ticket")

        reasons = [d["reason"] for d in result["duplicate_rows"]]
        self.assertIn("Already exists in database", reasons)
        self.assertIn("Duplicate row within file", reasons)

    def test_database_batch_rollback_on_failure(self):
        # When an invalid row violates SQLite table constraints, executemany must rollback everything
        good_txn = {
            "date": date(2025, 1, 10),
            "description": "Good row",
            "amount": 100.0,
            "type": "expense",
            "category": "Food",
        }
        bad_txn = {
            "date": date(2025, 1, 10),
            "description": "Bad row",
            "amount": -50.0,  # Fails SQLite CHECK (amount > 0)
            "type": "expense",
            "category": "Food",
        }

        # Attempt batch insertion with mixed good and bad transactions
        with self.assertRaises(sqlite3.IntegrityError):
            database.add_transactions_batch([good_txn, bad_txn], db_path=self.db)

        # Database must still be empty because the batch rolled back atomically
        saved = database.get_transactions(self.db)
        self.assertEqual(len(saved), 0)

    def test_reject_legacy_xls_and_unsupported_formats(self):
        with self.assertRaises(ImportValidationError) as ctx:
            read_uploaded_file(BytesIO(b"dummy"), filename="statement.xls")
        self.assertIn("Legacy Excel (.xls) files are not supported", str(ctx.exception))

        with self.assertRaises(ImportValidationError) as ctx2:
            read_uploaded_file(BytesIO(b"dummy"), filename="statement.pdf")
        self.assertIn("Unsupported file format", str(ctx2.exception))

    def test_missing_columns_rejected_clearly(self):
        csv_content = "Date,Amount\n2025-01-01,100\n"
        buf = BytesIO(csv_content.encode("utf-8"))
        with self.assertRaises(ImportValidationError) as ctx:
            parse_and_validate_file(buf, filename="missing.csv", db_path=self.db)
        self.assertIn("Missing required columns", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
