from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from typing import Optional

TARGET_REGIONS = ["천안", "아산", "평택", "안성", "오산"]

CORE_MARKETING_KEYWORDS = [
    "마케팅",
    "마케터",
    "퍼포먼스",
    "그로스",
    "브랜드",
    "브랜딩",
    "crm",
    "디지털마케팅",
    "콘텐츠마케팅",
    "바이럴",
    "검색광고",
    "광고기획",
    "홍보",
    "pr",
    "ae",
    "marketing",
    "marketer",
    "growth",
    "performance",
]

SECONDARY_MARKETING_KEYWORDS = [
    "콘텐츠",
    "sns",
    "광고",
    "캠페인",
    "seo",
    "프로모션",
    "이커머스",
    "온라인md",
    "온라인 md",
    "상품기획",
    "커뮤니케이션",
    "유튜브",
    "인스타",
    "블로그",
    "스마트스토어",
    "카피라이터",
]

EXCLUDE_TITLE_KEYWORDS = [
    "미화",
    "청소",
    "도장",
    "방수",
    "지게차",
    "생산직",
    "단순노무",
    "경비",
    "운전",
    "배송기사",
    "조리",
    "주방",
    "간호조무사",
    "요양보호사",
    "설비보전",
    "용접",
    "배관",
    "전기기사",
    "건설현장",
    "텔레마케터",
    "레슨코치",
    "비서",
]


@dataclass
class JobPosting:
    platform: str
    title: str
    company: str
    location: str
    url: str
    regions: list[str] = field(default_factory=list)
    salary_raw: str = ""
    salary_display: str = "회사내규 / 면접 후 결정"
    salary_annual_manwon: int = 0
    salary_min_manwon: int = 0
    salary_max_manwon: int = 0
    experience: str = ""
    employment_type: str = ""
    deadline: str = ""
    tags: list[str] = field(default_factory=list)
    company_rating: Optional[float] = None
    is_core_marketing: bool = True
    posted_at: str = ""
    job_id: str = ""

    def finalize(self) -> "JobPosting":
        self.title = clean_text(self.title)
        self.company = clean_text(self.company)
        self.location = clean_text(self.location)
        self.experience = clean_text(self.experience)
        self.employment_type = clean_text(self.employment_type)
        self.deadline = clean_text(self.deadline)
        self.salary_raw = clean_text(self.salary_raw)

        if not self.regions:
            self.regions = extract_regions(self.location, self.title)

        min_m, max_m, annual_m, display = parse_salary(self.salary_raw)
        self.salary_min_manwon = min_m
        self.salary_max_manwon = max_m
        self.salary_annual_manwon = annual_m
        self.salary_display = display

        self.is_core_marketing = is_core_marketing_role(self.title, self.tags)

        if not self.job_id:
            key = f"{self.platform}:{self.url}"
            self.job_id = hashlib.md5(key.encode("utf-8")).hexdigest()[:12]
        return self

    def dedup_key(self) -> str:
        norm_company = re.sub(r"\(주\)|㈜|주식회사|\s+", "", self.company).lower()
        norm_title = re.sub(r"[\[\]()【】\s/·\-_,.]+", "", self.title).lower()
        return f"{norm_company}::{norm_title[:36]}"

    def to_dict(self) -> dict:
        return asdict(self)


def clean_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def extract_regions(location: str, title: str = "") -> list[str]:
    found: list[str] = []
    loc_text = location or ""
    for city in TARGET_REGIONS:
        if city in loc_text:
            found.append(city)
    if not found and title:
        # Allow title match when location mentions surrounding province or multiple locations
        if any(hint in loc_text for hint in ("충남", "경기", "전국", "외", "")) or not loc_text:
            for city in TARGET_REGIONS:
                if city in title:
                    found.append(city)
    return found


def is_core_marketing_role(title: str, tags: list[str] | None = None) -> bool:
    title_lower = (title or "").lower().replace("텔레마케터", "")
    return any(kw in title_lower for kw in CORE_MARKETING_KEYWORDS)


def is_marketing_job(title: str, tags: list[str] | None = None) -> bool:
    title_lower = (title or "").lower()
    if any(bad in title_lower for bad in EXCLUDE_TITLE_KEYWORDS):
        return False

    clean_title = title_lower.replace("텔레마케터", "")
    if any(kw in clean_title for kw in CORE_MARKETING_KEYWORDS):
        return True
    if any(kw in clean_title for kw in SECONDARY_MARKETING_KEYWORDS):
        return True

    # Reject pure sales/field roles when title has no marketing keyword
    if any(non_mkt in clean_title for non_mkt in ("영업", "판매", "매장", "상담", "생산", "품질", "연구")):
        return False

    tags_lower = " ".join(tags or []).lower()
    if any(role in clean_title for role in ("기획", "담당", "매니저", "팀장", "사원")) and any(
        kw in tags_lower for kw in ("마케팅", "마케터", "퍼포먼스", "브랜드", "광고기획", "홍보")
    ):
        return True
    return False


