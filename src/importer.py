"""
importer.py - CSV and Excel transaction file parsing, validation, and duplicate detection.

This module safely reads uploaded CSV and Excel (.xlsx) files into memory,
maps columns to standard names, validates every row using src.validation,
checks for duplicates, and prepares clean records for atomic batch insertion.
"""
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
import re

import pandas as pd

from src import config, database
from src.validation import validate_transaction


COLUMN_ALIASES = {
    "date": [
        "date", "transaction date", "transaction_date", "txn date", "txn_date",
        "date of transaction", "posting date", "value date"
    ],
    "description": [
        "description", "desc", "details", "particulars", "narrative",
        "remarks", "title", "item", "memo", "note"
    ],
    "amount": [
        "amount", "amt", "value", "cost", "sum", "price"
    ],
    "type": [
        "type", "transaction type", "transaction_type", "txn type", "txn_type",
        "direction", "flow"
    ],
    "category": [
        "category", "cat", "expense category", "income category"
    ],
}


class ImportValidationError(Exception):
    """Raised when an uploaded file cannot be parsed or lacks required headers."""
    pass


def map_columns(df_columns):
    """
    Map DataFrame column headers to the canonical 5 fields:
    date, description, amount, type, category.
    Returns (mapping_dict, missing_fields).
    """
    mapping = {}
    normalized = {}
    for col in df_columns:
        clean = " ".join(re.sub(r"[_\-\.]+", " ", str(col)).strip().lower().split())
        normalized[clean] = col

    for canonical, aliases in COLUMN_ALIASES.items():
        found = None
        for alias in aliases:
            if alias in normalized:
                found = normalized[alias]
                break
        if found is not None:
            mapping[canonical] = found

    required = set(COLUMN_ALIASES.keys())
    missing = [c.capitalize() for c in required if c not in mapping]
    return mapping, sorted(missing)


def parse_raw_date(raw):
    """
    Attempt to convert a raw spreadsheet date value into a python datetime.date.
    Returns python date object if converted, otherwise returns the raw value.
    """
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    if isinstance(raw, (datetime, pd.Timestamp)):
        return raw.date()
    if isinstance(raw, date):
        return raw

    s = str(raw).strip()
    if not s:
        return None

    # Try standard date string formats
    formats = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%Y/%m/%d",
        "%Y.%m.%d",
        "%d.%m.%Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue

    # Fallback to pandas to_datetime
    try:
        parsed = pd.to_datetime(s, dayfirst=True)
        if not pd.isna(parsed):
            return parsed.date()
    except Exception:
        pass

    return raw

def get_existing_signatures(db_path=None, user_id=None):
    """
    Fetch signatures of existing transactions.

    When user_id is provided, inspect only that user's transactions.

    Each signature contains:
    (date, normalized description, rounded amount, type, category)
    """
    df = database.get_transactions(
        db_path=db_path,
        user_id=user_id,
    )

    if df.empty:
        return set()

    signatures = set()

    for _, row in df.iterrows():
        sig = (
            row["date"].strftime("%Y-%m-%d"),
            " ".join(
                str(row["description"]).strip().lower().split()
            ),
            round(float(row["amount"]), 2),
            str(row["type"]).strip().lower(),
            str(row["category"]).strip().lower(),
        )

        signatures.add(sig)

    return signatures



def make_transaction_signature(cleaned_txn):
    """Generate signature tuple from a cleaned transaction dict."""
    return (
        cleaned_txn["date"].isoformat(),
        " ".join(str(cleaned_txn["description"]).strip().lower().split()),
        round(float(cleaned_txn["amount"]), 2),
        cleaned_txn["type"].strip().lower(),
        cleaned_txn["category"].strip().lower(),
    )


def read_uploaded_file(file_or_path, filename=None):
    """
    Read an uploaded CSV or XLSX file safely into a pandas DataFrame.
    Never executes spreadsheet formulas.
    Raises ImportValidationError on invalid format or corrupt file.
    """
    name = filename or getattr(file_or_path, "name", None) or str(file_or_path)
    suffix = Path(name).suffix.lower()

    if suffix == ".xls":
        raise ImportValidationError(
            "Legacy Excel (.xls) files are not supported. "
            "Please save or export your spreadsheet as an Excel workbook (.xlsx) or CSV (.csv)."
        )

    if suffix not in (".csv", ".xlsx"):
        raise ImportValidationError(
            f"Unsupported file format '{suffix}'. Please upload a CSV (.csv) or Excel (.xlsx) file."
        )

    try:
        if suffix == ".csv":
            # Read CSV with string dtype for raw values; UTF-8 with fallback
            if isinstance(file_or_path, (bytes, bytearray)):
                file_or_path = BytesIO(file_or_path)
            elif hasattr(file_or_path, "read") and hasattr(file_or_path, "seek"):
                file_or_path.seek(0)
            df = pd.read_csv(file_or_path, dtype=str, skipinitialspace=True)
        else:
            # Excel .xlsx using openpyxl, no formula execution
            if isinstance(file_or_path, (bytes, bytearray)):
                file_or_path = BytesIO(file_or_path)
            elif hasattr(file_or_path, "read") and hasattr(file_or_path, "seek"):
                file_or_path.seek(0)
            df = pd.read_excel(file_or_path, dtype=str, engine="openpyxl")
    except Exception as exc:
        raise ImportValidationError(f"Could not read file contents: {exc}") from exc

    if df.empty or len(df.columns) == 0:
        raise ImportValidationError("The uploaded file is empty.")

    return df


