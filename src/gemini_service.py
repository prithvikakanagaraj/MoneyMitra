
"""
gemini_service.py - Service layer for Google Gemini AI integration.

Responsibilities:
1. Initialize the Google Gen AI SDK client safely.
2. Build factual financial context using deterministic calculations.
3. Retrieve relevant transactions for the authenticated user.
4. Send financial questions to Gemini with accuracy guardrails.
5. Handle API, authentication, quota, and network errors.
"""

import os
import re
import time
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types

from src import calculations as calc
from src import config, database
from src.retrieval import search_transactions


# ============================================================
# 1. SYSTEM INSTRUCTIONS
# ============================================================

SYSTEM_INSTRUCTION = f"""
You are MoneyMitra, an intelligent and friendly personal finance
assistant.

Help users understand their income, expenses, spending trends,
transactions, and financial health.

CRITICAL RULES:

1. FACTUAL ACCURACY
   - Treat Python-calculated financial totals as authoritative.
   - Never invent transactions, dates, amounts, or financial totals.
   - Explain when the supplied information cannot answer a question.
   - Semantic search results are supporting records, not proof that
     every matching transaction is relevant.
   - Do not claim that a calculation was performed if it was not.

2. CURRENCY
   - Use the configured currency symbol: {config.CURRENCY_SYMBOL}
   - Format amounts clearly, for example:
     {config.CURRENCY_SYMBOL}1,250.00

3. PRIVACY
   - Never ask for passwords, bank account numbers, credit card
     details, or other sensitive personal credentials.
   - Use only the authenticated user's financial data supplied
     in the financial context.

4. FINANCIAL GUIDANCE
   - You may offer budgeting suggestions and spending observations.
   - You are not a certified financial planner.

5. RESPONSE STYLE
   - Answer the user's question directly.
   - Be concise, clear, friendly, and helpful.
   - Do not invent information when the database does not support
     the requested answer.
"""


# ============================================================
# 2. PRIVACY AND DESCRIPTION SANITIZATION
# ============================================================

def sanitize_description(
    description: str,
    max_chars: int = 40,
) -> str:
    """Sanitize transaction descriptions before sending them to Gemini."""

    if not description:
        return "Unspecified"

    cleaned = " ".join(str(description).strip().split())

    cleaned = re.sub(
        r"\b\d{8,}\b",
        "[REDACTED_NUM]",
        cleaned,
    )

    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars - 3] + "..."

    return cleaned


# ============================================================
# 3. BUILD FINANCIAL CONTEXT
# ============================================================

def build_financial_context(
    df: Optional[Any] = None,
    db_path: Optional[str] = None,
    max_recent_transactions: int = 5,
    user_id: Optional[int] = None,
) -> str:
    """
    Build authoritative financial context using Python calculations.

    When df is not provided, an authenticated user_id is required
    before reading transactions from the database.
    """

    if df is None:
        if user_id is None:
            return (
                "Financial context unavailable: "
                "an authenticated user is required."
            )

        try:
            user_id = int(user_id)

            if user_id < 1:
                raise ValueError("Invalid user ID.")

            df = database.get_transactions(
                db_path=db_path,
                user_id=user_id,
            )

        except (TypeError, ValueError):
            return (
                "Financial context unavailable: "
                "a valid authenticated user is required."
            )

        except Exception:
            return (
                "Financial context unavailable: "
                "could not read from the database."
            )

    if df is None or df.empty:
        return (
            "FINANCIAL DATABASE STATUS:\n"
            "- Total transactions recorded: 0.\n"
            "- The database is currently empty.\n"
            "- The user can add a transaction or import a spreadsheet."
        )

    # A. Summary metrics
    summary = calc.compute_summary(df)

    total_income = calc.format_currency(summary["total_income"])
    total_expenses = calc.format_currency(summary["total_expense"])
    net_cash_flow = calc.format_currency(summary["net_cash_flow"])

    context_lines = [
        "AUTHORITATIVE FINANCIAL CONTEXT:",
        "Financial totals below are calculated using Python.",
        f"- Total Transactions: {summary['transaction_count']}",
        f"- Total Income: {total_income}",
        f"- Total Expenses: {total_expenses}",
        f"- Net Balance / Cash Flow: {net_cash_flow}",
        "",
    ]

    # B. Spending by category
    category_df = calc.category_spending(df)

    if category_df is not None and not category_df.empty:
        context_lines.append("EXPENSE BREAKDOWN BY CATEGORY:")

        total_expense_value = summary["total_expense"]

        for _, row in category_df.iterrows():
            category = row.get("category", "Other")
            amount = float(row.get("amount", 0))

            percentage = (
                (amount / total_expense_value) * 100
                if total_expense_value > 0
                else 0
            )

            context_lines.append(
                f"- {category}: {calc.format_currency(amount)} "
                f"({percentage:.1f}%)"
            )

        context_lines.append("")

    # C. Monthly financial trends
    monthly_df = calc.monthly_summary(df)

    if monthly_df is not None and not monthly_df.empty:
        context_lines.append("MONTHLY SUMMARY - LATEST MONTHS:")

        for _, row in monthly_df.tail(6).iterrows():
            month = row.get("month", "Unknown")
            income = float(row.get("income", 0))
            expense = float(row.get("expense", 0))
            net = income - expense

            context_lines.append(
                f"- {month}: "
                f"Income {calc.format_currency(income)} | "
                f"Expenses {calc.format_currency(expense)} | "
                f"Net {calc.format_currency(net)}"
            )

        context_lines.append("")

    # D. Limited sample of recent transactions
    if max_recent_transactions > 0:
        recent_transactions = df.head(max_recent_transactions)

        if not recent_transactions.empty:
            context_lines.append("RECENT TRANSACTIONS SAMPLE:")

            for _, row in recent_transactions.iterrows():
                transaction_date = row.get("date", "Unknown")

                if hasattr(transaction_date, "strftime"):
                    transaction_date = transaction_date.strftime("%Y-%m-%d")
                else:
                    transaction_date = str(transaction_date)[:10]

                description = sanitize_description(
                    row.get("description", "")
                )

                amount = calc.format_currency(
                    float(row.get("amount", 0))
                )

                transaction_type = str(
                    row.get("type", "unknown")
                ).capitalize()

                category = row.get("category", "Other")

                context_lines.append(
                    f"- {transaction_date} | "
                    f"{description} | "
                    f"{transaction_type}: {amount} | "
                    f"Category: {category}"
                )

    return "\n".join(context_lines)


