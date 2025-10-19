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

@st.cache_data(ttl=60)
def load_salary_by_skill(min_samples: int = 3):
    # Uses base tables so it works even if MVs aren’t created
    q = """
    SELECT
        COALESCE(s.skill_norm, s.skill_raw) AS skill,
        AVG(c.min) AS avg_min,
        AVG(c.max) AS avg_max,
        COUNT(*)   AS n
    FROM skills s
    JOIN jobs_skills js ON js.skill_id = s.skill_id
    JOIN compensation c ON c.job_id = js.job_id
    WHERE c.min IS NOT NULL AND c.max IS NOT NULL
    GROUP BY COALESCE(s.skill_norm, s.skill_raw)
    HAVING COUNT(*) >= :min_samples
    ORDER BY n DESC, skill
    """
    with engine.connect() as c:
        return pd.read_sql(text(q), c, params={"min_samples": min_samples})

@st.cache_data(ttl=60)
def load_locations_points():
    # Pulls points for the map; requires lat/lon (geocoded or provided)
    q = """
    SELECT job_id, city, state, country, lat, lon
    FROM locations
    WHERE lat IS NOT NULL AND lon IS NOT NULL
    """
    with engine.connect() as c:
        return pd.read_sql(text(q), c)

st.subheader("Salary by Skill")

with st.expander("Options", expanded=True):
    min_samples = st.slider("Minimum postings per skill (to include)", 1, 50, 3, step=1)
    show_top = st.slider("Show top N skills by sample size", 5, 50, 20, step=5)

sal = load_salary_by_skill(min_samples=min_samples)
if sal.empty:
    st.info("No parsed salary data found. Run the enrichment step (make enrich-salary) and refresh analytics.")
else:
    sal = sal.sort_values(["n", "skill"], ascending=[False, True]).head(show_top)
    st.write(f"Showing {len(sal)} skills (min samples ≥ {min_samples})")

    # Bar: average max salary per skill
    fig_sal = px.bar(
        sal,
        x="skill",
        y="avg_max",
        hover_data=["avg_min", "n"],
        title="Average Max Salary by Skill",
    )
    fig_sal.update_xaxes(tickangle=45)
    st.plotly_chart(fig_sal, use_container_width=True)

    # Optional: error bars (min/max band) via line markers
    sal_long = sal.melt(id_vars=["skill", "n"], value_vars=["avg_min", "avg_max"], var_name="kind", value_name="salary")
    fig_band = px.line(
        sal_long.sort_values(["skill", "kind"]),
        x="skill", y="salary", color="kind", markers=True,
        title="Average Min/Max Salary by Skill"
    )
    fig_band.update_xaxes(tickangle=45)
    st.plotly_chart(fig_band, use_container_width=True)

st.subheader("Jobs Map (lat/lon)")

locdf = load_locations_points()
if locdf.empty:
    st.info("No geocoded locations with lat/lon found. Run the location enrichment step (make enrich-locations).")
else:
    # Optional: filters
    with st.expander("Filters", expanded=False):
        countries = sorted([c for c in locdf["country"].dropna().unique().tolist()])
        sel_countries = st.multiselect("Filter by country", options=countries, default=countries[:5] if countries else [])
        if sel_countries:
            locdf = locdf[locdf["country"].isin(sel_countries)]

    # Fallbacks for display text
    locdf["label"] = locdf[["city", "state", "country"]].fillna("").agg(", ".join, axis=1).str.strip(", ").replace("", "Unknown")

    # Use scatter_geo (no Mapbox token required)
    fig_map = px.scatter_geo(
        locdf,
        lat="lat",
        lon="lon",
        hover_name="label",
        projection="natural earth",
        title="Job Locations",
    )
    # Nice zoomed-out view
    fig_map.update_geos(showcountries=True, showcountriesframe=True, resolution=50)
    st.plotly_chart(fig_map, use_container_width=True)

    st.caption("Tip: This uses lat/lon from the 'locations' table. For more coverage, ensure geocoding is enabled in Step 4.")
