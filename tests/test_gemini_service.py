"""
test_gemini_service.py - Unit tests for Gemini service layer using mocks.

Guarantees:
- Tests do NOT make real external API calls.
- Tests do NOT consume API quota.
- Tests do NOT touch real financial records.
"""
from datetime import date
import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

from src import config
from src.gemini_service import (
    ask_finance_assistant,
    build_financial_context,
    get_gemini_client,
    sanitize_description,
    sanitize_error_message,
)


class GeminiServiceTests(unittest.TestCase):
    def setUp(self):
        # Create a sample DataFrame matching database.get_transactions() schema
        self.sample_df = pd.DataFrame([
            {
                "id": 1,
                "date": pd.to_datetime("2025-01-10"),
                "description": "Monthly Salary from employer",
                "amount": 50000.00,
                "type": "income",
                "category": "Salary",
            },
            {
                "id": 2,
                "date": pd.to_datetime("2025-01-12"),
                "description": "Supermarket groceries and snacks",
                "amount": 3500.00,
                "type": "expense",
                "category": "Food",
            },
            {
                "id": 3,
                "date": pd.to_datetime("2025-01-15"),
                "description": "Electricity and internet bill",
                "amount": 1500.00,
                "type": "expense",
                "category": "Bills",
            },
        ])

    def test_sanitize_description(self):
        # Normal description
        self.assertEqual(sanitize_description("Lunch with friends"), "Lunch with friends")
        # Collapses spaces
        self.assertEqual(sanitize_description("  Coffee    and bagels  "), "Coffee and bagels")
        # Masks long digit sequences (e.g. account numbers)
        self.assertEqual(
            sanitize_description("Transfer to 123456789012 bank"),
            "Transfer to [REDACTED_NUM] bank",
        )
        # Truncates descriptions exceeding max_chars
        long_desc = "A" * 60
        sanitized = sanitize_description(long_desc, max_chars=40)
        self.assertEqual(len(sanitized), 40)
        self.assertTrue(sanitized.endswith("..."))

    def test_build_financial_context_populated(self):
        context = build_financial_context(df=self.sample_df)
        # Verifies deterministic figures are present
        self.assertIn("Total Income: ₹50,000.00", context)
        self.assertIn("Total Expenses: ₹5,000.00", context)
        self.assertIn("Net Balance / Cash Flow: ₹45,000.00", context)
        self.assertIn("Food: ₹3,500.00 (70.0%)", context)
        self.assertIn("Bills: ₹1,500.00 (30.0%)", context)
        self.assertIn("2025-01", context)
        # Verifies private metadata (like internal IDs or paths) is absent
        self.assertNotIn("finance.db", context)
        self.assertNotIn("'id': 1", context)

    def test_build_financial_context_empty(self):
        empty_df = pd.DataFrame(columns=["id", "date", "description", "amount", "type", "category"])
        context = build_financial_context(df=empty_df)
        self.assertIn("Total transactions recorded: 0", context)
        self.assertIn("database is currently empty", context)

    def test_sanitize_error_message(self):
        secret = "secret-test-key-12345"
        raw_error = f"Request failed with key: {secret} at url https://example.com"
        cleaned = sanitize_error_message(raw_error, secret_key=secret)
        self.assertNotIn(secret, cleaned)
        self.assertIn("[REDACTED_API_KEY]", cleaned)

        # Google key regex pattern test
        google_key = "AIzaSyD-TEST-FAKE-KEY-ABC1234567890"
        err_with_google_key = f"400 Bad Request for {google_key}"
        cleaned_google = sanitize_error_message(err_with_google_key)
        self.assertNotIn(google_key, cleaned_google)
        self.assertIn("[REDACTED_API_KEY]", cleaned_google)

    def test_get_gemini_client_missing_key(self):
        client, err = get_gemini_client(api_key=None)
        # When api_key is None and config.GEMINI_API_KEY is patched out
        with patch.object(config, "GEMINI_API_KEY", None):
            client, err = get_gemini_client()
            self.assertIsNone(client)
            self.assertIn("not configured", err)

    def test_ask_finance_assistant_empty_prompt(self):
        res = ask_finance_assistant(prompt="   ")
        self.assertFalse(res["success"])
        self.assertEqual(res["error_type"], "empty_prompt")

    def test_ask_finance_assistant_missing_key(self):
        with patch.object(config, "GEMINI_API_KEY", None):
            res = ask_finance_assistant(prompt="How much did I spend?")
            self.assertFalse(res["success"])
            self.assertEqual(res["error_type"], "missing_key")
            self.assertIn("not configured", res["response"])

    def test_ask_finance_assistant_successful_mock(self):
        # Create a mock Gemini client and response
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "You spent ₹5,000.00 on Food and Bills this month."
        mock_client.models.generate_content.return_value = mock_response

        res = ask_finance_assistant(
            prompt="What are my expenses?",
            df=self.sample_df,
            client=mock_client,
            model="gemini-2.5-flash",
        )

        self.assertTrue(res["success"])
        self.assertEqual(res["response"], "You spent ₹5,000.00 on Food and Bills this month.")
        self.assertIsNone(res["error_type"])

        # Verify client.models.generate_content was called
        mock_client.models.generate_content.assert_called_once()
        call_kwargs = mock_client.models.generate_content.call_args.kwargs
        self.assertEqual(call_kwargs["model"], "gemini-2.5-flash")
        # Ensure system instruction and temperature were set
        self.assertEqual(call_kwargs["config"].temperature, 0.2)
        self.assertIn("FACTUAL ACCURACY", call_kwargs["config"].system_instruction)

    def test_ask_finance_assistant_quota_error(self):
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception("429 ResourceExhausted: Quota exceeded")

        res = ask_finance_assistant(
            prompt="Tell me my balance",
            df=self.sample_df,
            client=mock_client,
        )

        self.assertFalse(res["success"])
        self.assertEqual(res["error_type"], "quota_exceeded")
        self.assertIn("quota was exceeded", res["response"])

    def test_ask_finance_assistant_auth_error(self):
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception("403 PermissionDenied: Invalid API key")

        res = ask_finance_assistant(
            prompt="Tell me my balance",
            df=self.sample_df,
            client=mock_client,
        )

        self.assertFalse(res["success"])
        self.assertEqual(res["error_type"], "auth_error")
        self.assertIn("Authentication failed", res["response"])

    def test_ask_finance_assistant_network_error(self):
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception("Connection timeout while contacting server")

        res = ask_finance_assistant(
            prompt="Tell me my balance",
            df=self.sample_df,
            client=mock_client,
        )

        self.assertFalse(res["success"])
        self.assertEqual(res["error_type"], "network_error")
        self.assertIn("verify your internet connection", res["response"])

    def test_ask_finance_assistant_with_conversation_history(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "You spent most on Food."
        mock_client.models.generate_content.return_value = mock_response

        history = [
            {"role": "user", "content": "Hello!"},
            {"role": "assistant", "content": "Hi! How can I help with your finances?"},
        ]

        res = ask_finance_assistant(
            prompt="What is my biggest expense?",
            conversation_history=history,
            df=self.sample_df,
            client=mock_client,
        )

        self.assertTrue(res["success"])
        call_kwargs = mock_client.models.generate_content.call_args.kwargs
        contents = call_kwargs["contents"]
        # Expected: 2 history turns + 1 latest turn with context = 3 contents
        self.assertEqual(len(contents), 3)
        self.assertEqual(contents[0].role, "user")
        self.assertEqual(contents[1].role, "model")
        self.assertEqual(contents[2].role, "user")
        self.assertIn("What is my biggest expense?", contents[2].parts[0].text)


if __name__ == "__main__":
    unittest.main()
