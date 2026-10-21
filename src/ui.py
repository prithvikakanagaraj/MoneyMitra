
"""
ui.py - shared helpers for MoneyMitra's Streamlit pages.
Only this file and files in pages/ import streamlit.
"""

import streamlit as st

from src import config, database


def setup_page(title, icon):
    """
    Configure the page, initialize the database, and protect
    the page behind authentication.
    """
    st.set_page_config(
        page_title=f"{title} | {config.APP_TITLE}",
        page_icon=icon,
        layout="wide",
    )

    database.init_db()

    # Authentication will be enforced once the login flow is connected.
    if not st.session_state.get("authenticated", False):
        st.warning("Please log in to access MoneyMitra.")
        st.info("The login and registration screens will be connected next.")
        st.stop()


def show_transactions_table(df):
    """Show a transactions DataFrame as a nicely formatted table."""

    table = df[
        ["id", "date", "description", "type", "category", "amount"]
    ].copy()

    table["type"] = table["type"].str.capitalize()

    st.dataframe(
        table,
        hide_index=True,
        column_config={
            "id": st.column_config.NumberColumn(
                "ID",
                width="small",
            ),
            "date": st.column_config.DateColumn(
                "Date",
                format="DD MMM YYYY",
            ),
            "description": st.column_config.TextColumn(
                "Description",
                width="large",
            ),
            "type": st.column_config.TextColumn(
                "Type",
                width="small",
            ),
            "category": st.column_config.TextColumn("Category"),
            "amount": st.column_config.NumberColumn(
                f"Amount ({config.CURRENCY_SYMBOL})",
                format=f"{config.CURRENCY_SYMBOL}%.2f",
            ),
        },
    )
