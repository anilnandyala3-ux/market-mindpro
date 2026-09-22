import json
import os
import re
import html
import hashlib
import secrets
from datetime import datetime

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from groq import Groq
from io import BytesIO
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


# =========================================================
# LOAD ENVIRONMENT VARIABLES
# =========================================================

load_dotenv()

env_api_key = (
    os.getenv("GROQ_API_KEY") or ""
).strip().strip('"').strip("'")

REPORTS_FILE = "reports.json"
USERS_FILE = "users.json"

# Recommended current Groq model
DEFAULT_MODEL = "openai/gpt-oss-20b"


# =========================================================
# PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="Market Mind Pro",
    page_icon="🧠",
    layout="wide"
)


# =========================================================
# SESSION STATE
# =========================================================

if "result" not in st.session_state:
    st.session_state.result = ""

if "idea" not in st.session_state:
    st.session_state.idea = ""

if "authenticated_user" not in st.session_state:
    st.session_state.authenticated_user = None


# =========================================================
# REPORT FUNCTIONS
# =========================================================

def load_reports():
    if not os.path.exists(REPORTS_FILE):
        return []

    try:
        with open(REPORTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return data

        return []

    except Exception:
        return []


def save_reports(reports):
    try:
        with open(REPORTS_FILE, "w", encoding="utf-8") as f:
            json.dump(
                reports,
                f,
                ensure_ascii=False,
                indent=2
            )
    except Exception as err:
        st.warning(f"Could not save report history: {err}")


def load_users():
    if not os.path.exists(USERS_FILE):
        return []

    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2)


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        120000,
    ).hex()
    return salt, password_hash


def password_matches(password, user):
    _, password_hash = hash_password(password, user["salt"])
    return secrets.compare_digest(password_hash, user["password_hash"])


if st.session_state.authenticated_user is None:
    st.title("🧠 Market Mind Pro")
    st.subheader("Create your account or sign in")

    login_tab, signup_tab, reset_tab = st.tabs(
        ["Sign in", "Create account", "Reset password"]
    )

    with login_tab:
        login_username = st.text_input("Username", key="login_username")
        login_password = st.text_input(
            "Password",
            type="password",
            key="login_password",
        )

        if st.button("Sign in", type="primary", width="stretch"):
            users = load_users()
            user = next(
                (
                    saved_user
                    for saved_user in users
                    if saved_user.get("username", "").lower()
                    == login_username.strip().lower()
                ),
                None,
            )

            if user and password_matches(login_password, user):
                st.session_state.authenticated_user = user["username"]
                st.rerun()
            else:
                st.error("Invalid username or password.")

    with signup_tab:
        signup_email = st.text_input("Email", key="signup_email")
        signup_username = st.text_input("Username", key="signup_username")
        signup_password = st.text_input(
            "Password",
            type="password",
            key="signup_password",
        )
        signup_confirmation = st.text_input(
            "Confirm password",
            type="password",
            key="signup_confirmation",
        )

        if st.button("Create account", type="primary", width="stretch"):
            users = load_users()
            normalized_email = signup_email.strip().lower()
            normalized_username = signup_username.strip().lower()
            username_exists = any(
                user.get("username", "").lower() == normalized_username
                for user in users
            )
            email_exists = any(
                user.get("email", "").lower() == normalized_email
                for user in users
            )

            if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized_email):
                st.error("Enter a valid email address.")
            elif not re.fullmatch(r"[A-Za-z0-9_.-]{3,30}", signup_username.strip()):
                st.error("Username must be 3-30 characters using letters, numbers, _, ., or -.")
            elif len(signup_password) < 8:
                st.error("Password must be at least 8 characters.")
            elif signup_password != signup_confirmation:
                st.error("Passwords do not match.")
            elif username_exists or email_exists:
                st.error("That username or email is already registered.")
            else:
                salt, password_hash = hash_password(signup_password)
                users.append(
                    {
                        "email": normalized_email,
                        "username": signup_username.strip(),
                        "salt": salt,
                        "password_hash": password_hash,
                        "created_at": datetime.now().isoformat(),
                    }
                )
                save_users(users)
                st.session_state.authenticated_user = signup_username.strip()
                st.rerun()

    with reset_tab:
        reset_username = st.text_input("Username", key="reset_username")
        reset_email = st.text_input("Registered email", key="reset_email")
        reset_password = st.text_input(
            "New password",
            type="password",
            key="reset_password",
        )
        reset_confirmation = st.text_input(
            "Confirm new password",
            type="password",
            key="reset_confirmation",
        )

        if st.button("Reset password", type="primary", width="stretch"):
            users = load_users()
            normalized_username = reset_username.strip().lower()
            normalized_email = reset_email.strip().lower()
            user = next(
                (
                    saved_user
                    for saved_user in users
                    if saved_user.get("username", "").lower()
                    == normalized_username
                    and saved_user.get("email", "").lower()
                    == normalized_email
                ),
                None,
            )

            if not user:
                st.error("The username and email do not match a registered account.")
            elif len(reset_password) < 8:
                st.error("Password must be at least 8 characters.")
            elif reset_password != reset_confirmation:
                st.error("Passwords do not match.")
            else:
                salt, password_hash = hash_password(reset_password)
                user["salt"] = salt
                user["password_hash"] = password_hash
                save_users(users)
                st.success("Password reset successfully. You can now sign in.")

    st.stop()


