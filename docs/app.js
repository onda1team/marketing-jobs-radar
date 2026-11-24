const STORAGE_KEY = "marketing_radar_bookmarks_v1";

const state = {
  jobs: [],
  meta: null,
  region: "전체",
  platform: "전체",
  query: "",
  salaryOnly: false,
  bookmarkOnly: false,
  sort: "salary",
  bookmarks: new Set(JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]")),
};

function fmtManwon(v) {
  if (!v) return "-";
  if (v >= 10000) {
    const eok = Math.floor(v / 10000);
    const rem = v % 10000;
    return rem ? `${eok}억 ${rem.toLocaleString()}만원` : `${eok}억원`;
  }
  return `${v.toLocaleString()}만원`;
}

function escapeHtml(str) {
  return String(str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function saveBookmarks() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify([...state.bookmarks]));
}

function toggleBookmark(jobId) {
  if (state.bookmarks.has(jobId)) {
    state.bookmarks.delete(jobId);
  } else {
    state.bookmarks.add(jobId);
  }
  saveBookmarks();
  renderJobs();
}

function buildChips() {
  const regionContainer = document.getElementById("regionChips");
  const regions = ["전체", ...(state.meta.target_regions || ["천안", "아산", "평택", "안성", "오산"])];
  const rCounts = state.meta.region_counts || {};

  regionContainer.innerHTML = regions
    .map((r) => {
      const cnt = r === "전체" ? state.meta.total : rCounts[r] || 0;
      const active = state.region === r ? "active" : "";
      return `<button class="chip ${active}" data-region="${r}">${r}<span class="cnt">${cnt}</span></button>`;
    })
    .join("");

  regionContainer.querySelectorAll(".chip").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.region = btn.dataset.region;
      buildChips();
      renderJobs();
    });
  });

  const platformContainer = document.getElementById("platformChips");
  const pCounts = state.meta.platform_counts || {};
  const platforms = ["전체", ...Object.keys(pCounts)];

  platformContainer.innerHTML = platforms
    .map((p) => {
      const cnt = p === "전체" ? state.meta.total : pCounts[p] || 0;
      const active = state.platform === p ? "active" : "";
      return `<button class="chip ${active}" data-platform="${p}">${p}<span class="cnt">${cnt}</span></button>`;
    })
    .join("");

  platformContainer.querySelectorAll(".chip").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.platform = btn.dataset.platform;
      buildChips();
      renderJobs();
    });
  });
}

