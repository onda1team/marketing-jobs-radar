from __future__ import annotations

import csv
import json
import logging
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .incruit import fetch_incruit
from .jobkorea import fetch_jobkorea
from .jobplanet import fetch_jobplanet
from .models import JobPosting, TARGET_REGIONS
from .saramin import fetch_saramin
from .wanted import fetch_wanted

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "docs" / "data"


def deduplicate(jobs: list[JobPosting]) -> list[JobPosting]:
    """Merge duplicate postings across platforms, keeping the richest salary/rating info."""
    merged: dict[str, JobPosting] = {}
    for job in jobs:
        key = job.dedup_key()
        existing = merged.get(key)
        if not existing:
            merged[key] = job
            continue

        # Prefer the entry with an explicit higher salary
        if job.salary_annual_manwon > existing.salary_annual_manwon:
            if existing.company_rating and not job.company_rating:
                job.company_rating = existing.company_rating
            merged[key] = job
        else:
            if job.company_rating and not existing.company_rating:
                existing.company_rating = job.company_rating
            if not existing.experience and job.experience:
                existing.experience = job.experience
            if not existing.deadline and job.deadline:
                existing.deadline = job.deadline
    return list(merged.values())


def sort_by_salary_desc(jobs: list[JobPosting]) -> list[JobPosting]:
    """Sort postings by highest annual salary first, then core marketing role, then rating."""
    return sorted(
        jobs,
        key=lambda j: (
            1 if j.salary_annual_manwon > 0 else 0,
            j.salary_annual_manwon,
            j.salary_min_manwon,
            1 if j.is_core_marketing else 0,
            j.company_rating or 0.0,
            j.company,
        ),
        reverse=True,
    )


def save_outputs(jobs: list[JobPosting], platform_errors: dict[str, str]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    now_kst = datetime.now(KST)

    region_counter: Counter[str] = Counter()
    platform_counter: Counter[str] = Counter()
    for j in jobs:
        platform_counter[j.platform] += 1
        for r in j.regions:
            region_counter[r] += 1

    disclosed = [j for j in jobs if j.salary_annual_manwon > 0]
    top_salary = disclosed[0].salary_annual_manwon if disclosed else 0
    avg_salary = (
        round(sum(j.salary_annual_manwon for j in disclosed) / len(disclosed))
        if disclosed
        else 0
    )

    payload = {
        "updated_at": now_kst.strftime("%Y-%m-%d %H:%M KST"),
        "updated_iso": now_kst.isoformat(),
        "target_regions": TARGET_REGIONS,
        "total": len(jobs),
        "salary_disclosed_count": len(disclosed),
        "top_salary_manwon": top_salary,
        "avg_salary_manwon": avg_salary,
        "region_counts": {r: region_counter.get(r, 0) for r in TARGET_REGIONS},
        "platform_counts": dict(platform_counter),
        "platform_errors": platform_errors,
        "jobs": [j.to_dict() for j in jobs],
    }

    json_path = DATA_DIR / "jobs.json"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    csv_path = DATA_DIR / "jobs.csv"
    fieldnames = [
        "순위",
        "플랫폼",
        "연봉(표시)",
        "연봉환산(만원)",
        "지역",
        "상세근무지",
        "회사명",
        "공고제목",
        "경력",
        "고용형태",
        "마감일",
        "기업평점",
        "링크",
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for idx, j in enumerate(jobs, start=1):
            writer.writerow(
                {
                    "순위": idx,
                    "플랫폼": j.platform,
                    "연봉(표시)": j.salary_display,
                    "연봉환산(만원)": j.salary_annual_manwon or "",
                    "지역": ", ".join(j.regions),
                    "상세근무지": j.location,
                    "회사명": j.company,
                    "공고제목": j.title,
                    "경력": j.experience,
                    "고용형태": j.employment_type,
                    "마감일": j.deadline,
                    "기업평점": j.company_rating if j.company_rating is not None else "",
                    "링크": j.url,
                }
            )

    logger.info("저장 완료: %s (%d건), %s", json_path, len(jobs), csv_path)


def run() -> list[JobPosting]:
    collectors = [
        ("사람인", fetch_saramin),
        ("잡코리아", fetch_jobkorea),
        ("원티드", fetch_wanted),
        ("인크루트", fetch_incruit),
        ("잡플래닛", fetch_jobplanet),
    ]

    all_jobs: list[JobPosting] = []
    platform_errors: dict[str, str] = {}

    for name, fn in collectors:
        try:
            fetched = fn()
            all_jobs.extend(fetched)
        except Exception as exc:
            logger.exception("[%s] 수집 중 예외 발생", name)
            platform_errors[name] = str(exc)

    unique_jobs = deduplicate(all_jobs)
    sorted_jobs = sort_by_salary_desc(unique_jobs)
    save_outputs(sorted_jobs, platform_errors)
    return sorted_jobs


if __name__ == "__main__":
    jobs = run()
    print(f"\n총 {len(jobs)}건 수집 완료 (연봉 명시: {sum(1 for j in jobs if j.salary_annual_manwon > 0)}건)")
    print("\n--- 연봉 TOP 15 ---")
    for i, j in enumerate(jobs[:15], start=1):
        print(
            f"{i:2d}. [{j.platform}] {j.salary_display:24s} | {','.join(j.regions):5s} | "
            f"{j.company} - {j.title[:45]}"
        )