# =========================================================
# GROQ MODEL CHECK
# =========================================================

def get_available_models(client):
    """
    Get models available to the current Groq API key.
    """

    try:
        models = client.models.list()

        model_ids = []

        for model in models.data:
            if hasattr(model, "id"):
                model_ids.append(model.id)

        return model_ids

    except Exception:
        return []


# =========================================================
# PDF GENERATION
# =========================================================

def generate_pdf(result_text, idea_name):
    buffer = BytesIO()
    styles = getSampleStyleSheet()
    title_style = styles["Title"]
    title_style.alignment = TA_CENTER
    body_style = styles["BodyText"]
    body_style.leading = 18

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
    )

    story = [
        Paragraph("Market Mind Pro", title_style),
        Spacer(1, 18),
        Paragraph(html.escape(idea_name), styles["Heading2"]),
        Spacer(1, 12),
    ]

    for line in result_text.splitlines():
        content = html.escape(line) or "&nbsp;"
        story.append(Paragraph(content, body_style))
        story.append(Spacer(1, 6))

    document.build(story)
    return buffer.getvalue()


# =========================================================
# MARKET SIZE CHART
# =========================================================

def create_market_chart(result_text):

    market_numbers = re.findall(
        r"\$[\d,.]+\s*(?:million|billion|trillion|M|B|T)?",
        result_text,
        flags=re.IGNORECASE
    )

    if len(market_numbers) >= 3:

        values = []

        for value in market_numbers[:3]:

            clean_value = value.replace("$", "")
            clean_value = clean_value.replace(",", "")

            multiplier = 1

            if re.search(
                r"billion|B",
                clean_value,
                re.IGNORECASE
            ):
                multiplier = 1_000_000_000

            elif re.search(
                r"million|M",
                clean_value,
                re.IGNORECASE
            ):
                multiplier = 1_000_000

            elif re.search(
                r"trillion|T",
                clean_value,
                re.IGNORECASE
            ):
                multiplier = 1_000_000_000_000

            number = re.sub(
                r"[^0-9.]",
                "",
                clean_value
            )

            try:
                values.append(
                    float(number) * multiplier
                )
            except:
                pass

        if len(values) >= 3:

            df = pd.DataFrame(
                {
                    "Segment": [
                        "TAM",
                        "SAM",
                        "SOM"
                    ],
                    "Value": values[:3]
                }
            )

            st.bar_chart(
                df.set_index("Segment")
            )


# =========================================================
# COMPETITOR TABLE
# =========================================================