function getFilteredJobs() {
  const q = state.query.trim().toLowerCase();
  let list = state.jobs.filter((j) => {
    if (state.region !== "전체" && !(j.regions || []).includes(state.region)) return false;
    if (state.platform !== "전체" && j.platform !== state.platform) return false;
    if (state.salaryOnly && !(j.salary_annual_manwon > 0)) return false;
    if (state.bookmarkOnly && !state.bookmarks.has(j.job_id)) return false;
    if (q) {
      const hay = `${j.company} ${j.title} ${j.location} ${(j.tags || []).join(" ")} ${j.experience}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });

  list = [...list];
  if (state.sort === "salary") {
    list.sort((a, b) => {
      if ((b.salary_annual_manwon || 0) !== (a.salary_annual_manwon || 0)) {
        return (b.salary_annual_manwon || 0) - (a.salary_annual_manwon || 0);
      }
      if ((b.is_core_marketing ? 1 : 0) !== (a.is_core_marketing ? 1 : 0)) {
        return (b.is_core_marketing ? 1 : 0) - (a.is_core_marketing ? 1 : 0);
      }
      return (b.company_rating || 0) - (a.company_rating || 0);
    });
  } else if (state.sort === "core") {
    list.sort((a, b) => {
      if ((b.is_core_marketing ? 1 : 0) !== (a.is_core_marketing ? 1 : 0)) {
        return (b.is_core_marketing ? 1 : 0) - (a.is_core_marketing ? 1 : 0);
      }
      return (b.salary_annual_manwon || 0) - (a.salary_annual_manwon || 0);
    });
  } else if (state.sort === "rating") {
    list.sort((a, b) => {
      if ((b.company_rating || 0) !== (a.company_rating || 0)) {
        return (b.company_rating || 0) - (a.company_rating || 0);
      }
      return (b.salary_annual_manwon || 0) - (a.salary_annual_manwon || 0);
    });
  }

  return list;
}

function renderJobs() {
  const list = getFilteredJobs();
  const countEl = document.getElementById("resultCount");
  const container = document.getElementById("jobList");

  const disclosedInView = list.filter((j) => j.salary_annual_manwon > 0).length;
  countEl.innerHTML = `표시 중 <strong>${list.length}건</strong> (연봉 명시 ${disclosedInView}건)`;

  if (!list.length) {
    container.innerHTML = `<div class="empty-state">조건에 맞는 공고가 없습니다. 필터를 조정해 보세요.</div>`;
    return;
  }

  container.innerHTML = list
    .map((j, idx) => {
      const rank = idx + 1;
      const rankClass =
        j.salary_annual_manwon > 0 && rank <= 3 ? `top${rank}` : "";
      const hasSalary = j.salary_annual_manwon > 0;
      const saved = state.bookmarks.has(j.job_id);
      const regionsHtml = (j.regions || [])
        .map((r) => `<span class="region-badge">${escapeHtml(r)}</span>`)
        .join("");
      const ratingHtml = j.company_rating
        ? `<span class="rating-badge">★ ${Number(j.company_rating).toFixed(1)}</span>`
        : "";
      const tagsHtml = (j.tags || [])
        .slice(0, 5)
        .map((t) => `<span class="tag">#${escapeHtml(t)}</span>`)
        .join("");

      const metaItems = [
        j.location ? `📍 ${escapeHtml(j.location)}` : "",
        j.experience ? `💼 ${escapeHtml(j.experience)}` : "",
        j.employment_type ? `📄 ${escapeHtml(j.employment_type)}` : "",
        j.deadline ? `⏰ ${escapeHtml(j.deadline)}` : "",
      ].filter(Boolean);

      return `
        <article class="job-card">
          <div class="rank-badge ${rankClass}">${rank}</div>
          <div class="job-main">
            <div class="job-top-meta">
              <span class="platform-badge platform-${escapeHtml(j.platform)}">${escapeHtml(j.platform)}</span>
              ${regionsHtml}
              <span class="company-name">${escapeHtml(j.company)}</span>
              ${ratingHtml}
            </div>
            <a class="job-title" href="${escapeHtml(j.url)}" target="_blank" rel="noopener noreferrer">
              ${escapeHtml(j.title)}
            </a>
            <div class="job-sub-meta">
              ${metaItems.map((m) => `<span>${m}</span>`).join("")}
            </div>
            ${tagsHtml ? `<div class="tag-row">${tagsHtml}</div>` : ""}
          </div>
          <div class="job-side">
            <div class="salary-pill ${hasSalary ? "disclosed" : "undisclosed"}">
              ${escapeHtml(j.salary_display)}
            </div>
            <div class="card-actions">
              <button
                class="btn-bookmark ${saved ? "saved" : ""}"
                data-bookmark="${escapeHtml(j.job_id)}"
                title="북마크"
              >${saved ? "★" : "☆"}</button>
              <a class="btn-open" href="${escapeHtml(j.url)}" target="_blank" rel="noopener noreferrer">
                공고 보기 ↗
              </a>
            </div>
          </div>
        </article>
      `;
    })
    .join("");

  container.querySelectorAll("[data-bookmark]").forEach((btn) => {
    btn.addEventListener("click", () => toggleBookmark(btn.dataset.bookmark));
  });
}

async function init() {
  try {
    const res = await fetch("data/jobs.json?_=" + Date.now());
    if (!res.ok) throw new Error("jobs.json을 불러오지 못했습니다.");
    const data = await res.json();
    state.meta = data;
    state.jobs = data.jobs || [];

    document.getElementById("updatedAt").textContent = `최근 자동 수집: ${data.updated_at || "-"}`;
    document.getElementById("statTotal").textContent = `${(data.total || 0).toLocaleString()}건`;
    document.getElementById("statDisclosed").textContent = `${(data.salary_disclosed_count || 0).toLocaleString()}건`;
    document.getElementById("statTopSalary").textContent = fmtManwon(data.top_salary_manwon);
    document.getElementById("statAvgSalary").textContent = fmtManwon(data.avg_salary_manwon);

    buildChips();
    renderJobs();
  } catch (err) {
    document.getElementById("jobList").innerHTML =
      `<div class="empty-state">데이터 로드 오류: ${escapeHtml(err.message)}</div>`;
  }
}

document.getElementById("searchInput").addEventListener("input", (e) => {
  state.query = e.target.value;
  renderJobs();
});

document.getElementById("salaryOnlyToggle").addEventListener("change", (e) => {
  state.salaryOnly = e.target.checked;
  renderJobs();
});

document.getElementById("bookmarkOnlyToggle").addEventListener("change", (e) => {
  state.bookmarkOnly = e.target.checked;
  renderJobs();
});

document.getElementById("sortSelect").addEventListener("change", (e) => {
  state.sort = e.target.value;
  renderJobs();
});

init();