def parse_salary(raw: str) -> tuple[int, int, int, str]:
    """
    Parse Korean salary strings into (min_manwon, max_manwon, sort_annual_manwon, display_label).
    All numeric values are in 만원 (10,000 KRW) annualized.
    """
    if not raw:
        return 0, 0, 0, "회사내규 / 면접 후 결정"

    text = raw.replace(",", "").replace(" ", "")
    if any(k in text for k in ("내규", "면접", "협의", "추후", "미기재")):
        # Check if there's still a numeric figure alongside (e.g., "연봉 4,000만원 (면접 후 협의)")
        if not re.search(r"\d", text):
            return 0, 0, 0, raw.strip()

    # Detect unit type
    is_hourly = "시급" in text
    is_daily = "일급" in text
    is_monthly = "월급" in text or "월" in text
    is_annual = "연봉" in text or "연" in text

    # Extract numbers with 만원 / 억 / 원
    # Handle "억" e.g. "1억", "1억2000만원", "1.2억"
    eok_matches = re.findall(r"(\d+(?:\.\d+)?)억(?:(\d+)만)?", text)
    nums_manwon: list[int] = []
    if eok_matches:
        for eok_str, man_str in eok_matches:
            val = int(round(float(eok_str) * 10000))
            if man_str:
                val += int(man_str)
            nums_manwon.append(val)
    else:
        # Match numbers followed by 만원 or 만
        man_matches = re.findall(r"(\d+(?:\.\d+)?)만", text)
        if man_matches:
            nums_manwon = [int(round(float(m))) for m in man_matches]
        else:
            # Match raw KRW numbers like 3500000원 or 12000원
            won_matches = re.findall(r"(\d{4,9})원", text)
            if won_matches:
                if is_hourly:
                    # 209 hours/month * 12 months
                    nums_manwon = [int(round(int(w) * 209 * 12 / 10000)) for w in won_matches]
                    is_annual = True
                    is_hourly = False
                elif is_daily:
                    nums_manwon = [int(round(int(w) * 22 * 12 / 10000)) for w in won_matches]
                    is_annual = True
                    is_daily = False
                else:
                    nums_manwon = [int(round(int(w) / 10000)) for w in won_matches]

    nums_manwon = [n for n in nums_manwon if n > 0]
    if not nums_manwon:
        return 0, 0, 0, raw.strip()

    # Convert hourly/monthly to annual
    converted_from_monthly = False
    if is_hourly:
        # e.g., 시급 1.2만원
        annual_nums = [int(round(n * 209 * 12)) for n in nums_manwon]
    elif is_daily:
        annual_nums = [int(round(n * 22 * 12)) for n in nums_manwon]
    elif is_monthly and not is_annual:
        annual_nums = [n * 12 for n in nums_manwon]
        converted_from_monthly = True
    elif not is_annual and max(nums_manwon) < 1200:
        # Saramin often shows "280 만원" or "350 만원" without saying "월급"
        annual_nums = [n * 12 for n in nums_manwon]
        converted_from_monthly = True
    else:
        annual_nums = nums_manwon

    # Sanity filter (ignore unrealistic parsed numbers like 100만원 annual or > 5억원)
    annual_nums = [n for n in annual_nums if 1500 <= n <= 50000]
    if not annual_nums:
        return 0, 0, 0, raw.strip()

    min_m = min(annual_nums)
    max_m = max(annual_nums)
    sort_val = max_m  # Highest potential salary first

    def fmt(v: int) -> str:
        if v >= 10000:
            eok = v // 10000
            rem = v % 10000
            return f"{eok}억 {rem:,}만원" if rem else f"{eok}억원"
        return f"{v:,}만원"

    if min_m == max_m:
        base_str = f"연 {fmt(max_m)}"
    else:
        base_str = f"연 {fmt(min_m)} ~ {fmt(max_m)}"

    if converted_from_monthly:
        orig_m = f"{min(nums_manwon):,}~{max(nums_manwon):,}만원" if len(set(nums_manwon)) > 1 else f"{nums_manwon[0]:,}만원"
        display = f"{base_str} (월 {orig_m})"
    else:
        display = base_str

    return min_m, max_m, sort_val, display
