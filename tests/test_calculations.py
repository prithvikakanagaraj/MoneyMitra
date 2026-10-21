"""Tests for src/calculations.py - the numbers on the dashboard must be exactly right."""
import os
import tempfile
import unittest
from datetime import date

import pandas as pd

from src import calculations as calc
from src import database
from src.validation import validate_transaction


def add(db, d, description, amount, txn_type, category):
    cleaned, errors = validate_transaction(d, description, amount, txn_type, category)
    assert not errors, errors
    database.add_transaction(cleaned, db)


class CalculationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "test.db")
        database.init_db(self.db)
        # Known data, so every expected number below can be checked by hand:
        add(self.db, date(2025, 1, 5),  "Salary Jan",   "50000",   "income",  "Salary")
        add(self.db, date(2025, 1, 10), "Groceries",    "1200.50", "expense", "Food")
        add(self.db, date(2025, 1, 20), "Bus pass",     "799.50",  "expense", "Travel")
        add(self.db, date(2025, 2, 5),  "Freelance gig", "8000",   "income",  "Freelance")
        add(self.db, date(2025, 2, 8),  "Pizza night",  "500",     "expense", "Food")
        self.df = database.get_transactions(self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def test_summary_cards(self):
        s = calc.compute_summary(self.df)
        self.assertEqual(s["total_income"], 58000.00)
        self.assertEqual(s["total_expense"], 2500.00)     # 1200.50 + 799.50 + 500
        self.assertEqual(s["net_cash_flow"], 55500.00)
        self.assertEqual(s["transaction_count"], 5)

    def test_summary_of_empty_data_is_zero(self):
        empty = self.df.iloc[0:0]  # same columns, zero rows
        s = calc.compute_summary(empty)
        self.assertEqual((s["total_income"], s["total_expense"], s["net_cash_flow"], s["transaction_count"]), (0, 0, 0, 0))

    def test_floating_point_noise_is_removed(self):
        db = os.path.join(self.tmp.name, "float.db")
        database.init_db(db)
        add(db, date(2025, 1, 1), "a", "0.10", "expense", "Other")
        add(db, date(2025, 1, 1), "b", "0.20", "expense", "Other")
        self.assertEqual(calc.compute_summary(database.get_transactions(db))["total_expense"], 0.30)

    def test_net_cash_flow_can_be_negative(self):
        db = os.path.join(self.tmp.name, "neg.db")
        database.init_db(db)
        add(db, date(2025, 1, 1), "Big buy", "900", "expense", "Shopping")
        add(db, date(2025, 1, 2), "Gift", "100", "income", "Gift")
        s = calc.compute_summary(database.get_transactions(db))
        self.assertEqual(s["net_cash_flow"], -800.00)
        self.assertEqual(calc.format_currency(s["net_cash_flow"]), "-₹800.00")

    def test_monthly_summary_matches_database(self):
        m = calc.monthly_summary(self.df)
        self.assertEqual(list(m["month"]), ["2025-01", "2025-02"])
        self.assertEqual(list(m["income"]), [50000.0, 8000.0])
        self.assertEqual(list(m["expense"]), [2000.0, 500.0])

    def test_monthly_summary_fills_missing_type_with_zero(self):
        db = os.path.join(self.tmp.name, "only_exp.db")
        database.init_db(db)
        add(db, date(2025, 3, 1), "Only expense", "75", "expense", "Food")
        m = calc.monthly_summary(database.get_transactions(db))
        self.assertEqual(list(m["income"]), [0.0])
        self.assertEqual(list(m["expense"]), [75.0])

    def test_category_spending_counts_expenses_only_and_sorts(self):
        c = calc.category_spending(self.df)
        self.assertEqual(list(c["category"]), ["Food", "Travel"])    # Salary/Freelance excluded
        self.assertEqual(list(c["amount"]), [1700.50, 799.50])

    def test_empty_chart_data_is_handled(self):
        self.assertTrue(calc.monthly_summary(self.df.iloc[0:0]).empty)
        self.assertTrue(calc.category_spending(self.df.iloc[0:0]).empty)

    def test_search_is_case_insensitive_and_literal(self):
        self.assertEqual(list(calc.filter_transactions(self.df, search="PIZZA")["description"]), ["Pizza night"])
        # characters like '(' or '*' must not crash (they are treated as plain text)
        self.assertTrue(calc.filter_transactions(self.df, search="(*").empty)

    def test_filter_by_type_category_and_dates(self):
        self.assertEqual(len(calc.filter_transactions(self.df, types=["income"])), 2)
        self.assertEqual(len(calc.filter_transactions(self.df, categories=["Food"])), 2)
        jan = calc.filter_transactions(self.df, start_date=date(2025, 1, 1), end_date=date(2025, 1, 31))
        self.assertEqual(len(jan), 3)
        # end date is inclusive
        self.assertEqual(len(calc.filter_transactions(self.df, start_date=date(2025, 1, 20), end_date=date(2025, 1, 20))), 1)

    def test_filters_combine_with_and(self):
        r = calc.filter_transactions(self.df, search="pizza", types=["expense"], categories=["Food"])
        self.assertEqual(len(r), 1)
        self.assertTrue(calc.filter_transactions(self.df, search="pizza", types=["income"]).empty)

    def test_no_filters_returns_everything(self):
        self.assertEqual(len(calc.filter_transactions(self.df)), 5)

    def test_format_currency(self):
        self.assertEqual(calc.format_currency(1234.5), "₹1,234.50")
        self.assertEqual(calc.format_currency(0), "₹0.00")


if __name__ == "__main__":
    unittest.main()
