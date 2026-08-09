/**
 * krizky-filters — in-browser filtering via progressive enhancement.
 *
 * Reads filter config from <script type="application/json" id="filter-config">,
 * fetches a compact JSON file, and filters records client-side.
 *
 * Filtering logic: AND between dimensions, OR within a dimension.
 * - For many:true dimensions (JSON arrays): record must contain AT LEAST ONE active value.
 * - For other dimensions: record value must be one of the active slugs.
 *   (select type enforces max 1 active value via UI)
 *
 * URL state: ?dim1=val1,val2&dim2=val3  (slugs, comma-separated per dimension)
 */
(function () {
  "use strict";

  // ── Bootstrap ────────────────────────────────────────────────────────────

  const configEl = document.getElementById("filter-config");
  if (!configEl) return;

  let config;
  try {
    config = JSON.parse(configEl.textContent);
  } catch (e) {
    return;
  }

  const { jsonUrl, pageSize, gridSelector, dimensions } = config;
  const grid = document.querySelector(gridSelector);
  if (!grid) return;

  /** @type {Map<string, Set<string>>} dim → active slugs */
  const state = new Map();

  let allRecords = [];
  let currentPage = 1;

  // ── Load data ─────────────────────────────────────────────────────────────

  fetch(jsonUrl)
    .then((r) => r.json())
    .then((data) => {
      allRecords = data;
      // Hide static (server-rendered) pagination — JS takes over from here.
      document.querySelectorAll("[data-static-pagination]").forEach((el) => {
        el.hidden = true;
      });
      parseUrlState();
      attachPillListeners();
      window.addEventListener("popstate", () => {
        parseUrlState();
        filterAndRender();
      });
      filterAndRender();
    })
    .catch(() => {
      /* silently fall back to static rendering */
    });

  // ── URL state ─────────────────────────────────────────────────────────────

  function parseUrlState() {
    state.clear();
    const params = new URLSearchParams(location.search);
    for (const [dim] of Object.entries(dimensions)) {
      const raw = params.get(dim);
      if (raw) {
        state.set(dim, new Set(raw.split(",").filter(Boolean)));
      }
    }
    currentPage = 1;
  }

  function serializeState() {
    const params = new URLSearchParams();
    for (const [dim, values] of state) {
      if (values.size > 0) {
        params.set(dim, [...values].join(","));
      }
    }
    return params.toString();
  }

  // ── Pill listeners ────────────────────────────────────────────────────────

  function attachPillListeners() {
    document.querySelectorAll("[data-filter-value][data-filter-dimension]").forEach((pill) => {
      pill.addEventListener("click", (e) => {
        e.preventDefault();
        const dim = pill.dataset.filterDimension;
        const slug = pill.dataset.filterValue;
        const dimCfg = dimensions[dim];
        if (!dimCfg) return;

        let active = state.get(dim) || new Set();

        if (dimCfg.type === "select") {
          // radio-like: clicking active value deselects; otherwise replace
          if (active.has(slug)) {
            active = new Set();
          } else {
            active = new Set([slug]);
          }
        } else {
          // multiselect: toggle
          active = new Set(active);
          if (active.has(slug)) {
            active.delete(slug);
          } else {
            active.add(slug);
          }
        }

        if (active.size > 0) {
          state.set(dim, active);
        } else {
          state.delete(dim);
        }

        currentPage = 1;
        const qs = serializeState();
        history.pushState({}, "", qs ? "?" + qs : location.pathname);
        filterAndRender();
      });
    });
  }

  // ── Filter ────────────────────────────────────────────────────────────────

  function matchesFilter(record) {
    for (const [dim, active] of state) {
      if (active.size === 0) continue;
      const dimCfg = dimensions[dim];
      if (!dimCfg) continue;
      const val = record[dim];

      if (dimCfg.many) {
        // OR within dimension: at least one value's slug must be active.
        // stitky_slug is a {value: slug} object — use it to resolve slugs.
        const valArr = Array.isArray(val) ? val : [];
        const slugObj = record[dim + "_slug"];
        const slugArr = (slugObj && typeof slugObj === "object" && !Array.isArray(slugObj))
          ? valArr.map((v) => slugObj[v] ?? String(v))
          : valArr.map(String);
        if (!slugArr.some((s) => active.has(s))) return false;
      } else {
        // OR within dimension: prefer {dim}_slug field over raw value field.
        const slugVal = String(record[dim + "_slug"] ?? val ?? "");
        if (!active.has(slugVal)) return false;
      }
    }
    return true;
  }

  // ── Render ────────────────────────────────────────────────────────────────

  function filterAndRender() {
    const filtered = allRecords.filter(matchesFilter);
    updatePillStates();

    const total = filtered.length;
    const size = pageSize > 0 ? pageSize : total;
    const totalPages = size > 0 ? Math.max(1, Math.ceil(total / size)) : 1;
    if (currentPage > totalPages) currentPage = 1;

    const start = (currentPage - 1) * size;
    const pageRecords = filtered.slice(start, start + size);

    renderCards(pageRecords);
    renderPagination(currentPage, totalPages, total);
  }

  function renderCards(records) {
    const tmpl = document.getElementById("card-template");
    if (!tmpl) {
      grid.innerHTML = "";
      return;
    }

    grid.classList.add("is-loading");
    const fragment = document.createDocumentFragment();

    records.forEach((record) => {
      const clone = tmpl.content.cloneNode(true);
      clone.querySelectorAll("[data-field]").forEach((el) => {
        const field = el.dataset.field;
        const val = record[field] ?? "";

        if (el.tagName === "IMG") {
          el.src = String(val);
        } else if (el.tagName === "A") {
          const pattern = el.dataset.hrefPattern;
          el.href = pattern ? pattern.replace("{value}", String(val)) : String(val);
        } else if (Array.isArray(val)) {
          const itemClass = el.dataset.fieldItemClass || "";
          if (val.length === 0) {
            el.hidden = true;
          } else {
            el.hidden = false;
            el.innerHTML = val
              .map((v) => `<span class="${itemClass}">${escapeHtml(String(v))}</span>`)
              .join("");
          }
        } else if (el.dataset.truncate) {
          const max = parseInt(el.dataset.truncate, 10);
          const str = String(val);
          el.textContent = str.length > max ? str.slice(0, max).trimEnd() + "…" : str;
        } else if (el.dataset.dateFormat && val) {
          el.textContent = formatDate(String(val), el.dataset.dateFormat);
        } else {
          el.textContent = String(val);
        }
      });
      fragment.appendChild(clone);
    });

    grid.innerHTML = "";
    grid.appendChild(fragment);
    grid.classList.remove("is-loading");
  }

  function escapeHtml(str) {
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function formatDate(dateStr, fmt) {
    const d = new Date(dateStr.replace(" ", "T"));
    if (isNaN(d.getTime())) return dateStr;
    const day = d.getDate();
    const month = d.getMonth() + 1;
    const year = d.getFullYear();
    return fmt
      .replace(/%-d/g, String(day))
      .replace(/%d/g, String(day).padStart(2, "0"))
      .replace(/%-m/g, String(month))
      .replace(/%m/g, String(month).padStart(2, "0"))
      .replace(/%Y/g, String(year))
      .replace(/%y/g, String(year).slice(-2));
  }

  // ── Pagination ────────────────────────────────────────────────────────────

  let paginationEl = null;

  function renderPagination(page, totalPages, total) {
    if (!paginationEl) {
      paginationEl = document.querySelector("[data-filter-pagination]");
    }
    if (!paginationEl) return;

    if (totalPages <= 1) {
      paginationEl.hidden = true;
      return;
    }

    paginationEl.hidden = false;
    const prevBtn = paginationEl.querySelector("[data-filter-prev]");
    const nextBtn = paginationEl.querySelector("[data-filter-next]");
    const info = paginationEl.querySelector("[data-filter-page-info]");

    if (prevBtn) {
      prevBtn.disabled = page <= 1;
      prevBtn.onclick = () => { currentPage--; filterAndRender(); };
    }
    if (nextBtn) {
      nextBtn.disabled = page >= totalPages;
      nextBtn.onclick = () => { currentPage++; filterAndRender(); };
    }
    if (info) {
      info.textContent = `${page} / ${totalPages}`;
    }
  }

  // ── Pill active states ────────────────────────────────────────────────────

  function updatePillStates() {
    document.querySelectorAll("[data-filter-value][data-filter-dimension]").forEach((pill) => {
      const dim = pill.dataset.filterDimension;
      const slug = pill.dataset.filterValue;
      const active = state.get(dim);
      const isActive = active ? active.has(slug) : false;
      pill.classList.toggle("pill--active", isActive);
      pill.setAttribute("aria-pressed", String(isActive));
    });
  }
})();
