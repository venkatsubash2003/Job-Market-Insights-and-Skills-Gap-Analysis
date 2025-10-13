CREATE TABLE IF NOT EXISTS jobs (
  job_id SERIAL PRIMARY KEY,
  title_raw TEXT NOT NULL,
  description_raw TEXT,
  company TEXT,
  source TEXT,
  post_date DATE,
  location_raw TEXT,
  salary_raw TEXT,
  url TEXT,
  collected_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS skills (
  skill_id SERIAL PRIMARY KEY,
  skill_raw TEXT NOT NULL,
  skill_norm TEXT,
  confidence NUMERIC,
  extractor_version TEXT,
  created_at TIMESTAMP DEFAULT NOW()
); 

CREATE TABLE IF NOT EXISTS jobs_skills (
  job_id INT REFERENCES jobs(job_id) ON DELETE CASCADE,
  skill_id INT REFERENCES skills(skill_id) ON DELETE CASCADE,
  PRIMARY KEY (job_id, skill_id)
);

CREATE TABLE IF NOT EXISTS compensation (
  job_id INT PRIMARY KEY REFERENCES jobs(job_id) ON DELETE CASCADE,
  min NUMERIC,
  max NUMERIC,
  currency TEXT,
  period TEXT,
  parsed_confidence NUMERIC
);

CREATE TABLE IF NOT EXISTS locations (
  job_id INT PRIMARY KEY REFERENCES jobs(job_id) ON DELETE CASCADE,
  city TEXT,
  state TEXT,
  country TEXT,
  lat NUMERIC,
  lon NUMERIC,
  geocode_confidence NUMERIC
);

CREATE TABLE IF NOT EXISTS metadata (
  run_id TEXT PRIMARY KEY,
  git_sha TEXT,
  data_version TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);
