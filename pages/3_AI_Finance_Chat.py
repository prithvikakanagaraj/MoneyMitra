
"""
pages/3_AI_Finance_Chat.py

MoneyMitra's interactive AI Finance Chat page.

Features:
- Uses the authenticated user's ID.
- Sends user-specific financial queries to the Gemini service.
- Maintains conversation history within the current session.
- Supports clearing the conversation.
- Displays friendly error messages.
"""

from typing import Callable, Dict, List, Optional

import streamlit as st

from src import config, ui
from src.gemini_service import ask_finance_assistant


def process_user_message(
    prompt: str,
    chat_messages: List[Dict[str, str]],
    service_fn: Callable = ask_finance_assistant,
    user_id: Optional[int] = None,
) -> Dict[str, str]:
    """
    Format conversation history, call the Gemini service for the
    authenticated user, and return the assistant's response.

    This helper is separated from the UI to simplify unit testing.
    """

    if user_id is None and service_fn is ask_finance_assistant:
        return {
        "role": "assistant",
        "content": (
            "Please log in to use your personal finance assistant."
        ),
        "is_error": True,
    }

    history = [
        {
            "role": message["role"],
            "content": message["content"],
        }
        for message in chat_messages
        if not message.get("is_error")
    ]

    try:
        result = service_fn(
            prompt=prompt,
            conversation_history=history,
            user_id=user_id,
        )

    except Exception:
        return {
            "role": "assistant",
            "content": (
                "❌ Something went wrong while contacting your "
                "finance assistant. Please try again."
            ),
            "is_error": True,
        }

    if result.get("success"):
        return {
            "role": "assistant",
            "content": result.get("response", ""),
            "is_error": False,
        }

    error_message = result.get(
        "response",
        "An error occurred while communicating with Gemini.",
    )

    return {
        "role": "assistant",
        "content": f"❌ {error_message}",
        "is_error": True,
    }


def render_chat_page() -> None:
    """Render the authenticated MoneyMitra AI chat page."""

    ui.setup_page("AI Finance Chat", "🤖")

    user_id = st.session_state.get("user_id")

    # Extra protection: never display the personal finance chat
    # without an authenticated user.
    if user_id is None:
        st.warning("Please log in to access your finance assistant.")
        st.stop()

    st.title("🤖 MoneyMitra AI Finance Assistant")

    st.caption(
        "Ask questions about your income, expenses, spending habits, "
        "transactions, and financial summaries."
    )

    st.info(
        "Your assistant is designed to answer using your own "
        "financial transaction data."
    )

    # Initialize chat history for this Streamlit session.
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    # Keep conversations separate if the authenticated user changes
    # within the same Streamlit session.
    previous_chat_user_id = st.session_state.get("chat_user_id")

    if previous_chat_user_id != user_id:
        st.session_state.chat_messages = []
        st.session_state.chat_user_id = user_id

    # Chat controls.
    control_col, _ = st.columns([1, 4])

    with control_col:
        if st.button(
            "🗑️ Clear conversation",
            use_container_width=True,
        ):
            st.session_state.chat_messages = []
            st.rerun()

    # Check whether the Gemini API key is configured.
    api_key = getattr(config, "GEMINI_API_KEY", None)

    if not api_key:
        st.warning(
            "The Gemini API key may not be configured. "
            "Check your MoneyMitra configuration before sending "
            "questions to the AI assistant."
        )

    # Display existing conversation.
    for message in st.session_state.chat_messages:
        role = message.get("role", "assistant")
        content = message.get("content", "")

        with st.chat_message(
            "assistant" if role == "assistant" else "user"
        ):
            st.markdown(content)

    # Input field for the user's next question.
    prompt = st.chat_input(
        "Ask MoneyMitra about your finances..."
    )

    if prompt and prompt.strip():
        prompt = prompt.strip()

        # Display the user's message immediately.
        st.session_state.chat_messages.append(
            {
                "role": "user",
                "content": prompt,
                "is_error": False,
            }
        )

        with st.chat_message("user"):
            st.markdown(prompt)

        # Generate the assistant's response.
        with st.chat_message("assistant"):
            with st.spinner(
                "MoneyMitra is analyzing your financial data..."
            ):
                response_message = process_user_message(
                    prompt=prompt,
                    chat_messages=st.session_state.chat_messages[:-1],
                    user_id=user_id,
                )

            st.markdown(response_message["content"])

        # Save the assistant's response to the current session.
        st.session_state.chat_messages.append(response_message)


if __name__ == "__main__":
    render_chat_page()