# ============================================================
# 4. INITIALIZE GEMINI CLIENT
# ============================================================

def get_gemini_client(
    api_key: Optional[str] = None,
) -> tuple[Optional[genai.Client], Optional[str]]:
    """Return a Gemini client and an optional initialization error."""

    key = api_key or config.GEMINI_API_KEY

    if not key or not str(key).strip():
        return (
            None,
            "Gemini API key is not configured. "
            "Please add GEMINI_API_KEY to your .env file.",
        )

    try:
        client = genai.Client(api_key=key.strip())
        return client, None

    except Exception as exc:
        sanitized_error = sanitize_error_message(str(exc), key)

        return (
            None,
            f"Could not initialize Gemini client: {sanitized_error}",
        )


# ============================================================
# 5. SANITIZE ERROR MESSAGES
# ============================================================

def sanitize_error_message(
    message: str,
    secret_key: Optional[str] = None,
) -> str:
    """Remove API keys from error messages."""

    if not message:
        return "Unknown error."

    sanitized = str(message)

    if secret_key and len(secret_key) > 4:
        sanitized = sanitized.replace(
            secret_key,
            "[REDACTED_API_KEY]",
        )

    sanitized = re.sub(
        r"AIza[0-9A-Za-z_-]{20,}",
        "[REDACTED_API_KEY]",
        sanitized,
    )

    return sanitized


# ============================================================
# 6. MAIN FINANCE ASSISTANT FUNCTION
# ============================================================

