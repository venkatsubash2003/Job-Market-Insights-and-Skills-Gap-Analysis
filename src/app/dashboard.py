from __future__ import annotations
import os
import pandas as pd
from sqlalchemy import create_engine, text
from src.common.config import settings

import streamlit as st
import plotly.express as px

st.set_page_config(page_title="Job Market Insights", layout="wide")

# ---------- DB ----------
engine = create_engine(settings.sqlalchemy_url)

@st.cache_data(ttl=60)
def load_skill_counts():
    with engine.connect() as c:
        return pd.read_sql("SELECT skill, job_count, last_seen FROM mv_skill_counts ORDER BY job_count DESC, skill", c)

@st.cache_data(ttl=60)
def load_monthly():
    with engine.connect() as c:
        df = pd.read_sql(
            "SELECT month, skill, job_count FROM mv_monthly_skill_counts",
            c,
            parse_dates=["month"],
        )
        return df

@st.cache_data(ttl=60)
def load_pairs():
    with engine.connect() as c:
        return pd.read_sql(
            "SELECT skill_a, skill_b, pair_count FROM mv_skill_cooccurrence ORDER BY pair_count DESC",
            c,
        )

st.title("Job Market Insights & Skills Gap Analysis — Analytics")

# ---------- Top Skills ----------
st.subheader("Top Skills (overall)")
skill_counts = load_skill_counts()
top_n = st.slider("Show top N skills", 5, 50, 20, step=5)
fig_top = px.bar(
    skill_counts.head(top_n),
    x="skill", y="job_count",
    title=f"Top {top_n} Skills by Job Count",
)
fig_top.update_xaxes(tickangle=45)
st.plotly_chart(fig_top, use_container_width=True)

# ---------- Trends ----------
st.subheader("Monthly Trends")
monthly = load_monthly()
skills_available = sorted(monthly["skill"].unique().tolist())
select_skills = st.multiselect(
    "Select skills to plot (up to 8)", options=skills_available, default=skills_available[:5], max_selections=8
)

if select_skills:
    msel = monthly[monthly["skill"].isin(select_skills)].copy()
    msel = msel.sort_values("month")
    fig_trend = px.line(msel, x="month", y="job_count", color="skill", markers=True, title="Monthly Job Counts by Skill")
    st.plotly_chart(fig_trend, use_container_width=True)
else:
    st.info("Select at least one skill to see trend lines.")

# ---------- Co-occurrence ----------
st.subheader("Skill Co-occurrence (Top Pairs)")
pairs = load_pairs()
k = st.slider("Show top K pairs", 10, 100, 30, step=10)
st.dataframe(pairs.head(k))

# Optional: simple network suggestion (textual)
if not pairs.empty:
    st.caption("Tip: Look at pairs with high counts to find common bundles of requirements (e.g., Python + SQL).")

st.divider()
st.caption("Data sources: materialized views mv_skill_counts, mv_monthly_skill_counts, mv_skill_cooccurrence. Refresh with `make analytics-refresh` after new extractions.")
