from __future__ import annotations
import os
import pandas as pd
from datetime import date
from sqlalchemy import create_engine, text

import streamlit as st
import plotly.express as px

# ---------- App setup ----------
st.set_page_config(page_title="Job Market Insights", layout="wide")
st.title("Job Market Insights & Skills Gap Analysis")

# DB
from src.common.config import settings
engine = create_engine(settings.sqlalchemy_url)

# ---------- Utility cache loaders ----------
@st.cache_data(ttl=120)
def load_df(sql: str, parse_month=False):
    with engine.connect() as c:
        df = pd.read_sql(text(sql), c)
    if parse_month and "month" in df.columns:
        df["month"] = pd.to_datetime(df["month"])
    return df

@st.cache_data(ttl=120)
def load_skill_counts():
    return load_df("""
        SELECT skill, job_count, last_seen
        FROM mv_skill_counts
        ORDER BY job_count DESC, skill
    """)

@st.cache_data(ttl=120)
def load_skill_trends():
    return load_df("""
        SELECT month, skill, job_count
        FROM mv_monthly_skill_counts
    """, parse_month=True)

@st.cache_data(ttl=120)
def load_salary_trends():
    return load_df("""
        SELECT month, skill, avg_min, avg_max, n
        FROM mv_monthly_salary_by_skill
    """, parse_month=True)

@st.cache_data(ttl=120)
def load_country_trends():
    return load_df("""
        SELECT month, country, job_count
        FROM mv_monthly_jobs_by_country
    """, parse_month=True)

@st.cache_data(ttl=120)
def load_movers():
    return load_df("""
        SELECT month, skill, job_count, prev_job_count, mom_growth_pct
        FROM mv_skill_mom_growth
        WHERE mom_growth_pct IS NOT NULL
    """, parse_month=True)

@st.cache_data(ttl=120)
def load_locations_points():
    return load_df("""
        SELECT job_id, city, state, country, lat, lon
        FROM locations
        WHERE lat IS NOT NULL AND lon IS NOT NULL
    """)

@st.cache_data(ttl=120)
def load_salary_by_skill(min_samples: int = 3):
    # base tables (works without MV)
    return load_df(f"""
        SELECT COALESCE(s.skill_norm, s.skill_raw) AS skill,
               AVG(c.min) AS avg_min,
               AVG(c.max) AS avg_max,
               COUNT(*)   AS n
        FROM skills s
        JOIN jobs_skills js ON js.skill_id = s.skill_id
        JOIN compensation c ON c.job_id = js.job_id
        WHERE c.min IS NOT NULL AND c.max IS NOT NULL
        GROUP BY COALESCE(s.skill_norm, s.skill_raw)
        HAVING COUNT(*) >= {min_samples}
        ORDER BY n DESC, skill
    """)

# ---------- Sidebar: global filters & navigation ----------
st.sidebar.title("Navigation")
page = st.sidebar.radio(
    "Go to",
    ["Overview", "Skill Trends", "Salary by Skill", "Geo Map", "Top Movers"],
)

# Global: date range (based on trends table)
tr_all = load_skill_trends()
if not tr_all.empty:
    mind, maxd = tr_all["month"].min().date(), tr_all["month"].max().date()
    dr = st.sidebar.date_input(
        "Date range (month-based)",
        value=(mind, maxd),
        min_value=mind,
        max_value=maxd,
    )
else:
    dr = (date.today(), date.today())

# Global: country filter for trend + map
ct_all = load_country_trends()
countries_all = sorted(ct_all["country"].dropna().unique().tolist()) if not ct_all.empty else []
sel_countries = st.sidebar.multiselect(
    "Countries", options=countries_all, default=countries_all[:5] if countries_all else []
)

# Global: skill selection helper
sc = load_skill_counts()
skills_all = sc["skill"].tolist() if not sc.empty else []
default_skills = skills_all[:5] if len(skills_all) >= 5 else skills_all

# Helper to apply date filter
def filter_by_date(df: pd.DataFrame, col="month"):
    if df.empty or col not in df.columns:
        return df
    lo, hi = pd.to_datetime(dr[0]), pd.to_datetime(dr[1])
    return df[(df[col] >= lo) & (df[col] <= hi)]

# ---------- Pages ----------

