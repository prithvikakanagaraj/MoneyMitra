
"""Financial Insights page - personalised financial analytics with Gemini AI."""

import pandas as pd
import streamlit as st
import plotly.express as px

from src import config, database, ui
from src.gemini_service import ask_finance_assistant


# ---------------------------------------------------------
# Page setup and authenticated user's transactions
# ---------------------------------------------------------

ui.setup_page("Financial Insights", "📊")

st.title("📊 Financial Insights")
st.caption(
    "Understand your spending habits, track your cash flow, "
    "and make smarter financial decisions."
)

user_id = st.session_state.get("user_id")

if user_id is None:
    st.warning("Please log in to view your financial insights.")
    st.stop()

df = database.get_transactions(user_id=user_id)

if df is None or df.empty:
    st.info(
        "You don't have any transactions yet. Add a transaction or "
        "import a CSV/Excel file to unlock your financial insights."
    )
    st.stop()


# ---------------------------------------------------------
# Prepare transaction data
# ---------------------------------------------------------

df = df.copy()
df["date"] = pd.to_datetime(df["date"], errors="coerce")
df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
df = df.dropna(subset=["date", "amount"])
df = df[df["amount"] >= 0]
df["type"] = df["type"].astype(str).str.lower().str.strip()
df["category"] = df["category"].fillna("Uncategorized").astype(str)

currency = config.CURRENCY_SYMBOL


def money(value):
    """Format an amount using MoneyMitra's configured currency."""
    return f"{currency}{value:,.2f}"


# ---------------------------------------------------------
# Date range filter
# ---------------------------------------------------------

st.subheader("📅 Choose your analysis period")

min_date = df["date"].min().date()
max_date = df["date"].max().date()

date_col1, date_col2 = st.columns(2)

with date_col1:
    start_date = st.date_input(
        "From",
        value=min_date,
        min_value=min_date,
        max_value=max_date,
        key="insights_start_date",
    )

with date_col2:
    end_date = st.date_input(
        "To",
        value=max_date,
        min_value=min_date,
        max_value=max_date,
        key="insights_end_date",
    )

if start_date > end_date:
    st.error("The start date cannot be after the end date.")
    st.stop()

period_df = df[
    (df["date"].dt.date >= start_date)
    & (df["date"].dt.date <= end_date)
].copy()

period_expenses = period_df[
    period_df["type"] == "expense"
].copy()

period_income = period_df[
    period_df["type"] == "income"
].copy()

total_income = float(period_income["amount"].sum())
total_expenses = float(period_expenses["amount"].sum())
net_cash_flow = total_income - total_expenses

st.divider()


# ---------------------------------------------------------
# Financial summary
# ---------------------------------------------------------

st.subheader("💰 Your financial summary")

metric1, metric2, metric3, metric4 = st.columns(4)

metric1.metric("Total Income", money(total_income))
metric2.metric("Total Expenses", money(total_expenses))

metric3.metric(
    "Net Cash Flow",
    money(net_cash_flow),
    delta=(
        "Positive balance"
        if net_cash_flow > 0
        else "Negative balance"
        if net_cash_flow < 0
        else "Break-even"
    ),
    delta_color="normal" if net_cash_flow >= 0 else "inverse",
)

if total_income > 0:
    savings_rate = (net_cash_flow / total_income) * 100
    metric4.metric("Income Remaining", f"{savings_rate:.1f}%")
else:
    savings_rate = None
    metric4.metric(
        "Income Remaining",
        "N/A",
        help="Add income transactions to calculate this percentage.",
    )

st.caption(
    "Income remaining is calculated as (income − expenses) ÷ income. "
    "It may be negative when expenses exceed income and does not account "
    "for transactions outside the selected period."
)

st.divider()


# ---------------------------------------------------------
# Income versus expenses
# ---------------------------------------------------------

st.subheader("📈 Income vs. Expenses")

if period_df.empty:
    st.info("No transactions were found in this date range.")
