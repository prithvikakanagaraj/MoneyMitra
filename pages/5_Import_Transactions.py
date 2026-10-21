
"""Import Transactions page: upload and import CSV or Excel (.xlsx) files."""

import streamlit as st

from src import config, database, ui
from src.importer import ImportValidationError, parse_and_validate_file


ui.setup_page("Import Transactions", "📥")

st.title("📥 Import Transactions")

st.caption(
    "Upload your transactions from a spreadsheet "
    "(CSV or Excel) into your personal finance database."
)

# Get the authenticated user's ID.
user_id = st.session_state["user_id"]


# ---- Template / Guidelines ----------------------------------------

with st.expander("ℹ️ File format guidelines & allowed categories"):
    st.markdown(
        """
        Your spreadsheet must contain these **5 columns**
        (column names are case-insensitive):

        - **Date:** e.g. `2025-01-15` or `15/01/2025`
        - **Description:** e.g. `Groceries at supermarket`
        - **Amount:** e.g. `250` or `1250.50` (positive numbers only)
        - **Type:** `income` or `expense`
        - **Category:** must match one of the allowed categories below
        """
    )

    col_a, col_b = st.columns(2)

    with col_a:
        st.write("**Allowed Expense categories:**")
        st.write(", ".join(config.EXPENSE_CATEGORIES))

    with col_b:
        st.write("**Allowed Income categories:**")
        st.write(", ".join(config.INCOME_CATEGORIES))

    sample_csv = (
        "Date,Description,Amount,Type,Category\n"
        "2025-01-15,Supermarket groceries,1450.50,expense,Food\n"
        "2025-01-16,Monthly salary,55000,income,Salary\n"
        "2025-01-18,Electricity bill,1200,expense,Bills\n"
    )

    st.download_button(
        label="Download sample CSV template",
        data=sample_csv,
        file_name="sample_transactions.csv",
        mime="text/csv",
    )


# ---- File Uploader & Options --------------------------------------

st.subheader("1. Upload file")

uploaded_file = st.file_uploader(
    "Choose a CSV or Excel file",
    type=["csv", "xlsx"],
    help="Select a .csv or .xlsx file. Legacy .xls files are not supported.",
)

skip_duplicates = st.checkbox(
    "Skip duplicate transactions (Recommended)",
    value=True,
    help=(
        "Automatically ignores rows that already exist in your account "
        "or are repeated within this file."
    ),
)

if not uploaded_file:
    st.info(
        "Upload a .csv or .xlsx file to see a preview "
        "of transactions before importing."
    )
    st.stop()


# ---- Process & Preview --------------------------------------------

st.subheader("2. Preview & Validation")

try:
    result = parse_and_validate_file(
        uploaded_file,
        filename=uploaded_file.name,
        skip_duplicates=skip_duplicates,
        user_id=user_id,
    )

except ImportValidationError as err:
    st.error(f"❌ {err}")
    st.stop()

except Exception as err:
    st.error(f"❌ Unexpected error reading file: {err}")
    st.stop()


# ---- Summary Cards -------------------------------------------------

col1, col2, col3, col4 = st.columns(4)

with col1, st.container(border=True):
    st.metric("Total rows found", result["total_rows"])

with col2, st.container(border=True):
    st.metric("Ready to import", len(result["rows_to_import"]))

with col3, st.container(border=True):
    st.metric("Duplicates detected", result["duplicate_count"])

with col4, st.container(border=True):
    st.metric("Invalid rows", result["invalid_count"])


# ---- Validation Alerts --------------------------------------------

if result["invalid_count"] > 0:
    st.warning(
        f"⚠️ **{result['invalid_count']} row(s)** contain errors "
        "and will be **skipped**. Review the details below."
    )

    with st.expander(
        f"View {result['invalid_count']} invalid row error(s)",
        expanded=False,
    ):
        for inv in result["invalid_rows"]:
            st.markdown(
                f"- **Row {inv['row_number']}** "
                f"({inv['raw_data']['description'] or 'Empty'}): "
                f"`{'; '.join(inv['errors'])}`"
            )


if result["duplicate_count"] > 0:
    if skip_duplicates:
        st.info(
            f"ℹ️ **{result['duplicate_count']} duplicate row(s)** "
            "detected and skipped."
        )
    else:
        st.warning(
            f"⚠️ **{result['duplicate_count']} duplicate row(s)** "
            "will be imported because duplicate skipping is disabled."
        )


# ---- Preview Table -------------------------------------------------

st.write("**File preview:**")

st.dataframe(
    result["preview_df"],
    hide_index=True,
    column_config={
        "row": st.column_config.NumberColumn("Row #", width="small"),
        "date": st.column_config.TextColumn("Date", width="medium"),
        "description": st.column_config.TextColumn(
            "Description",
            width="large",
        ),
        "amount": st.column_config.TextColumn("Amount", width="small"),
        "type": st.column_config.TextColumn("Type", width="small"),
        "category": st.column_config.TextColumn(
            "Category",
            width="medium",
        ),
        "status": st.column_config.TextColumn("Status", width="small"),
        "notes": st.column_config.TextColumn(
            "Notes / Errors",
            width="large",
        ),
    },
)


# ---- Import Action -------------------------------------------------

st.subheader("3. Confirm Import")

to_import_count = len(result["rows_to_import"])

if to_import_count == 0:
    st.error("No valid transactions to import from this file.")

else:
    import_label = f"Import {to_import_count} valid transaction(s)"

    if st.button(import_label, type="primary"):
        try:
            # IMPORTANT: save every imported transaction under this user.
            inserted = database.add_transactions_batch(
                result["rows_to_import"],
                user_id=user_id,
            )

            st.success(
                f"🎉 Successfully imported **{inserted}** "
                "transaction(s) into your account!"
            )

            st.page_link(
                "pages/2_Transaction_History.py",
                label="View in Transaction History",
                icon="📜",
            )

            st.page_link(
                "app.py",
                label="Go to Dashboard",
                icon="💰",
            )

        except Exception:
            st.error(
                "❌ A database error occurred during import. "
                "Please check the terminal for details. "
                "The batch operation should roll back its changes."
            )
