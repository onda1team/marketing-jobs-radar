from __future__ import annotations

import logging
import time

import requests

from .models import JobPosting, extract_regions, is_marketing_job

logger = logging.getLogger(__name__)

API_URL = "https://www.wanted.co.kr/api/chaos/navigation/v1/results"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "ko-KR,ko;q=0.9",
}

WANTED_LOCATIONS = [
    "chungnam.cheonan-si",
    "chungnam.asan-si",
    "gyeonggi.pyeongtaek-si",
    "gyeonggi.anseong-si",
    "gyeonggi.osan-si",
]


def fetch_wanted() -> list[JobPosting]:
    """Fetch marketing job postings from Wanted API for the 5 target cities."""
    results: list[JobPosting] = []
    seen_ids: set[int] = set()
    session = requests.Session()
    session.headers.update(HEADERS)

    offset = 0
    limit = 20
    for _ in range(5):
        params = {
            "job_group_id": 523,  # 마케팅·광고
            "country": "kr",
            "job_sort": "job.latest_order",
            "years": -1,
            "locations": WANTED_LOCATIONS,
            "limit": limit,
            "offset": offset,
        }
        try:
            resp = session.get(API_URL, params=params, timeout=15)
            resp.raise_for_status()
            payload = resp.json()
        except Exception as exc:
            logger.warning("[원티드] API 요청 실패 (offset=%d): %s", offset, exc)
            break

        items = payload.get("data", [])
        if not items:
            break

        for item in items:
            jid = item.get("id")
            if not jid or jid in seen_ids:
                continue

            title = item.get("position", "")
            company = (item.get("company") or {}).get("name", "")
            addr = item.get("address") or {}
            location = " ".join(
                part for part in [addr.get("location", ""), addr.get("district", "")] if part
            )
            regions = extract_regions(location, title)
            if not regions:
                continue
            if not is_marketing_job(title, ["마케팅"]):
                continue

            annual_from = item.get("annual_from")
            annual_to = item.get("annual_to")
            if annual_from is not None and annual_to is not None:
                if annual_from == 0 and annual_to >= 99:
                    exp = "경력무관"
                elif annual_to >= 99:
                    exp = f"경력 {annual_from}년 이상"
                else:
                    exp = f"경력 {annual_from}~{annual_to}년"
            else:
                exp = ""

            seen_ids.add(jid)
            tags = ["마케팅·광고"]
            if item.get("reward_total"):
                tags.append(f"보상금 {item['reward_total']}")

            job = JobPosting(
                platform="원티드",
                title=title,
                company=company,
                location=location,
                url=f"https://www.wanted.co.kr/wd/{jid}",
                regions=regions,
                salary_raw="",
                experience=exp,
                employment_type="정규직",
                deadline="상시채용",
                tags=tags,
            ).finalize()
            results.append(job)

        if len(items) < limit:
            break
        offset += limit
        time.sleep(0.3)

    logger.info("[원티드] 총 %d건 수집 완료", len(results))
    return results