def competitor_table(result_text):

    pattern = (
        r"(?:Top 3 Competitors|"
        r"Top 3 Competitors\s*\:)"
        r"\s*(.*)"
    )

    comps = re.findall(
        pattern,
        result_text,
        flags=re.IGNORECASE
    )

    if comps:

        comp_text = comps[0]

        comp_list = [
            c.strip()
            for c in re.split(
                r",|\n",
                comp_text
            )
            if c.strip()
        ]

        # Remove markdown formatting
        comp_list = [
            re.sub(
                r"[*#\-]",
                "",
                c
            ).strip()
            for c in comp_list
        ]

        comp_list = comp_list[:3]

        if comp_list:

            df = pd.DataFrame(
                {
                    "Competitor": comp_list,
                    "Feature": ["Analyze"] * len(comp_list),
                    "Pricing": ["Research Required"] * len(comp_list),
                }
            )

            st.dataframe(
                df,
                    width="stretch",
                hide_index=True
            )


# =========================================================
# SIDEBAR
# =========================================================

st.sidebar.title("⚙️ Settings")

st.sidebar.caption(f"Signed in as {st.session_state.authenticated_user}")

if st.sidebar.button("Log out", width="stretch"):
    st.session_state.authenticated_user = None
    st.rerun()

st.sidebar.markdown(
    "### 🤖 Groq AI"
)

model_choice = st.sidebar.text_input(
    "Groq Model ID",
    value=DEFAULT_MODEL,
    placeholder="Enter a valid Groq model ID",
    help=(
        "Recommended: openai/gpt-oss-20b"
    )
)

if not model_choice.strip():
    model_choice = DEFAULT_MODEL

temperature = st.sidebar.slider(
    "Creativity Level",
    0.0,
    1.0,
    0.7
)

investor_mode = st.sidebar.checkbox(
    "🚀 Investor Pitch Mode"
)


# =========================================================
# API KEY
# =========================================================

use_env_key = st.sidebar.checkbox(
    "Use API Key from .env",
    value=bool(env_api_key)
)

if use_env_key and env_api_key:

    api_key = env_api_key

    st.sidebar.success(
        "✅ API key loaded from .env"
    )

else:

    if use_env_key and not env_api_key:

        st.sidebar.warning(
            "No GROQ_API_KEY found in .env"
        )

    api_key = st.sidebar.text_input(
        "Enter Groq API Key",
        type="password",
        placeholder="Enter your Groq API Key",
        key="api_key_input"
    )


# =========================================================
# MAIN HEADER
# =========================================================

st.title("🧠 Market Mind Pro")

st.markdown(
    """
    ### 🚀 AI-Powered Startup Market Analysis

    Enter your business idea and generate an AI-powered
    market research report.
    """
)

st.divider()


# =========================================================
# BUSINESS IDEA
# =========================================================

idea = st.text_input(
    "💡 Enter your business idea",
    placeholder="Example: AI Fitness Coach App"
)


# =========================================================
# ANALYZE BUTTON
# =========================================================

