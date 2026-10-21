
"""Add Transaction page: the manual entry form."""

from datetime import date

import streamlit as st

from src import config, database, ui
from src.validation import validate_transaction


ui.setup_page("Add Transaction", "➕")

st.title("➕ Add a Transaction")

# Get the authenticated user's ID.
user_id = st.session_state["user_id"]

# --- Form version ---
# Changing widget keys after a successful save clears the form.
# Validation errors leave the user's entries untouched.

if "form_version" not in st.session_state:
    st.session_state.form_version = 0

v = st.session_state.form_version

if "flash_message" in st.session_state:
    st.success(st.session_state.pop("flash_message"))

# Select the transaction type outside the form so the category
# options update when the transaction type changes.

txn_type = st.radio(
    "Transaction type",
    config.TRANSACTION_TYPES,
    format_func=str.capitalize,
    horizontal=True,
)

with st.form("add_transaction_form"):
    col1, col2 = st.columns(2)

    with col1:
        txn_date = st.date_input(
            "Date",
            value=date.today(),
            min_value=config.MIN_DATE,
            max_value=date.today(),
            key=f"date_{v}",
        )

        amount = st.text_input(
            f"Amount ({config.CURRENCY_SYMBOL})",
            placeholder="e.g. 250 or 99.50",
            key=f"amount_{v}",
        )

    with col2:
        category = st.selectbox(
            "Category",
            config.CATEGORIES_BY_TYPE[txn_type],
            key=f"category_{v}_{txn_type}",
        )

        description = st.text_input(
            "Description",
            placeholder="e.g. Lunch with friends",
            key=f"description_{v}",
        )

    submitted = st.form_submit_button(
        "Save transaction",
        type="primary",
    )

# --- Save transaction ---

if submitted:
    cleaned, errors = validate_transaction(
        txn_date,
        description,
        amount,
        txn_type,
        category,
    )

    if errors:
        for message in errors:
            st.error(message)

    else:
        # IMPORTANT: associate the transaction with the logged-in user.
        database.add_transaction(
            cleaned,
            user_id=user_id,
        )

        st.session_state.flash_message = (
            f"Saved {cleaned['type']}: {cleaned['description']} "
            f"({config.CURRENCY_SYMBOL}{cleaned['amount']:,.2f}, "
            f"{cleaned['category']}, "
            f"{cleaned['date']:%d %b %Y})"
        )

        st.session_state.form_version += 1
        st.rerun()


# --- Recent transactions ---
# Display only transactions belonging to the logged-in user.

st.subheader("Your Most Recent Transactions")

recent = database.get_transactions(
    user_id=user_id,
).head(5)

if recent.empty:
    st.caption("Nothing saved yet. Add your first transaction above.")
else:
    ui.show_transactions_table(recent)
