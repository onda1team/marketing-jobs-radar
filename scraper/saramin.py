from __future__ import annotations

import logging
import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .models import JobPosting, TARGET_REGIONS, extract_regions, is_marketing_job

logger = logging.getLogger(__name__)

BASE_URL = "https://www.saramin.co.kr"
SEARCH_URL = f"{BASE_URL}/zf_user/search/recruit"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.saramin.co.kr/",
}


def fetch_saramin(pages_per_region: int = 2) -> list[JobPosting]:
    """Fetch marketing job postings from Saramin for the target regions."""
    results: list[JobPosting] = []
    seen_urls: set[str] = set()
    session = requests.Session()
    session.headers.update(HEADERS)

    for city in TARGET_REGIONS:
        for page in range(1, pages_per_region + 1):
            params = {
                "searchType": "search",
                "searchword": f"마케팅 {city}",
                "recruitPage": page,
                "recruitSort": "relation",
                "recruitPageCount": 40,
            }
            try:
                resp = session.get(SEARCH_URL, params=params, timeout=15)
                resp.raise_for_status()
            except Exception as exc:
                logger.warning("[사람인] %s p%d 요청 실패: %s", city, page, exc)
                break

            soup = BeautifulSoup(resp.text, "lxml")
            items = soup.select(".item_recruit")
            if not items:
                break

            for item in items:
                title_el = item.select_one(".job_tit a")
                corp_el = item.select_one(".corp_name a")
                if not title_el or not corp_el:
                    continue

                title = title_el.get_text(" ", strip=True)
                href = title_el.get("href", "")
                url = urljoin(BASE_URL, href)
                if url in seen_urls:
                    continue

                company = corp_el.get_text(" ", strip=True)
                conds = [s.get_text(" ", strip=True) for s in item.select(".job_condition span")]
                location = conds[0] if len(conds) > 0 else ""
                experience = conds[1] if len(conds) > 1 else ""
                employment_type = conds[3] if len(conds) > 3 else ""

                salary_raw = ""
                for c in conds:
                    if any(k in c for k in ("만원", "억원", "연봉", "월급", "시급", "내규", "면접")):
                        salary_raw = c
                        break
                if not salary_raw:
                    # Also check badge / job_sector area
                    for badge in item.select(".area_badge span, .job_meta span"):
                        txt = badge.get_text(" ", strip=True)
                        if re.search(r"(연봉|월급|만원|억원)", txt):
                            salary_raw = txt
                            break

                tags = [a.get_text(" ", strip=True) for a in item.select(".job_sector a") if a.get_text(strip=True)]
                deadline_el = item.select_one(".job_date .date")
                deadline = deadline_el.get_text(" ", strip=True) if deadline_el else ""

                regions = extract_regions(location, title)
                if not regions:
                    continue
                if not is_marketing_job(title, tags):
                    continue

                seen_urls.add(url)
                job = JobPosting(
                    platform="사람인",
                    title=title,
                    company=company,
                    location=location,
                    url=url,
                    regions=regions,
                    salary_raw=salary_raw,
                    experience=experience,
                    employment_type=employment_type,
                    deadline=deadline,
                    tags=tags[:6],
                ).finalize()
                results.append(job)

            time.sleep(0.35)

    logger.info("[사람인] 총 %d건 수집 완료", len(results))
    return results
