"""
calculations.py - ALL exact financial maths lives here (plain Python + pandas).

Why this matters for the project: in later phases the AI chatbot will EXPLAIN
numbers produced by these functions. It will never calculate them itself,
because language models can get arithmetic wrong.

Every function takes a DataFrame (from database.get_transactions()) and returns
simple values, so each one is easy to test.
"""
import pandas as pd

from src import config


def format_currency(amount):
    """1234.5 -> '₹1,234.50'   |   -80 -> '-₹80.00'"""
    sign = "-" if amount < 0 else ""
    return f"{sign}{config.CURRENCY_SYMBOL}{abs(amount):,.2f}"


def compute_summary(df):
    """Totals for the dashboard cards."""
    income = float(df.loc[df["type"] == "income", "amount"].sum())
    expense = float(df.loc[df["type"] == "expense", "amount"].sum())
    income, expense = round(income, 2), round(expense, 2)
    return {
        "total_income": income,
        "total_expense": expense,
        "net_cash_flow": round(income - expense, 2),
        "transaction_count": int(len(df)),
    }


def monthly_summary(df):
    """One row per month: columns month ('YYYY-MM'), income, expense."""
    if df.empty:
        return pd.DataFrame(columns=["month", "income", "expense"])
    monthly = (
        df.assign(month=df["date"].dt.strftime("%Y-%m"))
        .pivot_table(index="month", columns="type", values="amount", aggfunc="sum", fill_value=0)
        .reindex(columns=["income", "expense"], fill_value=0)
        .rename_axis(columns=None)
        .reset_index()
        .sort_values("month")
        .reset_index(drop=True)
    )
    monthly[["income", "expense"]] = monthly[["income", "expense"]].round(2)
    return monthly


def category_spending(df):
    """Total EXPENSES per category, biggest first. Columns: category, amount."""
    expenses = df[df["type"] == "expense"]
    if expenses.empty:
        return pd.DataFrame(columns=["category", "amount"])
    result = (
        expenses.groupby("category", as_index=False)["amount"].sum()
        .sort_values("amount", ascending=False)
        .reset_index(drop=True)
    )
    result["amount"] = result["amount"].round(2)
    return result


def filter_transactions(df, search="", types=None, categories=None, start_date=None, end_date=None):
    """
    Apply the filters from the Transaction History page.
    An empty / None filter means "don't filter on this".
    The end date is inclusive.
    """
    mask = pd.Series(True, index=df.index)
    if search and search.strip():
        mask &= df["description"].str.contains(search.strip(), case=False, regex=False, na=False)
    if types:
        mask &= df["type"].isin(types)
    if categories:
        mask &= df["category"].isin(categories)
    if start_date is not None:
        mask &= df["date"] >= pd.Timestamp(start_date)
    if end_date is not None:
        mask &= df["date"] <= pd.Timestamp(end_date)
    return df[mask]
