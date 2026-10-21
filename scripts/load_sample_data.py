"""
Load clearly-labelled SAMPLE transactions so you can see the charts working.

    python -m scripts.load_sample_data            # add the sample rows
    python -m scripts.load_sample_data --remove   # delete ONLY the sample rows

Every sample description starts with "[SAMPLE]" so it can't be confused with real data.
The dates are relative to today, covering roughly the last 4 months.
"""
import argparse
from datetime import date, timedelta

from src import config, database
from src.validation import validate_transaction

# (days_ago, description, amount, type, category)
SAMPLE_ROWS = [
    (118, "Monthly salary", "52000", "income", "Salary"),
    (115, "Rent and electricity", "14500", "expense", "Bills"),
    (112, "Groceries", "3200.75", "expense", "Food"),
    (105, "Online course", "2999", "expense", "Education"),
    (98, "Movie night", "650", "expense", "Entertainment"),
    (90, "Monthly salary", "52000", "income", "Salary"),
    (88, "Rent and electricity", "14800", "expense", "Bills"),
    (84, "Train tickets", "1850", "expense", "Travel"),
    (80, "Restaurant dinner", "1450.50", "expense", "Food"),
    (75, "Headphones", "3499", "expense", "Shopping"),
    (68, "Freelance project", "9000", "income", "Freelance"),
    (60, "Monthly salary", "52000", "income", "Salary"),
    (58, "Rent and electricity", "14500", "expense", "Bills"),
    (52, "Groceries", "2890.25", "expense", "Food"),
    (47, "Textbooks", "1750", "expense", "Education"),
    (41, "Weekend trip", "6200", "expense", "Travel"),
    (35, "Concert ticket", "2200", "expense", "Entertainment"),
    (30, "Monthly salary", "52000", "income", "Salary"),
    (28, "Rent and electricity", "15100", "expense", "Bills"),
    (24, "Groceries", "3410", "expense", "Food"),
    (19, "Clothes shopping", "4150", "expense", "Shopping"),
    (14, "Coffee and snacks", "380", "expense", "Food"),
    (9, "Streaming subscription", "499", "expense", "Entertainment"),
    (5, "Auto fare and cab rides", "720", "expense", "Travel"),
    (2, "Stationery", "260", "expense", "Other"),
]


def main():
    parser = argparse.ArgumentParser(description="Load or remove SAMPLE transactions.")
    parser.add_argument("--remove", action="store_true", help="delete the sample rows instead of adding them")
    args = parser.parse_args()

    database.init_db()
    if args.remove:
        print(f"Removed {database.delete_sample_transactions()} sample transactions.")
        return

    today = date.today()
    for days_ago, description, amount, txn_type, category in SAMPLE_ROWS:
        cleaned, errors = validate_transaction(
            today - timedelta(days=days_ago), config.SAMPLE_PREFIX + description, amount, txn_type, category
        )
        if errors:
            raise SystemExit(f"Bad sample row {description!r}: {errors}")
        database.add_transaction(cleaned)
    print(f"Added {len(SAMPLE_ROWS)} SAMPLE transactions to {config.DB_PATH}")
    print("Remove them any time with: python -m scripts.load_sample_data --remove")


if __name__ == "__main__":
    main()
