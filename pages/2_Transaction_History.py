
"""Transaction History page: full table with search, filters and delete."""

import streamlit as st

from src import calculations as calc
from src import config, database, ui


ui.setup_page("Transaction History", "📜")

st.title("📜 Transaction History")

# Get the authenticated user's ID.
user_id = st.session_state["user_id"]

if "history_flash" in st.session_state:
    st.success(st.session_state.pop("history_flash"))

# Retrieve only this user's transactions.
df = database.get_transactions(user_id=user_id)

if df.empty:
    st.info("No transactions yet.")
    st.page_link(
        "pages/1_Add_Transaction.py",
        label="Add a transaction",
        icon="➕",
    )
    st.stop()


# ---- Filters -------------------------------------------------------

with st.container(border=True):
    f1, f2, f3 = st.columns([2, 1, 1])

    search = f1.text_input(
        "Search description",
        placeholder="e.g. pizza",
    )

    types = f2.multiselect(
        "Type",
        config.TRANSACTION_TYPES,
        format_func=str.capitalize,
        help="Leave empty to show both.",
    )

    categories = f3.multiselect(
        "Category",
        sorted(df["category"].unique()),
        help="Leave empty to show all categories.",
    )

    min_day = df["date"].min().date()
    max_day = df["date"].max().date()

    date_range = st.date_input(
        "Date range",
        value=(min_day, max_day),
        min_value=min_day,
        max_value=max_day,
    )


# date_input can return a one-item tuple while the user
# is still selecting the second date.

if isinstance(date_range, (tuple, list)):
    start = date_range[0] if len(date_range) >= 1 else min_day
    end = date_range[1] if len(date_range) == 2 else max_day
else:
    start, end = date_range, date_range


filtered = calc.filter_transactions(
    df,
    search,
    types,
    categories,
    start,
    end,
)


# ---- Results -------------------------------------------------------

st.write(
    f"Showing **{len(filtered)}** of **{len(df)}** transactions."
)

if filtered.empty:
    st.warning(
        "No transactions match these filters. "
        "Try clearing the search or widening the date range."
    )

else:
    totals = calc.compute_summary(filtered)

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Income (filtered)",
        calc.format_currency(totals["total_income"]),
    )

    c2.metric(
        "Expenses (filtered)",
        calc.format_currency(totals["total_expense"]),
    )

    c3.metric(
        "Net (filtered)",
        calc.format_currency(totals["net_cash_flow"]),
    )

    ui.show_transactions_table(filtered)

    # ---- Delete ----------------------------------------------------
    # The database deletion is scoped to the logged-in user's ID.

    with st.expander("Delete a transaction"):
        labels = {
            int(r.id): (
                f"#{r.id} | {r.date:%d %b %Y} | "
                f"{r.description} | "
                f"{config.CURRENCY_SYMBOL}{r.amount:,.2f} "
                f"({r.type})"
            )
            for r in filtered.itertuples()
        }

        chosen = st.selectbox(
            "Choose a transaction",
            list(labels),
            format_func=labels.get,
        )

        confirm = st.checkbox(
            "Yes, permanently delete this transaction"
        )

        if st.button("Delete", disabled=not confirm):
            deleted = database.delete_transaction(
                chosen,
                user_id=user_id,
            )

            if deleted:
                st.session_state.history_flash = (
                    f"Deleted transaction #{chosen}."
                )
            else:
                st.session_state.history_flash = (
                    "The transaction could not be deleted. "
                    "It may no longer exist in your account."
                )

            st.rerun()
