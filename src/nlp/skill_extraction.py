from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, List, Dict, Set, Tuple

import spacy
from spacy.matcher import PhraseMatcher
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, Row
from src.common.config import settings


# ---------- Config ----------
SKILLS_CSV = Path("data/skills/skills_list.csv")
EXTRACTOR_VERSION = "rule_v1"


def load_skills(csv_path: Path) -> List[str]:
    if not csv_path.exists():
        raise FileNotFoundError(f"Skills CSV not found at {csv_path}")
    skills: List[str] = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        if "skill" not in r.fieldnames:
            raise ValueError("CSV must have a 'skill' column")
        for row in r:
            s = (row["skill"] or "").strip()
            if s:
                skills.append(s)
    # de-dup while preserving order
    seen: Set[str] = set()
    uniq: List[str] = []
    for s in skills:
        key = s.lower()
        if key not in seen:
            seen.add(key)
            uniq.append(s)
    return uniq


def build_matcher(nlp) -> Tuple[PhraseMatcher, Dict[int, str]]:
    """Return a PhraseMatcher and map from match_id->skill string."""
    vocab_map: Dict[int, str] = {}
    matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
    skills = load_skills(SKILLS_CSV)
    patterns = []
    for skill in skills:
        doc = nlp.make_doc(skill)
        patterns.append(doc)
    matcher.add("SKILL", patterns)
    # Recreate id->string mapping
    for skill in skills:
        vocab_map[nlp.vocab.strings["SKILL"]] = "SKILL"  # not used per match
    return matcher, {}


def normalize(s: str) -> str:
    """Canonicalize skill strings lightly; keep human-readable."""
    return " ".join(s.split()).strip()


def extract_skills_for_text(nlp, matcher: PhraseMatcher, text_str: str) -> List[str]:
    if not text_str:
        return []
    doc = nlp(text_str)
    matches = matcher(doc)
    found: Set[str] = set()
    for _, start, end in matches:
        span = doc[start:end].text
        found.add(normalize(span))
    return sorted(found)


def fetch_jobs(engine: Engine) -> List[Row]:
    with engine.connect() as conn:
        # Only pull columns we need
        rows = conn.execute(
            text("SELECT job_id, description_raw FROM jobs ORDER BY job_id ASC")
        ).fetchall()
    return rows


def load_existing_skills(engine: Engine) -> Dict[str, int]:
    """Return {skill_norm_lower: skill_id} cache."""
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT skill_id, COALESCE(skill_norm, skill_raw) AS s FROM skills")
        ).fetchall()
    return {normalize(r.s).lower(): r.skill_id for r in rows}


def upsert_skill(engine: Engine, cache: Dict[str, int], skill_raw: str) -> int:
    """Insert into skills if missing; return skill_id."""
    norm = normalize(skill_raw)
    key = norm.lower()
    if key in cache:
        return cache[key]
    # Insert new skill
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                INSERT INTO skills (skill_raw, skill_norm, confidence, extractor_version)
                VALUES (:skill_raw, :skill_norm, :conf, :ver)
                RETURNING skill_id
                """
            ),
            {"skill_raw": skill_raw, "skill_norm": norm, "conf": None, "ver": EXTRACTOR_VERSION},
        ).mappings().first()
        skill_id = int(row["skill_id"])
    cache[key] = skill_id
    return skill_id


def link_job_skill(engine: Engine, job_id: int, skill_id: int) -> None:
    """Insert into jobs_skills; rely on PK(job_id, skill_id) to avoid dupes."""
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO jobs_skills (job_id, skill_id)
                VALUES (:job_id, :skill_id)
                ON CONFLICT DO NOTHING
                """
            ),
            {"job_id": job_id, "skill_id": skill_id},
        )


def main() -> None:
    print("Loading spaCy model...")
    nlp = spacy.load("en_core_web_sm", disable=["ner", "tagger", "lemmatizer"])
    matcher, _ = build_matcher(nlp)

    engine = create_engine(settings.sqlalchemy_url)
    print("Fetching jobs...")
    jobs = fetch_jobs(engine)
    print(f"Found {len(jobs)} job(s). Extracting skills...")

    cache = load_existing_skills(engine)
    total_links = 0

    for r in jobs:
        job_id = int(r.job_id)
        desc = r.description_raw or ""
        skills = extract_skills_for_text(nlp, matcher, desc)
        if not skills:
            continue
        for s in skills:
            sid = upsert_skill(engine, cache, s)
            link_job_skill(engine, job_id, sid)
            total_links += 1

    print(f"Done. Linked {total_links} job-skill pair(s).")


if __name__ == "__main__":
    main()
