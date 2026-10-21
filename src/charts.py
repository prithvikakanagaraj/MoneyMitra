"""
charts.py - builds Plotly figures.

These functions only DRAW. The numbers come from calculations.py, which
computes them from the database - so the charts can never show made-up data.
"""
import plotly.express as px

from src import config

INCOME_COLOR = "#2E9E6B"
EXPENSE_COLOR = "#E5484D"


def monthly_chart(monthly_df):
    """Grouped bars: income vs expenses for each month."""
    long_df = monthly_df.melt(
        id_vars="month", value_vars=["income", "expense"],
        var_name="Type", value_name="Amount",
    )
    long_df["Type"] = long_df["Type"].str.capitalize()
    fig = px.bar(
        long_df, x="month", y="Amount", color="Type", barmode="group",
        color_discrete_map={"Income": INCOME_COLOR, "Expense": EXPENSE_COLOR},
        labels={"month": "Month", "Amount": f"Amount ({config.CURRENCY_SYMBOL})"},
    )
    fig.update_xaxes(type="category")  # keep "2025-01" as text, not a date axis
    fig.update_traces(hovertemplate="%{x}<br>%{y:,.2f}<extra></extra>")
    fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), legend_title_text="")
    return fig


def category_chart(category_df):
    """Donut chart: share of total spending per category."""
    fig = px.pie(category_df, names="category", values="amount", hole=0.5)
    fig.update_traces(
        textinfo="percent+label",
        hovertemplate="%{label}<br>" + config.CURRENCY_SYMBOL + "%{value:,.2f} (%{percent})<extra></extra>",
    )
    fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), showlegend=False)
    return fig
