
"""
app.py - MoneyMitra entry point.

Start with: streamlit run app.py
"""

import re

import streamlit as st

from src import auth, calculations as calc
from src import charts, config, database, ui


# -------------------------------------------------------------------
# Page setup and database initialization
# -------------------------------------------------------------------

st.set_page_config(
    page_title=f"MoneyMitra | {config.APP_TITLE}",
    page_icon="💚",
    layout="wide",
)

database.init_db()


# -------------------------------------------------------------------
# Session state
# -------------------------------------------------------------------

defaults = {
    "authenticated": False,
    "user_id": None,
    "user_name": None,
    "user_email": None,
    "auth_page": "Login",
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# -------------------------------------------------------------------
# Midnight Finance styling
# IMPORTANT: All CSS stays inside this single style block.
# -------------------------------------------------------------------

st.markdown(
    """
    <style>
    /* Main application background */

    .stApp {
        background-color: #0B1220;
        color: #E5EDF7;
    }

    /* Main content spacing */

    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
        max-width: 1200px;
    }

    /* Typography */

    h1, h2, h3 {
        color: #F1F5F9;
        letter-spacing: -0.4px;
    }

    p {
        color: #CBD5E1;
    }

    /* MoneyMitra branding */

    .money-mitra-title {
        font-size: 2.7rem;
        font-weight: 800;
        color: #34D399;
        text-align: center;
        margin-bottom: 0;
    }

    .money-mitra-subtitle {
        text-align: center;
        color: #B7C4D8;
        font-size: 1rem;
        margin-bottom: 1.8rem;
    }

    /* Dashboard metric cards */

    [data-testid="stMetric"] {
        background-color: #151F32;
        border: 1px solid #26364D;
        padding: 20px;
        border-radius: 14px;
        transition:
            border-color 0.2s ease,
            transform 0.2s ease;
    }

    [data-testid="stMetric"]:hover {
        border-color: #34D399;
        transform: translateY(-2px);
    }

    [data-testid="stMetricLabel"] {
        color: #A8B6CA;
    }

    [data-testid="stMetricValue"] {
        color: #F1F5F9;
        font-weight: 700;
    }

    /* Containers and cards */

    [data-testid="stVerticalBlockBorderWrapper"] {
        border-color: #26364D;
        border-radius: 14px;
    }

    /* Buttons */

    div.stButton > button,
    div.stFormSubmitButton > button {
        border-radius: 9px;
        min-height: 42px;
        transition:
            border-color 0.2s ease,
            background-color 0.2s ease;
    }

    div.stButton > button:hover,
    div.stFormSubmitButton > button:hover {
        border-color: #34D399;
    }

    /* Primary buttons */

    div.stButton > button[kind="primary"],
    div.stFormSubmitButton > button[kind="primary"] {
        background-color: #059669;
        border-color: #059669;
        color: #FFFFFF;
    }

    div.stButton > button[kind="primary"]:hover,
    div.stFormSubmitButton > button[kind="primary"]:hover {
        background-color: #047857;
        border-color: #34D399;
        color: #FFFFFF;
    }

    /* Input fields */

    [data-testid="stTextInput"] input {
        background-color: #111827;
        color: #F1F5F9;
        border-color: #334155;
        border-radius: 9px;
    }

    [data-testid="stTextInput"] input:focus {
        border-color: #34D399;
        box-shadow: 0 0 0 1px #34D399;
    }

    /* Tabs */

    [data-testid="stTabs"] button {
        color: #CBD5E1;
    }

    [data-testid="stTabs"] button[aria-selected="true"] {
        color: #34D399;
    }

    [data-testid="stTabs"] [data-baseweb="tab-highlight"] {
        background-color: #34D399;
    }

    /* Sidebar */

    [data-testid="stSidebar"] {
        background-color: #111827;
        border-right: 1px solid #26364D;
    }

    [data-testid="stSidebar"] h2 {
        color: #34D399;
    }

    /* Section separators */

    hr {
        border-color: #26364D;
        opacity: 0.8;
    }

    /* Caption text */

    [data-testid="stCaptionContainer"] {
        color: #A8B6CA;
    }

    /* Data tables */

    [data-testid="stDataFrame"] {
        border: 1px solid #26364D;
        border-radius: 12px;
        overflow: hidden;
    }

    /* Links */

    a {
        color: #34D399;
    }

    a:hover {
        color: #6EE7B7;
    }

    /* Responsive layout */

    @media (max-width: 768px) {
        .block-container {
            padding-top: 1rem;
            padding-left: 1rem;
            padding-right: 1rem;
        }

        .money-mitra-title {
            font-size: 2.1rem;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# -------------------------------------------------------------------
# Authentication helpers
# -------------------------------------------------------------------

def validate_registration(name, email, password, confirm_password):
    """Return an error message when registration input is invalid."""

    name = name.strip()
    email = email.strip().lower()

    if not name:
        return "Please enter your name."

    if len(name) > 100:
        return "Your name must be 100 characters or fewer."

    if not email or not re.fullmatch(
        r"[^@\s]+@[^@\s]+\.[^@\s]+",
        email,
    ):
        return "Please enter a valid email address."

    if len(email) > 254:
        return "Your email address is too long."

    if len(password) < 8:
        return "Your password must contain at least 8 characters."

    if len(password) > 128:
        return "Your password must contain no more than 128 characters."

    if password != confirm_password:
        return "The passwords do not match."

    return None


def log_in_user(user):
    """Save the authenticated user's details in the session."""

    st.session_state["authenticated"] = True
    st.session_state["user_id"] = user["id"]
    st.session_state["user_name"] = user["name"]
    st.session_state["user_email"] = user["email"]


def log_out_user():
    """Clear authentication details from the session."""

    st.session_state["authenticated"] = False
    st.session_state["user_id"] = None
    st.session_state["user_name"] = None
    st.session_state["user_email"] = None
    st.session_state["auth_page"] = "Login"


# -------------------------------------------------------------------
# Login and registration screens
# -------------------------------------------------------------------

def render_auth_screen():
    """Display the MoneyMitra login or account-creation screen."""

    left, center, right = st.columns([1, 1.3, 1])

    with center:
        st.markdown(
            '<p class="money-mitra-title">💚 MoneyMitra</p>',
            unsafe_allow_html=True,
        )

        st.markdown(
            '<p class="money-mitra-subtitle">'
            "Your Money. Your Mitra. Your Smarter Future."
            "</p>",
            unsafe_allow_html=True,
        )

        login_tab, register_tab = st.tabs(
            ["🔐 Login", "✨ Create Account"]
        )

        # ---------------- Login ----------------

        with login_tab:
            st.subheader("Welcome back!")

            st.caption(
                "Log in to access your personal finance dashboard."
            )

            with st.form("login_form"):
                email = st.text_input(
                    "Email address",
                    placeholder="you@example.com",
                ).strip().lower()

                password = st.text_input(
                    "Password",
                    type="password",
                    placeholder="Enter your password",
                )

                login_submitted = st.form_submit_button(
                    "Login",
                    use_container_width=True,
                    type="primary",
                )

            if login_submitted:
                if not email or not password:
                    st.error(
                        "Please enter both your email and password."
                    )
                else:
                    user = database.get_user_by_email(email)

                    if user and auth.verify_password(
                        password,
                        user["password_hash"],
                    ):
                        log_in_user(user)
                        st.rerun()
                    else:
                        st.error("Invalid email or password.")

        # ---------------- Registration ----------------

        with register_tab:
            st.subheader("Create your account")

            st.caption(
                "Your own space to track spending and understand your money."
            )

            with st.form("register_form"):
                name = st.text_input(
                    "Full name",
                    placeholder="Enter your name",
                )

                email = st.text_input(
                    "Email address",
                    placeholder="you@example.com",
                    key="register_email",
                )

                password = st.text_input(
                    "Create password",
                    type="password",
                    placeholder="At least 8 characters",
                    key="register_password",
                )

                confirm_password = st.text_input(
                    "Confirm password",
                    type="password",
                    placeholder="Enter the same password again",
                    key="confirm_password",
                )

                register_submitted = st.form_submit_button(
                    "Create Account",
                    use_container_width=True,
                    type="primary",
                )

            if register_submitted:
                error = validate_registration(
                    name,
                    email,
                    password,
                    confirm_password,
                )

                if error:
                    st.error(error)
                else:
                    normalized_email = email.strip().lower()

                    existing_user = database.get_user_by_email(
                        normalized_email
                    )

                    if existing_user:
                        st.error(
                            "An account with this email already exists. "
                            "Please log in instead."
                        )
                    else:
                        password_hash = auth.hash_password(password)

                        user_id = database.create_user(
                            name=name.strip(),
                            email=normalized_email,
                            password_hash=password_hash,
                        )

                        if user_id is None:
                            st.error(
                                "We couldn't create your account. "
                                "Please try again."
                            )
                        else:
                            user = database.get_user_by_id(user_id)

                            if user:
                                log_in_user(user)

                                st.success(
                                    "Your account was created successfully!"
                                )

                                st.rerun()
                            else:
                                st.error(
                                    "Your account was created, but we "
                                    "couldn't load it. Please try logging in."
                                )

        st.divider()

        st.caption(
            "🔒 Your password is stored as a secure Argon2 hash, "
            "not as plain text."
        )


# -------------------------------------------------------------------
# Authentication gate
# -------------------------------------------------------------------

if not st.session_state["authenticated"]:
    render_auth_screen()
    st.stop()


# -------------------------------------------------------------------
# Sidebar
# -------------------------------------------------------------------

with st.sidebar:
    st.markdown("## 💚 MoneyMitra")

    st.caption("Your personal finance companion")

    st.divider()

    st.write(f"Welcome, **{st.session_state['user_name']}!**")

    st.caption(st.session_state["user_email"])

    if st.button("🚪 Logout", use_container_width=True):
        log_out_user()
        st.rerun()


# -------------------------------------------------------------------
# Dashboard heading
# -------------------------------------------------------------------

st.markdown("## 💚 MoneyMitra")

st.title("Your Financial Overview")

st.caption(
    "A clearer picture of your money starts here. "
    "Track your income, understand your spending, "
    "and make more confident financial decisions."
)


# -------------------------------------------------------------------
# Retrieve the authenticated user's transactions
# -------------------------------------------------------------------

user_id = st.session_state["user_id"]

df = database.get_transactions(user_id=user_id)

if df.empty:
    st.info(
        "No transactions yet. Add your first transaction "
        "to see your dashboard come alive."
    )

    st.page_link(
        "pages/1_Add_Transaction.py",
        label="Add a transaction",
        icon="➕",
    )

    st.stop()


# -------------------------------------------------------------------
# Sample-data warning
# -------------------------------------------------------------------

if df["description"].str.startswith(
    config.SAMPLE_PREFIX,
    na=False,
).any():
    st.warning(
        "Some of your transactions are SAMPLE data "
        "(descriptions start with '[SAMPLE]'). "
        "We will add a user-specific option to remove sample data safely."
    )


# -------------------------------------------------------------------
# Summary cards
# -------------------------------------------------------------------

summary = calc.compute_summary(df)

col1, col2, col3 = st.columns(3)

with col1:
    with st.container(border=True):
        st.markdown("💚 **TOTAL INCOME**")

        st.metric(
            label="Money received",
            value=calc.format_currency(summary["total_income"]),
            label_visibility="collapsed",
        )

with col2:
    with st.container(border=True):
        st.markdown("🟠 **TOTAL EXPENSES**")

        st.metric(
            label="Money spent",
            value=calc.format_currency(summary["total_expense"]),
            label_visibility="collapsed",
        )

with col3:
    with st.container(border=True):
        st.markdown("💎 **NET CASH FLOW**")

        st.metric(
            label="Income minus expenses",
            value=calc.format_currency(summary["net_cash_flow"]),
            label_visibility="collapsed",
        )

st.caption(
    f"📊 Based on {summary['transaction_count']} transactions."
)


# -------------------------------------------------------------------
# Charts
# -------------------------------------------------------------------

st.divider()

left, right = st.columns(2)

with left:
    st.subheader("📈 Monthly income vs expenses")

    monthly_df = calc.monthly_summary(df)

    st.plotly_chart(
        charts.monthly_chart(monthly_df),
        use_container_width=True,
    )

with right:
    st.subheader("🥧 Spending by category")

    category_df = calc.category_spending(df)

    if category_df.empty:
        st.info(
            "No expenses recorded yet, so there is nothing "
            "to chart by category."
        )
    else:
        st.plotly_chart(
            charts.category_chart(category_df),
            use_container_width=True,
        )


# -------------------------------------------------------------------
# Recent activity
# -------------------------------------------------------------------

st.divider()

st.subheader("🧾 Latest transactions")

st.caption("Your five most recent recorded transactions.")

ui.show_transactions_table(df.head(5))