else:
    monthly = period_df.copy()
    monthly["month"] = monthly["date"].dt.to_period("M").astype(str)

    monthly_summary = (
        monthly.pivot_table(
            index="month",
            columns="type",
            values="amount",
            aggfunc="sum",
            fill_value=0,
        )
        .reset_index()
    )

    if "income" not in monthly_summary.columns:
        monthly_summary["income"] = 0.0

    if "expense" not in monthly_summary.columns:
        monthly_summary["expense"] = 0.0

    monthly_summary = monthly_summary.rename(
        columns={"income": "Income", "expense": "Expenses"}
    )

    chart_data = monthly_summary.melt(
        id_vars="month",
        value_vars=["Income", "Expenses"],
        var_name="Transaction Type",
        value_name="Amount",
    )

    fig = px.bar(
        chart_data,
        x="month",
        y="Amount",
        color="Transaction Type",
        barmode="group",
        labels={
            "month": "Month",
            "Amount": f"Amount ({currency})",
        },
        title="Monthly income and expenses",
    )

    fig.update_layout(
        template="plotly_dark",
        legend_title_text="",
        xaxis_title="Month",
        yaxis_title=f"Amount ({currency})",
        margin=dict(l=10, r=10, t=60, b=10),
    )

    st.plotly_chart(fig, use_container_width=True)

st.divider()


# ---------------------------------------------------------
# Spending by category
# ---------------------------------------------------------

st.subheader("🛍️ Where does your money go?")

category_summary = pd.DataFrame(columns=["category", "amount"])

if period_expenses.empty:
    st.info("No expenses were recorded during this period.")
else:
    category_summary = (
        period_expenses.groupby("category", as_index=False)["amount"]
        .sum()
        .sort_values("amount", ascending=False)
    )

    category_col1, category_col2 = st.columns([1.2, 1])

    with category_col1:
        category_fig = px.pie(
            category_summary,
            names="category",
            values="amount",
            hole=0.55,
            title="Expense distribution by category",
        )

        category_fig.update_layout(
            template="plotly_dark",
            margin=dict(l=10, r=10, t=60, b=10),
            legend_title_text="Category",
        )

        st.plotly_chart(category_fig, use_container_width=True)

    with category_col2:
        st.markdown("#### Category breakdown")

        display_categories = category_summary.copy()
        display_categories["amount"] = display_categories["amount"].map(money)

        display_categories = display_categories.rename(
            columns={
                "category": "Category",
                "amount": "Total Spent",
            }
        )

        st.dataframe(
            display_categories,
            use_container_width=True,
            hide_index=True,
        )

        highest_category = category_summary.iloc[0]

        st.metric(
            "Highest spending category",
            highest_category["category"],
            money(float(highest_category["amount"])),
        )

st.divider()


# ---------------------------------------------------------
# Spending patterns and month-over-month comparison
# ---------------------------------------------------------

st.subheader("🔍 Spending patterns")

if period_expenses.empty:
    st.info(
        "Once you record expenses, MoneyMitra will identify "
        "your largest spending day and monthly spending changes."
    )
else:
    highest_expense = period_expenses.loc[
        period_expenses["amount"].idxmax()
    ]

    pattern_col1, pattern_col2 = st.columns(2)

    with pattern_col1:
        st.markdown("#### Largest individual expense")

        st.metric(
            label=str(highest_expense["description"]),
            value=money(float(highest_expense["amount"])),
        )

        st.caption(
            f"Category: {highest_expense['category']} · "
            f"Date: {highest_expense['date'].strftime('%d %b %Y')}"
        )

    with pattern_col2:
        st.markdown("#### Average expense")

        average_expense = float(period_expenses["amount"].mean())

        st.metric(
            "Average per expense transaction",
            money(average_expense),
        )

    monthly_expenses = period_expenses.copy()
    monthly_expenses["month"] = monthly_expenses["date"].dt.to_period("M")

    monthly_expense_totals = (
        monthly_expenses.groupby("month")["amount"].sum().sort_index()
    )

    if len(monthly_expense_totals) >= 2:
        previous_month = monthly_expense_totals.iloc[-2]
        current_month = monthly_expense_totals.iloc[-1]
        change = current_month - previous_month

        if previous_month > 0:
            percentage_change = (change / previous_month) * 100

            if change > 0:
                st.warning(
                    f"Your expenses increased by "
                    f"{abs(percentage_change):.1f}% compared with "
                    "the previous recorded month."
                )
            elif change < 0:
                st.success(
                    f"Your expenses decreased by "
                    f"{abs(percentage_change):.1f}% compared with "
                    "the previous recorded month."
                )
            else:
                st.info(
                    "Your total expenses remained unchanged "
                    "compared with the previous recorded month."
                )

        elif current_month > 0:
            st.info(
                "Your latest recorded month has expenses, while the "
                "previous recorded month had none. A percentage "
                "change cannot be calculated from a zero baseline."
            )
        else:
            st.info(
                "No expenses were recorded in either of the "
                "two latest recorded months."
            )
    else:
        st.info(
            "Record expenses across at least two different months "
            "to unlock month-over-month spending comparisons."
        )

