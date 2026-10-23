/* ============================================================
   Rozgar — job board logic (vanilla JS, no dependencies)
   Data: data/jobs.json (regenerated hourly by GitHub Actions)
   ============================================================ */

const PAGE = 20;

const state = {
  jobs: [],
  meta: {},
  filtered: [],
  shown: PAGE,
  q: "",
  category: "",
  type: "",
  level: "",
  region: "",
  pakOnly: false,
  govOnly: false,
  savedOnly: false,
  sort: "new",
  saved: new Set(),
};

const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];

const esc = (s = "") =>
  String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const safeUrl = (u = "") => (/^https?:\/\//i.test(u) ? u : "");

/* inline SVG icons — emoji render inconsistently across devices */
const ICON = {
  clock: '<svg viewBox="0 0 24 24" width="13" height="13" aria-hidden="true"><circle cx="12" cy="12" r="8.5" fill="none" stroke="currentColor" stroke-width="1.9"/><path d="M12 7.5V12l3 1.8" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"/></svg>',
  level: '<svg viewBox="0 0 24 24" width="13" height="13" aria-hidden="true"><path d="M4 18V13M10 18V9M16 18V6M22 18v-3" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
  money: '<svg viewBox="0 0 24 24" width="13" height="13" aria-hidden="true"><rect x="2.5" y="6.5" width="19" height="11" rx="2" fill="none" stroke="currentColor" stroke-width="1.8"/><circle cx="12" cy="12" r="2.6" fill="none" stroke="currentColor" stroke-width="1.8"/></svg>',
  pin: '<svg viewBox="0 0 24 24" width="13" height="13" aria-hidden="true"><path d="M12 21s6.5-5.4 6.5-10.5a6.5 6.5 0 1 0-13 0C5.5 15.6 12 21 12 21z" fill="none" stroke="currentColor" stroke-width="1.8"/><circle cx="12" cy="10.4" r="2.4" fill="none" stroke="currentColor" stroke-width="1.8"/></svg>',
  arrow: '<svg viewBox="0 0 24 24" width="13" height="13" aria-hidden="true"><path d="M7 17 17 7M9 7h8v8" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  star: (filled) => `<svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true"><path d="M12 3.6l2.6 5.4 5.9.8-4.3 4.1 1.1 5.8L12 16.9 6.7 19.7l1.1-5.8L3.5 9.8l5.9-.8z" fill="${filled ? "currentColor" : "none"}" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/></svg>`,
  check: '<svg viewBox="0 0 24 24" width="13" height="13" aria-hidden="true"><path d="M4 12.5l5 5L20 6.5" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"/></svg>',
};

function ago(ts) {
  if (!ts) return "recently";
  const d = Math.max(0, Date.now() / 1000 - ts);
  if (d < 3600) return `${Math.max(1, Math.floor(d / 60))} min ago`;
  if (d < 86400) return `${Math.floor(d / 3600)}h ago`;
  if (d < 172800) return "yesterday";
  if (d < 2592000) return `${Math.floor(d / 86400)}d ago`;
  return new Date(ts * 1000).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

function salaryValue(j) {
  const n = parseFloat(j.salary_max || j.salary_min || 0);
  return Number.isFinite(n) ? n : 0;
}

/* ─────────────────────────────── saved jobs */
function loadSaved() {
  try {
    state.saved = new Set(JSON.parse(localStorage.getItem("rozgar-saved") || "[]"));
  } catch {
    state.saved = new Set();
  }
  $("#savedCount").textContent = state.saved.size;
}
function persistSaved() {
  try {
    localStorage.setItem("rozgar-saved", JSON.stringify([...state.saved]));
  } catch {}
  $("#savedCount").textContent = state.saved.size;
}

/* ─────────────────────────────── filtering */
function applyFilters() {
  const q = state.q.toLowerCase().trim();
  const words = q ? q.split(/\s+/) : [];

  const today = new Date().toISOString().slice(0, 10);
  state.filtered = state.jobs.filter((j) => {
    if (j.is_pk && j.last_date && j.last_date < today) return false;
    if (state.category && j.category !== state.category) return false;
    if (state.type && j.type !== state.type) return false;
    if (state.level && j.level !== state.level) return false;
    if (state.region && j.region !== state.region) return false;
    if (state.pakOnly && !(j.is_pk || j.pak_friendly)) return false;
    if (state.govOnly && (j.sector || "") !== "government" && !(j.is_pk && j.source !== "Manual")) return false;
    if (state.savedOnly && !state.saved.has(j.id)) return false;
    if (words.length) {
      const hay = (j.title + " " + j.company + " " + (j.tags || []).join(" ") + " " + j.location + " " + j.category).toLowerCase();
      if (!words.every((w) => hay.includes(w))) return false;
    }
    return true;
  });

  const pkRank = (j) => (j.is_pk ? 0 : 1);
  const sorters = {
    // "Pakistan first": local/Manual/Employer posts, then newest of the rest
    new: (a, b) => pkRank(a) - pkRank(b) || (b.published || 0) - (a.published || 0),
    old: (a, b) => (a.published || 0) - (b.published || 0),
    company: (a, b) => a.company.localeCompare(b.company),
    salary: (a, b) => salaryValue(b) - salaryValue(a),
  };
  state.filtered.sort(sorters[state.sort] || sorters.new);
}

/* ─────────────────────────────── rendering */
function cardHTML(j) {
  if (j.poster) {
    const savedP = state.saved.has(j.id);
    return `
    <article class="job-card poster-card ${j.is_manual ? "is-manual" : ""}">
      <a class="poster-thumb" href="jobs/${esc(j.slug)}.html">
        <img src="${esc(j.poster)}" alt="${esc(j.title)} poster" loading="lazy">
        ${j.last_date ? `<span class="poster-date">Last date ${esc(prettyDate(j.last_date))}</span>` : ""}
      </a>
      <div class="job-info">
        <h3 class="job-title"><a href="jobs/${esc(j.slug)}.html">${esc(j.title)}</a></h3>
        <p class="job-company"><b>${esc(j.company)}</b>${j.location ? " · " + esc(j.location) : ""}</p>
        <div class="chips">
          <span class="chip chip-src">${esc(j.source)}</span>
          ${j.qualification ? `<span class="chip">${esc(j.qualification)}</span>` : ""}
          ${j.age_limit ? `<span class="chip">Age ${esc(j.age_limit)}</span>` : ""}
        </div>
      </div>
      <div class="job-side">
        <button class="save-btn" data-save="${esc(j.id)}" aria-pressed="${savedP}" title="Save job">${ICON.star(savedP)}</button>
        <a class="apply" href="jobs/${esc(j.slug)}.html">Details ${ICON.arrow}</a>
      </div>
    </article>`;
  }
  const logo = safeUrl(j.company_logo)
    ? `<div class="logo"><img src="${esc(j.company_logo)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.parentNode.textContent='${esc((j.company || "?").slice(0, 2).toUpperCase())}'"></div>`
    : `<div class="logo">${esc((j.company || "?").slice(0, 2).toUpperCase())}</div>`;

  const isNew = j.age_days === 0;
  const saved = state.saved.has(j.id);
  const rel = ["Remotive", "Remote OK"].includes(j.source) ? " nofollow" : "";

  const tags = (j.tags || []).slice(0, 4).map((t) => `<span class="tag">${esc(t)}</span>`).join("");

  return `
  <article class="job-card ${j.is_manual ? "is-manual" : ""}">
    ${logo}
    <div class="job-info">
      <h3 class="job-title"><a href="jobs/${esc(j.slug)}.html">${esc(j.title)}</a></h3>
      <p class="job-company"><b>${esc(j.company)}</b>${j.location ? " · " + esc(j.location) : ""}</p>
      <div class="chips">
        ${isNew ? '<span class="chip chip-new">NEW</span>' : ""}
        ${j.last_date ? `<span class="chip chip-date">Last date: ${esc(prettyDate(j.last_date))}</span>` : ""}
        ${j.qualification ? `<span class="chip">${esc(j.qualification)}</span>` : ""}
        <span class="chip">${ICON.clock}${esc(j.type)}</span>
        <span class="chip">${ICON.level}${esc(j.level)}</span>
        ${j.salary ? `<span class="chip chip-salary">${ICON.money}${esc(j.salary)}</span>` : ""}
        ${j.is_manual ? `<span class="chip chip-manual">${ICON.check}Direct post</span>` : ""}
        ${j.pak_friendly ? `<span class="chip chip-pk">${ICON.pin}Open to PK</span>` : ""}
      </div>
      <div class="tags">${tags}</div>
    </div>
    <div class="job-side">
      <span class="time">${esc(ago(j.published))}</span>
      <button class="save-btn" data-save="${esc(j.id)}" aria-pressed="${saved}" title="Save job" aria-label="Save job">${ICON.star(saved)}</button>
      <a class="apply" href="${esc(safeUrl(j.url) || "#")}" target="_blank" rel="noopener noreferrer${rel}">Apply ${ICON.arrow}</a>
    </div>
  </article>`;
}

function render() {
  applyFilters();

  const list = $("#jobList");
  const slice = state.filtered.slice(0, state.shown);
  list.innerHTML = slice.map(cardHTML).join("");

  $("#resultsMeta").textContent =
    `${state.filtered.length} ${state.filtered.length === 1 ? "job" : "jobs"}` +
    (state.filtered.length !== state.jobs.length ? ` of ${state.jobs.length}` : "");

  const bits = [];
  if (state.q) bits.push(`“${state.q}”`);
  if (state.category) bits.push(state.category);
  if (state.type) bits.push(state.type);
  if (state.level) bits.push(state.level);
  if (state.region) bits.push(state.region);
  if (state.pakOnly) bits.push("Pakistan jobs");
  if (state.govOnly) bits.push("Government");
  if (state.savedOnly) bits.push("Saved");
  $("#resultsTitle").textContent = bits.length ? bits.join(" · ") : "Latest jobs";

  $("#empty").hidden = state.filtered.length !== 0;
  $("#loadMore").hidden = slice.length >= state.filtered.length;
  $("#clearFilters").hidden = !bits.length;

  renderCategories();
  renderPkStrip();
  syncUrl();
}

function renderCategories() {
  const counts = {};
  state.jobs.forEach((j) => (counts[j.category] = (counts[j.category] || 0) + 1));
  const cats = Object.entries(counts).sort((a, b) => b[1] - a[1]);

  $("#cats").innerHTML =
    `<button class="cat-btn ${!state.category ? "active" : ""}" data-cat="">All<span class="n">${state.jobs.length}</span></button>` +
    cats.map(([c, n]) => `<button class="cat-btn ${state.category === c ? "active" : ""}" data-cat="${esc(c)}">${esc(c)}<span class="n">${n}</span></button>`).join("");

  $("#catSideList").innerHTML = cats
    .slice(0, 8)
    .map(([c, n]) => `<li><a href="#" data-cat="${esc(c)}">${esc(c)}<span class="c">${n}</span></a></li>`)
    .join("");
}

function renderStats() {
  const m = state.meta;
  const todayS = new Date().toISOString().slice(0, 10);
  const pkCount = state.jobs.filter((j) => j.is_pk && (!j.last_date || j.last_date >= todayS)).length;
  const govCount = state.jobs.filter((j) => j.sector === "government" && (!j.is_pk || !j.last_date || j.last_date >= todayS)).length;
  $("#stTotal").textContent = (m.count || 0).toLocaleString();
  $("#stPk").textContent = pkCount.toLocaleString();
  $("#stGov").textContent = govCount.toLocaleString();
  $("#stNew").textContent = (m.new_today || 0).toLocaleString();
  const heroCount = $("#heroCount");
  if (heroCount) heroCount.textContent = (m.count || 0).toLocaleString();

  const when = m.generated_at ? new Date(m.generated_at) : new Date();
  $("#topStatus").textContent = `${(m.count || 0).toLocaleString()} jobs · ${ago(when.getTime() / 1000)}`;

  if (m.sources) {
    $("#sourceList").innerHTML = m.sources
      .map((s) => `<li><a href="#" data-source="${esc(s)}">${esc(s)}</a></li>`)
      .join("");
  }
}

function prettyDate(iso) {
  if (!iso) return "";
  const d = new Date(iso + "T00:00:00");
  if (isNaN(d)) return iso;
  return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}

function daysLeft(iso) {
  if (!iso) return null;
  const d = new Date(iso + "T00:00:00");
  if (isNaN(d)) return null;
  return Math.ceil((d - new Date()) / 86400000);
}

/* Pakistan band: horizontal posters */
function renderPkStrip() {
  const today = new Date().toISOString().slice(0, 10);
  const pkAll = state.jobs.filter((j) => j.is_pk && (!j.last_date || j.last_date >= today));
  const withPoster = pkAll.filter((j) => j.poster);
  const pk = (withPoster.length >= 4 ? withPoster : pkAll)
    .sort((a, b) => (a.last_date || "9999").localeCompare(b.last_date || "9999"))
    .slice(0, 10);

  $("#pkBandCount").textContent = pkAll.length;

  $("#pkStrip").innerHTML = pk
    .map((j) => {
      const dl = daysLeft(j.last_date);
      const urgent = dl !== null && dl <= 5 && dl >= 0;
      return `
      <a class="pk-card" href="jobs/${esc(j.slug)}.html">
        <div class="pk-thumb">
          <img src="${esc(j.poster || "")}" alt="${esc(j.title)} poster" loading="lazy"
               onerror="this.style.display='none'">
          ${urgent ? `<span class="pk-urgent">${dl === 0 ? "Last day" : dl + "d left"}</span>` : ""}
        </div>
        <div class="pk-body">
          <strong>${esc(j.title)}</strong>
          <span>${esc(j.company)}</span>
          <span class="pk-meta">${esc(j.location)} · ${j.last_date ? "Last date " + esc(prettyDate(j.last_date)) : "Open"}</span>
        </div>
      </a>`;
    })
    .join("");
}

function renderPopular() {
  const picks = [
    { label: "React", q: "react" },
    { label: "Python", q: "python" },
    { label: "Data analyst", q: "data analyst" },
    { label: "Customer support", q: "customer support" },
    { label: "Designer", q: "designer" },
    { label: "Accountant", q: "accountant" },
    { label: "Marketing", q: "marketing" },
    { label: "DevOps", q: "devops" },
    { label: "Internship", q: "intern" },
  ];
  $("#popular").innerHTML = picks
    .map((p) => `<button class="pop-chip" data-q="${esc(p.q)}">${esc(p.label)}</button>`)
    .join("");
}

/* ─────────────────────────────── url state */
function syncUrl() {
  const p = new URLSearchParams();
  if (state.q) p.set("q", state.q);
  if (state.category) p.set("category", state.category);
  if (state.type) p.set("type", state.type);
  if (state.level) p.set("level", state.level);
  if (state.region) p.set("region", state.region);
  if (state.pakOnly) p.set("pak", "1");
  if (state.savedOnly) p.set("saved", "1");
  if (state.sort !== "new") p.set("sort", state.sort);
  const qs = p.toString();
  history.replaceState(null, "", qs ? "?" + qs : location.pathname);
}

function readUrl() {
  const p = new URLSearchParams(location.search);
  state.q = p.get("q") || "";
  state.category = p.get("category") || "";
  state.type = p.get("type") || "";
  state.level = p.get("level") || "";
  state.region = p.get("region") || "";
  state.pakOnly = p.get("pak") === "1";
  state.savedOnly = p.get("saved") === "1";
  state.sort = p.get("sort") || "new";

  $("#q").value = state.q;
  $("#region").value = state.region;
  $("#type").value = state.type;
  $("#level").value = state.level;
  $("#sort").value = state.sort;
  $("#pakOnly").setAttribute("aria-pressed", state.pakOnly);
  $("#govOnly").setAttribute("aria-pressed", state.govOnly);
  $("#savedOnly").setAttribute("aria-pressed", state.savedOnly);
}

/* ─────────────────────────────── events */
function bind() {
  let t;
  $("#q").addEventListener("input", (e) => {
    clearTimeout(t);
    t = setTimeout(() => {
      state.q = e.target.value;
      state.shown = PAGE;
      render();
    }, 180);
  });
  $("#searchForm").addEventListener("submit", (e) => {
    e.preventDefault();
    state.q = $("#q").value;
    state.shown = PAGE;
    render();
    document.querySelector(".main-grid").scrollIntoView({ behavior: "smooth", block: "start" });
  });

  ["region", "type", "level", "sort"].forEach((id) => {
    $("#" + id).addEventListener("change", (e) => {
      state[id] = e.target.value;
      state.shown = PAGE;
      render();
    });
  });

  $("#cats").addEventListener("click", (e) => {
    const b = e.target.closest(".cat-btn");
    if (!b) return;
    state.category = b.dataset.cat;
    state.shown = PAGE;
    render();
  });

  $("#catSideList").addEventListener("click", (e) => {
    const a = e.target.closest("a[data-cat]");
    if (!a) return;
    e.preventDefault();
    state.category = a.dataset.cat;
    state.shown = PAGE;
    render();
    window.scrollTo({ top: 0, behavior: "smooth" });
  });

  $("#popular").addEventListener("click", (e) => {
    const b = e.target.closest(".pop-chip");
    if (!b) return;
    state.q = b.dataset.q;
    $("#q").value = state.q;
    state.shown = PAGE;
    render();
    document.querySelector(".main-grid").scrollIntoView({ behavior: "smooth", block: "start" });
  });

  $("#pakOnly").addEventListener("click", (e) => {
    state.pakOnly = !state.pakOnly;
    e.currentTarget.setAttribute("aria-pressed", state.pakOnly);
    state.shown = PAGE;
    render();
  });

  $("#govOnly").addEventListener("click", (e) => {
    state.govOnly = !state.govOnly;
    e.currentTarget.setAttribute("aria-pressed", state.govOnly);
    state.shown = PAGE;
    render();
  });

  $("#seeAllPk").addEventListener("click", () => {
    state.pakOnly = true;
    state.category = "";
    state.shown = PAGE;
    $("#pakOnly").setAttribute("aria-pressed", "true");
    render();
    document.querySelector(".main-grid").scrollIntoView({ behavior: "smooth", block: "start" });
  });

  $("#savedOnly").addEventListener("click", (e) => {
    state.savedOnly = !state.savedOnly;
    e.currentTarget.setAttribute("aria-pressed", state.savedOnly);
    state.shown = PAGE;
    render();
  });

  $("#clearFilters").addEventListener("click", () => {
    Object.assign(state, { q: "", category: "", type: "", level: "", region: "", pakOnly: false, govOnly: false, savedOnly: false, shown: PAGE });
    $("#q").value = "";
    $("#region").value = "";
    $("#type").value = "";
    $("#level").value = "";
    $("#pakOnly").setAttribute("aria-pressed", "false");
    $("#govOnly").setAttribute("aria-pressed", "false");
    $("#savedOnly").setAttribute("aria-pressed", "false");
    render();
  });

  $("#loadMore").addEventListener("click", () => {
    state.shown += PAGE;
    render();
  });

  $("#jobList").addEventListener("click", (e) => {
    const b = e.target.closest("[data-save]");
    if (!b) return;
    const id = b.dataset.save;
    if (state.saved.has(id)) state.saved.delete(id);
    else state.saved.add(id);
    persistSaved();
    const now = state.saved.has(id);
    b.setAttribute("aria-pressed", now);
    b.innerHTML = ICON.star(now);
    if (state.savedOnly) render();
  });

  $("#themeBtn").addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    applyTheme(next);
    localStorage.setItem("rozgar-theme", next);
  });

  // keyboard: "/" focuses search
  document.addEventListener("keydown", (e) => {
    if (e.key === "/" && document.activeElement.tagName !== "INPUT") {
      e.preventDefault();
      $("#q").focus();
    }
  });
}

function applyTheme(mode) {
  document.documentElement.dataset.theme = mode;
  const lbl = $(".theme-label");
  if (lbl) lbl.textContent = mode === "dark" ? "Light" : "Dark";
}

/* ─────────────────────────────── boot */
async function boot() {
  const savedTheme = localStorage.getItem("rozgar-theme");
  const prefersDark = window.matchMedia?.("(prefers-color-scheme: dark)").matches;
  applyTheme(savedTheme || (prefersDark ? "dark" : "light"));

  loadSaved();
  $("#year").textContent = new Date().getFullYear();
  readUrl();
  renderPopular();

  try {
    const res = await fetch("data/jobs.json", { cache: "no-store" });
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();
    state.jobs = data.jobs || [];
    state.meta = data.meta || {};
    if (!state.jobs.length) throw new Error("no jobs");
  } catch (err) {
    console.error(err);
    $("#skeleton").innerHTML =
      '<div class="empty"><strong>Jobs could not be loaded.</strong><span>Open the site through a web server (GitHub Pages), not by double-clicking the file.</span></div>';
    return;
  }

  $("#skeleton").remove();
  renderStats();
  render();
  renderPkStrip();
  bind();
}

boot();