if st.button(
    "🔍 Analyze Market",
    type="primary",
        width="stretch"
):

    if not idea.strip():

        st.error(
            "Please enter a business idea."
        )

    elif not api_key.strip():

        st.error(
            "❌ Groq API key is missing."
        )

    else:

        reports = load_reports()

        cached = next(
            (
                report
                for report in reports
                if report.get("idea", "").lower()
                == idea.lower()
            ),
            None
        )

        if cached:

            st.info(
                "📦 Using cached report for this idea."
            )

            result = cached.get(
                "result",
                ""
            )

        else:

            with st.spinner(
                "🤖 AI is analyzing your market..."
            ):

                try:

                    # -----------------------------------------
                    # CREATE GROQ CLIENT
                    # -----------------------------------------

                    client = Groq(
                        api_key=api_key
                    )

                    # -----------------------------------------
                    # CHECK MODEL ACCESS
                    # -----------------------------------------

                    available_models = (
                        get_available_models(client)
                    )

                    if available_models:

                        if model_choice not in available_models:

                            st.warning(
                                f"⚠️ The model `{model_choice}` "
                                "is not available to this API key."
                            )

                            fallback_models = [
                                "openai/gpt-oss-20b",
                                "llama-3.3-70b-versatile",
                                "llama-3.1-8b-instant"
                            ]

                            fallback = next(
                                (
                                    m
                                    for m in fallback_models
                                    if m in available_models
                                ),
                                None
                            )

                            if fallback:

                                st.info(
                                    f"Using available model: `{fallback}`"
                                )

                                model_to_use = fallback

                            else:

                                st.error(
                                    "❌ No suitable Groq model "
                                    "is available for this API key."
                                )

                                st.stop()

                        else:

                            model_to_use = model_choice

                    else:

                        # If model listing is unavailable,
                        # try the selected model directly.
                        model_to_use = model_choice

                    # -----------------------------------------
                    # PROMPT
                    # -----------------------------------------

                    prompt = f"""
You are an expert startup analyst and business consultant.

Analyze this business idea:

BUSINESS IDEA:
{idea}

Create a professional startup market research report.

IMPORTANT:
- Give realistic estimates.
- Clearly label estimates as estimates.
- Do not invent exact factual claims.
- Use simple language.
- Use headings exactly as requested.
- Make the report useful for a college project and startup presentation.

Provide the following sections:

1. Market Overview

2. Target Audience

3. Market Size

Provide:
TAM: $ amount
SAM: $ amount
SOM: $ amount

4. Top 3 Competitors

Write exactly:
Top 3 Competitors: Competitor 1, Competitor 2, Competitor 3

5. Key Trends

Give 3 important trends.

6. Opportunities

Give 3 opportunities.

7. Challenges

Give 3 challenges.

8. Go-To-Market Strategy

Explain the strategy step by step.

9. SWOT Analysis

Strengths:
Weaknesses:
Opportunities:
Threats:

10. Startup Scorecard

Use exactly this format:

Market Demand: X/10
Competition: X/10
Profit Potential: X/10
Scalability: X/10
Risk Level: X/10

11. Suggested Business Models

Give 2-3 suitable business models.

12. AI Confidence Score

Use exactly:

AI Confidence Score: X

where X is between 1 and 100.
"""

                    if investor_mode:

                        prompt += """

13. 1-Minute Investor Pitch

Include:
- Problem
- Solution
- Target Market
- Business Model
- Why Now
- Competitive Advantage
- Funding Ask
"""

                    # -----------------------------------------
                    # GROQ REQUEST
                    # -----------------------------------------

                    response = (
                        client.chat.completions.create(
                            model=model_to_use,
                            messages=[
                                {
                                    "role": "system",
                                    "content": (
                                        "You are a professional "
                                        "startup market analyst."
                                    )
                                },
                                {
                                    "role": "user",
                                    "content": prompt
                                }
                            ],
                            temperature=temperature,
                            max_tokens=4000,
                        )
                    )

                    result = (
                        response
                        .choices[0]
                        .message
                        .content
                    )

                    # -----------------------------------------
                    # SAVE REPORT
                    # -----------------------------------------

                    reports.append(
                        {
                            "idea": idea,
                            "result": result,
                            "created_at":
                                datetime.now().isoformat()
                        }
                    )

                    save_reports(
                        reports
                    )

                    st.success(
                        "✅ Market analysis completed!"
                    )

                except Exception as err:

                    error_text = str(err)

                    st.error(
                        "❌ Analysis failed"
                    )

                    st.code(
                        error_text
                    )

                    if (
                        "model_not_found"
                        in error_text.lower()
                        or "404"
                        in error_text
                    ):

                        st.warning(
                            """
The Groq API key cannot use the selected
model.

Try:

openai/gpt-oss-20b

or check the model permissions for your
Groq project.
"""
                        )

                    result = ""

        # -----------------------------------------
        # SAVE SESSION RESULT
        # -----------------------------------------

        if result:

            st.session_state.result = result

            st.session_state.idea = idea


# =========================================================
# DISPLAY REPORT
# =========================================================

