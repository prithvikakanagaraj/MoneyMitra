"""
validation.py - checks user input BEFORE it reaches the database.

validate_transaction() never crashes on bad input. It returns:
    (cleaned_transaction_or_None, list_of_error_messages)
so the web page can show every problem at once in plain English.
"""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from src import config


def _parse_date(raw):
    if raw is None or raw == "":
        return None, "Please choose a date."
    if isinstance(raw, datetime):
        parsed = raw.date()
    elif isinstance(raw, date):
        parsed = raw
    else:
        try:
            parsed = datetime.strptime(str(raw).strip(), "%Y-%m-%d").date()
        except ValueError:
            return None, "Date is not valid. Use the format YYYY-MM-DD."
    if parsed > date.today():
        return None, "Date cannot be in the future."
    if parsed < config.MIN_DATE:
        return None, f"Date cannot be before {config.MIN_DATE.isoformat()}."
    return parsed, None


def _parse_description(raw):
    text = " ".join(str(raw or "").split())  # trims and collapses repeated spaces
    if not text:
        return None, "Description is required."
    if len(text) > config.MAX_DESCRIPTION_LENGTH:
        return None, f"Description is too long (maximum {config.MAX_DESCRIPTION_LENGTH} characters)."
    return text, None


def _parse_amount(raw):
    if raw is None:
        return None, "Amount is required."
    text = str(raw).strip().replace(",", "").replace(config.CURRENCY_SYMBOL, "").strip()
    if not text:
        return None, "Amount is required."
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None, "Amount must be a number, for example 250 or 99.50."
    if not value.is_finite():
        return None, "Amount must be a number, for example 250 or 99.50."
    if value <= 0:
        return None, ("Amount must be greater than zero. "
                      "Use the Income / Expense choice for direction instead of a minus sign.")
    if value > config.MAX_AMOUNT:
        return None, f"Amount is too large (maximum {config.MAX_AMOUNT:,})."
    if value != value.quantize(Decimal("0.01")):
        return None, "Amount can have at most 2 decimal places."
    return value.quantize(Decimal("0.01")), None


def _parse_type(raw):
    text = str(raw or "").strip().lower()
    if text not in config.TRANSACTION_TYPES:
        return None, "Type must be either 'income' or 'expense'."
    return text, None


def _parse_category(raw, txn_type):
    text = str(raw or "").strip()
    if not text:
        return None, "Please choose a category."
    if txn_type is None:
        return None, None  # type is already reported as an error; don't pile on
    allowed = {c.lower(): c for c in config.CATEGORIES_BY_TYPE[txn_type]}
    if text.lower() not in allowed:
        return None, f"'{text}' is not a valid {txn_type} category. Choose one of: {', '.join(allowed.values())}."
    return allowed[text.lower()], None


def validate_transaction(txn_date, description, amount, txn_type, category):
    """Validate all five fields. Returns (cleaned_dict_or_None, errors_list)."""
    errors = []

    parsed_date, err = _parse_date(txn_date)
    if err: errors.append(err)

    parsed_description, err = _parse_description(description)
    if err: errors.append(err)

    parsed_amount, err = _parse_amount(amount)
    if err: errors.append(err)

    parsed_type, err = _parse_type(txn_type)
    if err: errors.append(err)

    parsed_category, err = _parse_category(category, parsed_type)
    if err: errors.append(err)

    if errors:
        return None, errors

    return {
        "date": parsed_date,
        "description": parsed_description,
        "amount": parsed_amount,
        "type": parsed_type,
        "category": parsed_category,
    }, []
