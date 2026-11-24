from __future__ import annotations

import logging
import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .models import JobPosting, TARGET_REGIONS, extract_regions, is_marketing_job

logger = logging.getLogger(__name__)

BASE_URL = "https://www.jobkorea.co.kr"
SEARCH_URL = f"{BASE_URL}/Search/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.jobkorea.co.kr/",
}


def fetch_jobkorea(pages_per_region: int = 2) -> list[JobPosting]:
    """Fetch marketing job postings from JobKorea for the target regions."""
    results: list[JobPosting] = []
    seen_ids: set[str] = set()
    session = requests.Session()
    session.headers.update(HEADERS)

    for city in TARGET_REGIONS:
        for page in range(1, pages_per_region + 1):
            params = {
                "stext": f"마케팅 {city}",
                "tabType": "recruit",
                "Page_No": page,
            }
            try:
                resp = session.get(SEARCH_URL, params=params, timeout=15)
                resp.raise_for_status()
            except Exception as exc:
                logger.warning("[잡코리아] %s p%d 요청 실패: %s", city, page, exc)
                break

            soup = BeautifulSoup(resp.text, "lxml")
            links = soup.select("a[href*='/Recruit/GI_Read/']")
            if not links:
                break

            page_found = 0
            for a in links:
                href = a.get("href", "")
                m = re.search(r"/Recruit/GI_Read/(\d+)", href)
                if not m:
                    continue
                gno = m.group(1)
                title = a.get_text(" ", strip=True)
                if not title or len(title) < 4 or gno in seen_ids:
                    continue

                # Find enclosing single-job card element (strictly 1 job id inside)
                card = a
                for _ in range(6):
                    parent = card.parent
                    if not parent or parent.name in ("body", "html", "[document]"):
                        break
                    parent_gnos = set(re.findall(r"/Recruit/GI_Read/(\d+)", str(parent)))
                    if len(parent_gnos) == 1:
                        card = parent
                    else:
                        break
                if not card or card is a:
                    continue

                card_text = card.get_text(" | ", strip=True)
                parts = [p.strip() for p in card_text.split("|") if p.strip()]

                # Extract company (usually right after title or via company link)
                company = ""
                comp_link = card.select_one("a[href*='/Recruit/Co_Read/'], a[href*='/company/']")
                if comp_link:
                    company = comp_link.get_text(" ", strip=True)
                if not company:
                    try:
                        idx = parts.index(title)
                        if idx + 1 < len(parts):
                            company = parts[idx + 1]
                    except ValueError:
                        pass
                if not company:
                    continue

                # Extract location, salary, experience, tags, deadline from parts
                location = ""
                salary_raw = ""
                experience = ""
                deadline = ""
                tags: list[str] = []

                for p in parts:
                    if p in (title, company, "스크랩", "즉시 지원", "홈페이지 지원", "신입 지원 가능", "•"):
                        continue
                    if not salary_raw and re.search(r"(연봉|월급|시급|일급)\s*[~]?\s*[\d,]+", p):
                        salary_raw = p
                    elif not location and re.search(r"(충남|충북|경기|서울|인천|대전|세종|천안|아산|평택|안성|오산)", p) and len(p) <= 30:
                        location = p
                    elif not experience and re.search(r"(신입|경력|무관)", p) and len(p) <= 20:
                        experience = p
                    elif not deadline and re.search(r"(~\d{2}\.\d{2}|상시채용|채용시|오늘 마감|D-\d+)", p):
                        deadline = p
                    elif "," in p and len(p) <= 90:
                        tags.extend([t.strip() for t in p.split(",") if t.strip()])

                regions = extract_regions(location, title)
                if not regions:
                    continue
                if not is_marketing_job(title, tags):
                    continue

                seen_ids.add(gno)
                page_found += 1
                url = urljoin(BASE_URL, f"/Recruit/GI_Read/{gno}")
                job = JobPosting(
                    platform="잡코리아",
                    title=title,
                    company=company,
                    location=location or city,
                    url=url,
                    regions=regions,
                    salary_raw=salary_raw,
                    experience=experience,
                    deadline=deadline,
                    tags=tags[:6],
                ).finalize()
                results.append(job)

            if page_found == 0:
                break
            time.sleep(0.35)

    logger.info("[잡코리아] 총 %d건 수집 완료", len(results))
    return results
