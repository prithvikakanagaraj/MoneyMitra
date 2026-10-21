"""
test_chat_page.py - Unit tests for the AI Finance Chat page processing logic.

Uses mocked services to ensure:
- Zero real API calls are executed.
- Zero network requests are made.
- Chat state and message transformations are tested accurately.
"""
import importlib
import unittest
from unittest.mock import MagicMock

# Import the pure message processing logic from the chat page using importlib (due to numeric prefix 3_)
_chat_module = importlib.import_module("pages.3_AI_Finance_Chat")
process_user_message = _chat_module.process_user_message



class ChatPageLogicTests(unittest.TestCase):
    def test_process_user_message_success(self):
        # Mock service function returning a successful response
        mock_service = MagicMock(return_value={
            "success": True,
            "response": "Your total income is ₹50,000.00.",
            "error_type": None,
        })

        existing_chat = [
            {"role": "user", "content": "Hello", "is_error": False},
            {"role": "assistant", "content": "Hi there!", "is_error": False},
        ]

        result = process_user_message(
            prompt="What is my total income?",
            chat_messages=existing_chat,
            service_fn=mock_service,
        )

        self.assertEqual(result["role"], "assistant")
        self.assertEqual(result["content"], "Your total income is ₹50,000.00.")
        self.assertFalse(result["is_error"])

        # Check call arguments
        mock_service.assert_called_once()
        kwargs = mock_service.call_args.kwargs
        self.assertEqual(kwargs["prompt"], "What is my total income?")
        self.assertEqual(len(kwargs["conversation_history"]), 2)

    def test_process_user_message_error(self):
        # Mock service returning an error (e.g. quota exceeded)
        mock_service = MagicMock(return_value={
            "success": False,
            "response": "The Gemini API request limit was exceeded.",
            "error_type": "quota_exceeded",
        })

        result = process_user_message(
            prompt="Summarize my budget",
            chat_messages=[],
            service_fn=mock_service,
        )

        self.assertEqual(result["role"], "assistant")
        self.assertTrue(result["is_error"])
        self.assertIn("❌ The Gemini API request limit was exceeded.", result["content"])

    def test_process_user_message_filters_out_previous_errors(self):
        # When chat history has an error message, it should NOT be passed to Gemini
        mock_service = MagicMock(return_value={
            "success": True,
            "response": "Understood.",
            "error_type": None,
        })

        existing_chat_with_error = [
            {"role": "user", "content": "First question", "is_error": False},
            {"role": "assistant", "content": "❌ Network timeout", "is_error": True},
            {"role": "user", "content": "Second question", "is_error": False},
            {"role": "assistant", "content": "Here is the answer", "is_error": False},
        ]

        result = process_user_message(
            prompt="Third question",
            chat_messages=existing_chat_with_error,
            service_fn=mock_service,
        )

        self.assertTrue(result["role"] == "assistant")
        self.assertFalse(result["is_error"])

        # Passed history should contain only the 3 non-error messages
        kwargs = mock_service.call_args.kwargs
        passed_history = kwargs["conversation_history"]
        self.assertEqual(len(passed_history), 3)
        for msg in passed_history:
            self.assertNotIn("❌", msg["content"])


if __name__ == "__main__":
    unittest.main()
