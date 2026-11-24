from __future__ import annotations

import logging
import re
import time

import requests
from bs4 import BeautifulSoup

from .models import JobPosting, TARGET_REGIONS, extract_regions, is_marketing_job

logger = logging.getLogger(__name__)

SEARCH_URL = "https://search.incruit.com/list/search.asp"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
}


def fetch_incruit(pages_per_region: int = 2) -> list[JobPosting]:
    """Fetch marketing job postings from Incruit for the target regions."""
    results: list[JobPosting] = []
    seen_urls: set[str] = set()
    session = requests.Session()
    session.headers.update(HEADERS)

    for city in TARGET_REGIONS:
        for page in range(1, pages_per_region + 1):
            params = {
                "col": "job",
                "kw": f"마케팅 {city}",
                "startno": (page - 1) * 30,
            }
            try:
                resp = session.get(SEARCH_URL, params=params, timeout=15)
                resp.raise_for_status()
                resp.encoding = "euc-kr"
            except Exception as exc:
                logger.warning("[인크루트] %s p%d 요청 실패: %s", city, page, exc)
                break

            soup = BeautifulSoup(resp.text, "lxml")
            rows = soup.select(".c_row")
            if not rows:
                break

            for row in rows:
                link = row.select_one("a[href*='jobpost.asp']")
                if not link:
                    continue
                url = link.get("href", "").strip()
                if not url or url in seen_urls:
                    continue

                title = link.get_text(" ", strip=True)
                # Normalize split highlighted words like "[ 천안 시]" -> "[천안시]"
                title = re.sub(r"\s+", " ", title).strip()

                comp_el = row.select_one(".cell_first a, .cpname")
                company = comp_el.get_text(" ", strip=True) if comp_el else ""
                if not company:
                    continue

                row_text = row.get_text(" | ", strip=True)
                parts = [p.strip() for p in row_text.split("|") if p.strip()]

                location = ""
                experience = ""
                employment_type = ""
                salary_raw = ""
                deadline = ""
                tags: list[str] = []

                for p in parts:
                    if not location and re.search(r"(충남|충북|경기|서울|천안|아산|평택|안성|오산)", p) and len(p) <= 25:
                        if p != title and p != company:
                            location = p
                    elif not salary_raw and re.search(r"(연봉|월급|시급|만원|억원)", p):
                        salary_raw = p
                    elif not experience and re.search(r"(경력|신입)", p) and len(p) <= 20:
                        experience = p
                    elif not employment_type and p in ("정규직", "계약직", "인턴", "프리랜서", "아르바이트"):
                        employment_type = p
                    elif not deadline and re.search(r"(~\d{2}\.\d{2}|채용시|상시채용)", p):
                        deadline = p

                # Extract category tags if present
                for sp in row.select(".cl_btm span"):
                    txt = sp.get_text(" ", strip=True)
                    if txt and len(txt) <= 25:
                        tags.append(txt)

                regions = extract_regions(location, title)
                if not regions:
                    continue
                if not is_marketing_job(title, tags):
                    continue

                seen_urls.add(url)
                job = JobPosting(
                    platform="인크루트",
                    title=title,
                    company=company,
                    location=location or city,
                    url=url,
                    regions=regions,
                    salary_raw=salary_raw,
                    experience=experience,
                    employment_type=employment_type,
                    deadline=deadline,
                    tags=tags[:5],
                ).finalize()
                results.append(job)

            time.sleep(0.35)

    logger.info("[인크루트] 총 %d건 수집 완료", len(results))
    return results