if page == "Overview":
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Top Skills (overall)")
        if sc.empty:
            st.info("No skills found. Run extraction & refresh analytics.")
        else:
            top_n = st.slider("Top N", 5, 50, 20, step=5)
            fig = px.bar(sc.head(top_n), x="skill", y="job_count", title=f"Top {top_n} Skills")
            fig.update_xaxes(tickangle=45)
            st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.subheader("Jobs by Country (most recent month in range)")
        ct = filter_by_date(ct_all.copy())
        if not sel_countries:
            ct = ct
        else:
            ct = ct[ct["country"].isin(sel_countries)]
        if ct.empty:
            st.info("No country data in selected range.")
        else:
            recent = ct["month"].max()
            snap = ct[ct["month"] == recent].sort_values("job_count", ascending=False).head(20)
            fig2 = px.bar(snap, x="country", y="job_count", title=f"Jobs by Country — {recent.date()}")
            fig2.update_xaxes(tickangle=45)
            st.plotly_chart(fig2, use_container_width=True)
    st.caption("Tip: Adjust the date range and country filters in the sidebar.")

elif page == "Skill Trends":
    st.subheader("Monthly Job Counts by Skill")
    df = filter_by_date(tr_all.copy())
    if df.empty:
        st.info("No trend data in selected date range.")
    else:
        pick = st.multiselect("Select skills", options=skills_all, default=default_skills, max_selections=8)
        if pick:
            sub = df[df["skill"].isin(pick)].sort_values("month")
            fig = px.line(sub, x="month", y="job_count", color="skill", markers=True)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Select at least one skill.")

elif page == "Salary by Skill":
    st.subheader("Average Salary by Skill")
    min_samples = st.slider("Minimum postings per skill", 1, 50, 3, step=1)
    show_top = st.slider("Show top N by sample size", 5, 50, 20, step=5)
    sal = load_salary_by_skill(min_samples=min_samples)
    if sal.empty:
        st.info("No parsed salary data. Run salary enrichment.")
    else:
        sal = sal.sort_values(["n", "skill"], ascending=[False, True]).head(show_top)
        col1, col2 = st.columns(2)
        with col1:
            fig_sal = px.bar(sal, x="skill", y="avg_max", hover_data=["avg_min", "n"],
                             title="Average Max Salary by Skill")
            fig_sal.update_xaxes(tickangle=45)
            st.plotly_chart(fig_sal, use_container_width=True)
        with col2:
            sal_long = sal.melt(id_vars=["skill", "n"],
                                value_vars=["avg_min", "avg_max"],
                                var_name="band", value_name="salary")
            fig_band = px.line(sal_long.sort_values(["skill","band"]),
                               x="skill", y="salary", color="band", markers=True,
                               title="Average Min/Max Salary")
            fig_band.update_xaxes(tickangle=45)
            st.plotly_chart(fig_band, use_container_width=True)

elif page == "Geo Map":
    st.subheader("Jobs Map (lat/lon)")
    locdf = load_locations_points()
    if locdf.empty:
        st.info("No geocoded locations. Run location enrichment.")
    else:
        if sel_countries:
            locdf = locdf[locdf["country"].isin(sel_countries)]
        locdf["label"] = locdf[["city","state","country"]].fillna("").agg(", ".join, axis=1)\
                            .str.strip(", ").replace("", "Unknown")
        fig_map = px.scatter_geo(
            locdf, lat="lat", lon="lon", hover_name="label",
            projection="natural earth", title="Job Locations"
        )
        fig_map.update_geos(showcountries=True, showcountriesframe=True, resolution=50)
        st.plotly_chart(fig_map, use_container_width=True)
        st.caption("Tip: Filter countries from the sidebar.")

elif page == "Top Movers":
    st.subheader("Top Rising & Falling Skills (MoM %)")
    mv = load_movers()
    mv = filter_by_date(mv.copy())
    if mv.empty:
        st.info("No movers in selected range (need at least 2 months).")
    else:
        recent_month = mv["month"].max()
        st.caption(f"Most recent month in range: {recent_month.date()}")
        m_recent = mv[mv["month"] == recent_month]
        risers = m_recent.sort_values("mom_growth_pct", ascending=False).head(10)
        fallers = m_recent.sort_values("mom_growth_pct", ascending=True).head(10)
        c1, c2 = st.columns(2)
        with c1:
            st.write("Top Rising Skills")
            st.dataframe(risers[["skill", "job_count", "prev_job_count", "mom_growth_pct"]])
        with c2:
            st.write("Top Falling Skills")
            st.dataframe(fallers[["skill", "job_count", "prev_job_count", "mom_growth_pct"]])