def ask_finance_assistant(
    prompt: str,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    df: Optional[Any] = None,
    db_path: Optional[str] = None,
    client: Optional[genai.Client] = None,
    model: Optional[str] = None,
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Query Gemini using financial information for the authenticated user.

    A user_id is mandatory for requests that use the database.
    A supplied DataFrame can be used for isolated tests.
    """

    user_query = str(prompt or "").strip()

    # A. Validate the prompt first so empty-prompt errors remain specific.
    if not user_query:
        return {
            "success": False,
            "response": "Please enter a question or request.",
            "error_type": "empty_prompt",
        }

    
    # B. Initialize Gemini and check API configuration.
    active_client = client

    if active_client is None:
        active_client, error_message = get_gemini_client()

        if active_client is None:
            return {
                "success": False,
                "response": error_message,
                "error_type": "missing_key",
            }

    # C. Validate authentication before accessing personal financial data.
    if user_id is None:
        # An explicitly supplied DataFrame is allowed for isolated tests.
        # Never query the database without authentication.
        if df is None:
            return {
                "success": False,
                "response": (
                    "Please log in to use your personal finance assistant."
                ),
                "error_type": "authentication_required",
            }
    else:
        try:
            user_id = int(user_id)
        except (TypeError, ValueError):
            return {
                "success": False,
                "response": "A valid authenticated user is required.",
                "error_type": "authentication_required",
            }

        if user_id < 1:
            return {
                "success": False,
                "response": "A valid authenticated user is required.",
                "error_type": "authentication_required",
            }

    active_client = client

    if active_client is None:
        active_client, error_message = get_gemini_client()

        if active_client is None:
            return {
                "success": False,
                "response": error_message,
                "error_type": "missing_key",
            }

    # D. Build financial context.
    financial_context = build_financial_context(
        df=df,
        db_path=db_path,
        user_id=user_id,
    )

    # E. Retrieve relevant transactions for this user.
    try:
        if user_id is None:
            # A DataFrame-only test does not authorize database retrieval.
            retrieved_transactions = []
        else:
            retrieved_transactions = search_transactions(
                user_query,
                top_k=5,
                user_id=user_id,
                db_path=db_path,
            )

    except Exception:
        # Retrieval failure should not crash the finance assistant.
        retrieved_transactions = []

    if retrieved_transactions:
        retrieval_lines = [
            "",
            "SEMANTICALLY RETRIEVED TRANSACTIONS:",
            (
                "These records were retrieved by semantic similarity "
                "and may be relevant to the question."
            ),
            (
                "Use the authoritative Python-calculated totals "
                "for financial summary figures."
            ),
        ]

        for transaction in retrieved_transactions:
            transaction_date = transaction.get("date", "Unknown date")

            description = sanitize_description(
                transaction.get("description", "")
            )

            category = transaction.get("category", "Other")

            transaction_type = str(
                transaction.get("type", "unknown")
            ).capitalize()

            try:
                amount = calc.format_currency(
                    float(transaction.get("amount", 0))
                )
            except (TypeError, ValueError):
                amount = "Unknown amount"

            retrieval_lines.append(
                f"- {transaction_date} | "
                f"{description} | "
                f"{transaction_type}: {amount} | "
                f"Category: {category}"
            )

        financial_context += "\n" + "\n".join(retrieval_lines)

    # F. Prepare the model conversation.
    model_name = model or config.GEMINI_MODEL or "gemini-2.5-flash"

    contents: List[types.Content] = []

    # Include prior messages, excluding any accidental empty content.
    if conversation_history:
        for turn in conversation_history:
            content_text = str(turn.get("content", "")).strip()

            if not content_text:
                continue

            role = (
                "user"
                if turn.get("role") == "user"
                else "model"
            )

            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=content_text)],
                )
            )

    # Supply financial context with the latest question.
    latest_question = (
        f"{financial_context}\n\n"
        f"USER QUESTION: {user_query}"
    )

    contents.append(
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=latest_question)],
        )
    )

    # G. Send request to Gemini.
    try:
        generation_config = types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=0.2,
        )

        max_retries = 3
        response = None

        for attempt in range(max_retries):
            try:
                response = active_client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=generation_config,
                )
                break

            except Exception as request_error:
                error_message = str(request_error).lower()

                temporary_error = any(
                    marker in error_message
                    for marker in (
                        "503",
                        "unavailable",
                        "overloaded",
                        "service unavailable",
                    )
                )

                if temporary_error and attempt < max_retries - 1:
                    time.sleep(2 ** (attempt + 1))
                    continue

                raise

        # H. Validate Gemini response.
        if not response or not response.text:
            return {
                "success": False,
                "response": (
                    "Gemini returned an empty response. "
                    "Please try rephrasing your question."
                ),
                "error_type": "empty_response",
            }

        return {
            "success": True,
            "response": response.text.strip(),
            "error_type": None,
        }

    # I. Handle Gemini errors.
    except Exception as exc:
        raw_message = str(exc)
        sanitized_message = sanitize_error_message(
            raw_message,
            config.GEMINI_API_KEY,
        )
        lower_message = raw_message.lower()

        if (
            "429" in lower_message
            or "quota" in lower_message
            or "resource_exhausted" in lower_message
        ):
            return {
                "success": False,
                "response": (
                    "The Gemini API request limit or quota "
                    "was exceeded. Please wait and try again."
                ),
                "error_type": "quota_exceeded",
            }

        if (
            "401" in lower_message
            or "403" in lower_message
            or "permission_denied" in lower_message
            or "invalid api key" in lower_message
        ):
            return {
                "success": False,
                "response": (
                    "Authentication failed. Please verify "
                    "that your GEMINI_API_KEY in .env is valid."
                ),
                "error_type": "auth_error",
            }

        if (
            "503" in lower_message
            or "unavailable" in lower_message
            or "overloaded" in lower_message
        ):
            return {
                "success": False,
                "response": (
                    "Gemini is temporarily busy, even after "
                    "retries. Please wait and try again."
                ),
                "error_type": "service_unavailable",
            }

        if any(
            marker in lower_message
            for marker in (
                "connection",
                "timeout",
                "nodename",
                "unreachable",
            )
        ):
            return {
                "success": False,
                "response": (
                    "Could not connect to Gemini. "
                    "Please verify your internet connection."
                ),
                "error_type": "network_error",
            }

        return {
            "success": False,
            "response": (
                "An error occurred while contacting Gemini: "
                f"{sanitized_message}"
            ),
            "error_type": "api_error",
        }