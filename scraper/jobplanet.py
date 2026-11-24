from __future__ import annotations

import logging
import time

import requests

from .models import JobPosting, TARGET_REGIONS, extract_regions, is_marketing_job

logger = logging.getLogger(__name__)

API_URL = "https://www.jobplanet.co.kr/api/v3/job/postings"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "ko-KR,ko;q=0.9",
}


def fetch_jobplanet() -> list[JobPosting]:
    """Fetch marketing job postings from JobPlanet JSON API (includes company rating)."""
    results: list[JobPosting] = []
    seen_ids: set[int] = set()
    session = requests.Session()
    session.headers.update(HEADERS)

    queries = [f"마케팅 {city}" for city in TARGET_REGIONS] + ["마케터"]
    for q in queries:
        for page in range(1, 3):
            params = {
                "order_by": "recent",
                "page": page,
                "page_size": 30,
                "query": q,
            }
            try:
                resp = session.get(API_URL, params=params, timeout=15)
                resp.raise_for_status()
                payload = resp.json()
            except Exception as exc:
                logger.warning("[잡플래닛] '%s' p%d 실패: %s", q, page, exc)
                break

            recruits = (payload.get("data") or {}).get("recruits") or []
            if not recruits:
                break

            for item in recruits:
                rid = item.get("id")
                if not rid or rid in seen_ids:
                    continue

                title = item.get("title", "")
                comp = item.get("company") or {}
                company = comp.get("name", "")
                rating = comp.get("grade")

                cities = item.get("cities") or []
                if isinstance(cities, list):
                    city_names = [
                        c.get("name", "") if isinstance(c, dict) else str(c)
                        for c in cities
                    ]
                    location = ", ".join(c for c in city_names if c)
                else:
                    location = ""
                if not location:
                    location = comp.get("city_name", "")

                occ = item.get("occupation_names") or {}
                tags = []
                if isinstance(occ, dict):
                    tags.extend(occ.get("level1") or [])
                    tags.extend(occ.get("level2") or [])

                regions = extract_regions(location, title)
                if not regions:
                    continue
                if not is_marketing_job(title, tags):
                    continue

                seen_ids.add(rid)
                url = item.get("external_url") or f"https://www.jobplanet.co.kr/job/search?posting_ids%5B%5D={rid}"
                exp = item.get("career_text") or (item.get("annual") or {}).get("text", "")
                deadline = item.get("deadline_message") or ""

                job = JobPosting(
                    platform="잡플래닛",
                    title=title,
                    company=company,
                    location=location,
                    url=url,
                    regions=regions,
                    salary_raw="",
                    experience=exp,
                    deadline=deadline,
                    tags=tags[:5],
                    company_rating=float(rating) if rating else None,
                ).finalize()
                results.append(job)

            time.sleep(0.3)

    logger.info("[잡플래닛] 총 %d건 수집 완료", len(results))
    return results