if st.session_state.result:

    st.divider()

    st.header(
        f"📊 Market Analysis: {st.session_state.idea}"
    )

    st.markdown(
        st.session_state.result
    )

    # =====================================================
    # SCORECARD
    # =====================================================

    st.markdown(
        "## 📈 Startup Scorecard"
    )

    scores = re.findall(
        r"(?:Market Demand|Competition|"
        r"Profit Potential|Scalability|Risk Level)"
        r"\s*:\s*(\d+)\s*/\s*10",
        st.session_state.result,
        flags=re.IGNORECASE
    )

    labels = [
        "Market Demand",
        "Competition",
        "Profit Potential",
        "Scalability",
        "Risk Level"
    ]

    if scores:

        columns = st.columns(5)

        for i, score in enumerate(
            scores[:5]
        ):

            with columns[i]:

                st.metric(
                    labels[i],
                    f"{score}/10"
                )


    # =====================================================
    # MARKET SIZE
    # =====================================================

    st.markdown(
        "## 💰 Market Size"
    )

    create_market_chart(
        st.session_state.result
    )


    # =====================================================
    # COMPETITORS
    # =====================================================

    st.markdown(
        "## 🏢 Competitor Comparison"
    )

    competitor_table(
        st.session_state.result
    )


    # =====================================================
    # RISK
    # =====================================================

    st.markdown(
        "## ⚠️ Risk Level"
    )

    risk_match = re.search(
        r"Risk Level\s*:\s*(\d+)\s*/\s*10",
        st.session_state.result,
        flags=re.IGNORECASE
    )

    if risk_match:

        risk_score = int(
            risk_match.group(1)
        )

        if risk_score <= 3:

            risk_text = "🟢 Low Risk"

        elif risk_score <= 7:

            risk_text = "🟡 Medium Risk"

        else:

            risk_text = "🔴 High Risk"

        st.markdown(
            f"### {risk_text}"
        )

        st.write(
            f"Risk Score: {risk_score}/10"
        )


    # =====================================================
    # AI CONFIDENCE
    # =====================================================

    st.markdown(
        "## 🤖 AI Confidence Score"
    )

    confidence_match = re.search(
        r"AI Confidence Score\s*:\s*(\d+)",
        st.session_state.result,
        flags=re.IGNORECASE
    )

    if confidence_match:

        confidence_value = int(
            confidence_match.group(1)
        )

        confidence_value = min(
            max(confidence_value, 0),
            100
        )

        st.progress(
            confidence_value / 100
        )

        st.write(
            f"AI Confidence: {confidence_value}%"
        )


    # =====================================================
    # PDF DOWNLOAD
    # =====================================================

    st.markdown(
        "## 📄 Download Report"
    )

    pdf_bytes = generate_pdf(
        st.session_state.result,
        st.session_state.idea
    )

    if pdf_bytes:

        safe_filename = re.sub(
            r"[^a-zA-Z0-9_-]",
            "_",
            st.session_state.idea
        )

        st.download_button(
            label="📥 Download Report as PDF",
            data=pdf_bytes,
            file_name=(
                f"{safe_filename}_Market_Report.pdf"
            ),
            mime="application/pdf",
                width="stretch"
        )


# =========================================================
# PREVIOUS REPORTS
# =========================================================

st.divider()

st.subheader(
    "📜 Previous Reports"
)

reports = load_reports()

if reports:

    for report in sorted(
        reports,
        key=lambda r: r.get(
            "created_at",
            ""
        ),
        reverse=True
    ):

        with st.expander(
            f"📄 {report.get('idea', 'Unknown Idea')}"
        ):

            st.caption(
                report.get(
                    "created_at",
                    ""
                )
            )

            st.write(
                report.get(
                    "result",
                    ""
                )
            )

else:

    st.info(
        "No previous reports yet."
    )


# =========================================================
# FOOTER
# =========================================================

st.markdown("---")

st.caption(
    "🧠 Market Mind Pro | AI Startup Market Analysis"
)