st.divider()


# ---------------------------------------------------------
# Rule-based financial observations
# ---------------------------------------------------------

st.subheader("💡 Your financial observations")

observations = []

if period_df.empty:
    observations.append(
        "There are no transactions in the selected period. "
        "Try selecting a different date range."
    )
else:
    if total_income > 0:
        if total_expenses > total_income:
            observations.append(
                "Your recorded expenses exceed your income during "
                "this period. Review discretionary spending and "
                "check whether all transactions are recorded."
            )
        elif total_expenses == total_income:
            observations.append(
                "Your recorded income and expenses are equal. "
                "There is no remaining cash flow in this period."
            )
        else:
            observations.append(
                f"You have {money(net_cash_flow)} remaining after "
                "your recorded expenses during this period."
            )
    elif total_expenses > 0:
        observations.append(
            "Expenses are recorded, but no income appears in this "
            "period. Add any missing income transactions if applicable."
        )
    else:
        observations.append(
            "No income or expense transactions were recorded "
            "in this period."
        )

    if not period_expenses.empty:
        highest_category = category_summary.iloc[0]

        category_share = (
            float(highest_category["amount"]) / total_expenses * 100
            if total_expenses > 0
            else 0
        )

        observations.append(
            f"Your largest spending category is "
            f"'{highest_category['category']}', accounting for "
            f"{category_share:.1f}% of your recorded expenses."
        )

        if category_share >= 50:
            observations.append(
                "More than half of your recorded expenses fall "
                "into one category. Review those transactions to "
                "see whether any spending can be reduced."
            )

    if total_income > 0 and savings_rate is not None:
        if savings_rate < 0:
            observations.append(
                "Your income remaining percentage is negative. "
                "Consider reviewing your expenses against your income."
            )
        elif savings_rate < 20:
            observations.append(
                "Less than 20% of your recorded income remains "
                "after expenses. If practical, review recurring "
                "costs and discretionary purchases."
            )
        else:
            observations.append(
                "At least 20% of your recorded income remains "
                "after expenses during this period."
            )

for observation in observations:
    st.markdown(f"- {observation}")


# ---------------------------------------------------------
# AI Financial Advisor
# ---------------------------------------------------------

st.divider()
st.subheader("✨ AI Financial Advisor")

st.write(
    "Get personalized observations and practical suggestions "
    "based on your transactions in the selected analysis period."
)

st.caption(
    "MoneyMitra calculates financial figures using Python. "
    "Gemini explains patterns and suggests possible actions."
)

if period_df.empty:
    st.info(
        "There are no transactions in the selected period to analyze. "
        "Choose another date range."
    )