def parse_and_validate_file(
    file_or_path,
    filename=None,
    db_path=None,
    skip_duplicates=True,
    user_id=None,
):
    """
    Main import pipeline:
    1. Read CSV / XLSX into DataFrame.
    2. Map column headers.
    3. Validate each row using src.validation.validate_transaction.
    4. Detect duplicates against existing database records and within the file.
    5. Return a structured report dict for the UI and testing.
    """
    df = read_uploaded_file(file_or_path, filename=filename)

    mapping, missing = map_columns(df.columns)
    if missing:
        found_cols = ", ".join(f"'{c}'" for c in df.columns)
        missing_cols = ", ".join(missing)
        raise ImportValidationError(
            f"Missing required columns: {missing_cols}. "
            f"Your file has columns: [{found_cols}]. "
            "Expected columns: Date, Description, Amount, Type, Category."
        )

    existing_signatures = get_existing_signatures(
    db_path=db_path,
    user_id=user_id,
)
    file_signatures = set()

    valid_rows = []
    invalid_rows = []
    duplicate_rows = []
    preview_records = []

    for idx, raw_row in df.iterrows():
        row_num = idx + 2  # 1-indexed spreadsheet row (row 1 is header)

        raw_date = raw_row[mapping["date"]]
        raw_desc = raw_row[mapping["description"]]
        raw_amount = raw_row[mapping["amount"]]
        raw_type = raw_row[mapping["type"]]
        raw_cat = raw_row[mapping["category"]]

        # Clean NaN/null values from Pandas
        raw_date = None if pd.isna(raw_date) else raw_date
        raw_desc = None if pd.isna(raw_desc) else raw_desc
        raw_amount = None if pd.isna(raw_amount) else raw_amount
        raw_type = None if pd.isna(raw_type) else raw_type
        raw_cat = None if pd.isna(raw_cat) else raw_cat

        # Pre-process date if possible
        parsed_date = parse_raw_date(raw_date)

        cleaned, errors = validate_transaction(
            txn_date=parsed_date,
            description=raw_desc,
            amount=raw_amount,
            txn_type=raw_type,
            category=raw_cat,
        )

        raw_display = {
            "row": row_num,
            "date": str(raw_date or ""),
            "description": str(raw_desc or ""),
            "amount": str(raw_amount or ""),
            "type": str(raw_type or ""),
            "category": str(raw_cat or ""),
        }

        if errors:
            invalid_rows.append({
                "row_number": row_num,
                "raw_data": raw_display,
                "errors": errors,
            })
            preview_records.append({
                **raw_display,
                "status": "Invalid",
                "notes": "; ".join(errors),
            })
            continue

        # Check for duplicates
        sig = make_transaction_signature(cleaned)
        is_dup = False
        dup_reason = ""

        if sig in existing_signatures:
            is_dup = True
            dup_reason = "Already exists in database"
        elif sig in file_signatures:
            is_dup = True
            dup_reason = "Duplicate row within file"
        else:
            file_signatures.add(sig)

        if is_dup:
            duplicate_rows.append({
                "row_number": row_num,
                "raw_data": raw_display,
                "cleaned": cleaned,
                "reason": dup_reason,
            })
            preview_records.append({
                **raw_display,
                "status": "Duplicate",
                "notes": dup_reason,
            })
            if not skip_duplicates:
                valid_rows.append(cleaned)
        else:
            valid_rows.append(cleaned)
            preview_records.append({
                **raw_display,
                "status": "Valid",
                "notes": "Ready to import",
            })

    # Rows that will actually be imported if user submits
    rows_to_import = valid_rows

    return {
        "total_rows": len(df),
        "valid_count": len([r for r in preview_records if r["status"] == "Valid"]),
        "duplicate_count": len(duplicate_rows),
        "invalid_count": len(invalid_rows),
        "rows_to_import": rows_to_import,
        "invalid_rows": invalid_rows,
        "duplicate_rows": duplicate_rows,
        "preview_df": pd.DataFrame(preview_records),
    }
