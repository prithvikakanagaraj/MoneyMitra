"""Tests for src/validation.py - invalid and empty inputs must be rejected clearly."""
import unittest
from datetime import date, timedelta

from src.validation import validate_transaction

GOOD_DATE = date(2025, 1, 15)


class ValidationTests(unittest.TestCase):
    def test_valid_expense_is_accepted_and_cleaned(self):
        cleaned, errors = validate_transaction(GOOD_DATE, "  Lunch   at   cafe ", "250.5", "expense", "food")
        self.assertEqual(errors, [])
        self.assertEqual(cleaned["description"], "Lunch at cafe")  # spaces tidied
        self.assertEqual(str(cleaned["amount"]), "250.50")
        self.assertEqual(cleaned["category"], "Food")              # canonical capitalisation

    def test_valid_income_is_accepted(self):
        cleaned, errors = validate_transaction(GOOD_DATE, "Monthly salary", "50000", "income", "Salary")
        self.assertEqual(errors, [])
        self.assertEqual(cleaned["type"], "income")

    def test_commas_and_currency_symbol_in_amount_are_accepted(self):
        cleaned, errors = validate_transaction(GOOD_DATE, "Laptop", "₹1,25,000.00", "expense", "Shopping")
        self.assertEqual(errors, [])
        self.assertEqual(str(cleaned["amount"]), "125000.00")

    def test_empty_description_rejected(self):
        for bad in ["", "   ", None]:
            cleaned, errors = validate_transaction(GOOD_DATE, bad, "10", "expense", "Food")
            self.assertIsNone(cleaned)
            self.assertIn("Description is required.", errors)

    def test_description_too_long_rejected(self):
        _, errors = validate_transaction(GOOD_DATE, "x" * 201, "10", "expense", "Food")
        self.assertTrue(any("too long" in e for e in errors))

    def test_bad_amounts_rejected(self):
        for bad in ["", "   ", None, "abc", "12abc", "NaN", "Infinity", "-5", "0", "0.00", "10.555", "99999999999"]:
            cleaned, errors = validate_transaction(GOOD_DATE, "Test", bad, "expense", "Food")
            self.assertIsNone(cleaned, f"amount {bad!r} should be rejected")
            self.assertTrue(errors, f"amount {bad!r} should give an error message")

    def test_future_date_rejected(self):
        tomorrow = date.today() + timedelta(days=1)
        _, errors = validate_transaction(tomorrow, "Test", "10", "expense", "Food")
        self.assertIn("Date cannot be in the future.", errors)

    def test_very_old_date_rejected(self):
        _, errors = validate_transaction(date(1990, 1, 1), "Test", "10", "expense", "Food")
        self.assertTrue(any("before" in e for e in errors))

    def test_missing_or_malformed_date_rejected(self):
        for bad in [None, "", "15/01/2025", "not a date"]:
            cleaned, errors = validate_transaction(bad, "Test", "10", "expense", "Food")
            self.assertIsNone(cleaned)
            self.assertTrue(errors)

    def test_iso_date_string_accepted(self):
        cleaned, errors = validate_transaction("2025-03-09", "Test", "10", "expense", "Food")
        self.assertEqual(errors, [])
        self.assertEqual(cleaned["date"], date(2025, 3, 9))

    def test_invalid_type_rejected(self):
        _, errors = validate_transaction(GOOD_DATE, "Test", "10", "refund", "Food")
        self.assertTrue(any("income" in e and "expense" in e for e in errors))

    def test_category_must_match_type(self):
        _, errors = validate_transaction(GOOD_DATE, "Test", "10", "expense", "Salary")
        self.assertTrue(any("not a valid expense category" in e for e in errors))
        _, errors = validate_transaction(GOOD_DATE, "Test", "10", "income", "Food")
        self.assertTrue(any("not a valid income category" in e for e in errors))

    def test_empty_category_rejected(self):
        _, errors = validate_transaction(GOOD_DATE, "Test", "10", "expense", "")
        self.assertIn("Please choose a category.", errors)

    def test_all_errors_reported_together(self):
        cleaned, errors = validate_transaction(None, "", "abc", "nonsense", "")
        self.assertIsNone(cleaned)
        self.assertGreaterEqual(len(errors), 4)


if __name__ == "__main__":
    unittest.main()