else:
    if st.button(
        "✨ Generate AI Insights",
        type="primary",
        key="generate_ai_insights",
    ):
        # Only the current user's transactions from the selected
        # date range are passed to the AI service.
        ai_df = period_df[
            [
                "date",
                "description",
                "type",
                "category",
                "amount",
            ]
        ].copy()

        

        period_context = (
            f"ANALYSIS PERIOD: {start_date} to {end_date}\n"
            f"TOTAL INCOME: {money(total_income)}\n"
            f"TOTAL EXPENSES: {money(total_expenses)}\n"
            f"NET CASH FLOW: {money(net_cash_flow)}\n"
            f"INCOME REMAINING: "
            f"{f'{savings_rate:.1f}%' if savings_rate is not None else 'Not available'}\n"
            f"TRANSACTION COUNT: {len(ai_df)}\n"
            f"EXPENSE CATEGORY BREAKDOWN:\n"
        )

        if not period_expenses.empty:
            for _, row in category_summary.iterrows():
                share = (
                    float(row["amount"]) / total_expenses * 100
                    if total_expenses > 0
                    else 0
                )
                period_context += (
                    f"- {row['category']}: {money(float(row['amount']))} "
                    f"({share:.1f}% of expenses)\n"
                )
        else:
            period_context += "- No expenses recorded.\n"

        period_context += (
            "\nMONTHLY INCOME AND EXPENSES:\n"
        )

        if not period_df.empty:
            ai_monthly = period_df.copy()
            ai_monthly["month"] = ai_monthly["date"].dt.to_period("M").astype(str)

            for month, month_df in ai_monthly.groupby("month", sort=True):
                month_income = float(
                    month_df.loc[month_df["type"] == "income", "amount"].sum()
                )
                month_expenses = float(
                    month_df.loc[month_df["type"] == "expense", "amount"].sum()
                )
                period_context += (
                    f"- {month}: income {money(month_income)}, "
                    f"expenses {money(month_expenses)}, "
                    f"net {money(month_income - month_expenses)}\n"
                )

        period_context += (
            "\nUse only the facts supplied above. Do not invent numbers, "
            "transactions, causes, or trends. Explain any uncertainty. "
            "Provide a concise analysis with these headings:\n"
            "1. Financial overview\n"
            "2. Spending patterns\n"
            "3. What is going well\n"
            "4. Practical recommendations\n"
            "5. One action to take next\n"
            "Keep the advice realistic, non-judgmental, and specific to "
            "the supplied data. Do not claim to be a certified financial "
            "planner. Do not repeat personal transaction descriptions."
        )

        with st.spinner(
            "MoneyMitra is analyzing your selected financial period..."
        ):
            try:
                result = ask_finance_assistant(
                    prompt=(
                        "Generate a personalized financial analysis "
                        "for the selected period. Follow the instructions "
                        "and use the financial context below as the "
                        "authoritative source.\n\n"
                        f"{period_context}"
                    ),
                    df=ai_df,
                    user_id=user_id,
                )

                if result.get("success"):
                    st.session_state["ai_financial_insights"] = {
                        "user_id": user_id,
                        "start_date": str(start_date),
                        "end_date": str(end_date),
                        "response": result["response"],
                    }
                else:
                    st.error(
                        result.get(
                            "response",
                            "Unable to generate AI insights. Please try again.",
                        )
                    )
            except Exception:
                st.error(
                    "Something went wrong while generating AI insights. "
                    "Your existing financial data and charts are unaffected."
                    "Please try again. "
                )
                


    saved_insights = st.session_state.get("ai_financial_insights")

    if saved_insights:
        # Never display a previous user's analysis or stale date-range result.
        if (
            saved_insights.get("user_id") == user_id
            and saved_insights.get("start_date") == str(start_date)
            and saved_insights.get("end_date") == str(end_date)
        ):
            st.markdown("### 🧠 Your personalized analysis")
            st.markdown(saved_insights["response"])
            st.caption(
                "AI-generated guidance is informational and may be imperfect. "
                "Verify financial figures against the summary above."
            )
        elif st.session_state.get("ai_financial_insights") is not None:
            st.session_state.pop("ai_financial_insights", None)


# ---------------------------------------------------------
# Transaction summary
# ---------------------------------------------------------

with st.expander("View transaction summary"):
    st.write(f"**Transactions analysed:** {len(period_df)}")
    st.write(f"**Income transactions:** {len(period_income)}")
    st.write(f"**Expense transactions:** {len(period_expenses)}")
    st.write(
        f"**Analysis period:** {start_date.strftime('%d %b %Y')} "
        f"to {end_date.strftime('%d %b %Y')}"
    )

st.caption(
    "These insights are based on your recorded transactions and are "
    "informational only, not professional financial advice."
)
