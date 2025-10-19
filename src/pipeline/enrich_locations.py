from __future__ import annotations
from sqlalchemy import create_engine, text
from src.common.config import settings
from src.parsing.location_norm import normalize_location

# Optional geocoding (disable if you don't need lat/lon yet)
try:
    from geopy.geocoders import Nominatim
    _GEOCODER = Nominatim(user_agent="job-insights-app")
except Exception:
    _GEOCODER = None

def geocode(city, state, country):
    if not _GEOCODER or not (city or state or country):
        return None, None, None
    q = ", ".join([p for p in [city, state, country] if p])
    try:
        loc = _GEOCODER.geocode(q, timeout=10)
        if loc:
            return loc.latitude, loc.longitude, 0.7
    except Exception:
        pass
    return None, None, None

def main():
    eng = create_engine(settings.sqlalchemy_url)
    with eng.begin() as conn:
        rows = conn.execute(text("""
            SELECT job_id, location_raw
            FROM jobs
            WHERE location_raw IS NOT NULL AND location_raw <> ''
        """)).mappings().all()

        upserts = 0
        for r in rows:
            parsed = normalize_location(r["location_raw"])
            lat = lon = gconf = None
            # Try geocoding lightly; you can comment this out if not needed
            lat, lon, gconf = geocode(parsed.city, parsed.state, parsed.country)

            conn.execute(text("""
                INSERT INTO locations (job_id, city, state, country, lat, lon, geocode_confidence)
                VALUES (:job_id, :city, :state, :country, :lat, :lon, :gconf)
                ON CONFLICT (job_id) DO UPDATE SET
                    city = EXCLUDED.city,
                    state = EXCLUDED.state,
                    country = EXCLUDED.country,
                    lat = EXCLUDED.lat,
                    lon = EXCLUDED.lon,
                    geocode_confidence = EXCLUDED.geocode_confidence
            """), {
                "job_id": r["job_id"],
                "city": parsed.city,
                "state": parsed.state,
                "country": parsed.country,
                "lat": lat,
                "lon": lon,
                "gconf": gconf if gconf is not None else parsed.confidence,
            })
            upserts += 1
    print(f"location upserts: {upserts}")

if __name__ == "__main__":
    main()
