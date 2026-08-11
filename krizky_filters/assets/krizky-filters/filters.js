/**
 * krizky-filters — in-browser filtering via progressive enhancement.
 *
 * Reads filter config from <script type="application/json" id="filter-config">,
 * fetches a compact JSON file, and filters records client-side.
 *
 * Filtering logic: AND between dimensions, OR within a dimension.
 * - For many:true dimensions (JSON arrays): record must contain AT LEAST ONE active value.
 * - For other dimensions: record value must be one of the active slugs.
 *
 * URL state: path encodes page (/page-2.html), query encodes filters (?dim=val1,val2)
 *
 * UI hook points (add to any element in your template to opt in):
 *   [data-filter-value][data-filter-dimension]  clickable filter control (pill, checkbox, …)
 *   [data-filter-clear]                         button: clear all active filters
 *   [data-filter-active-list]                   container: JS inserts removable chips here
 *   [data-filter-count-filtered]                shows current filtered record count
 *   [data-filter-count-total]                   shows total record count
 *   [data-filter-count]                         single element with {filtered}/{total} template
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

  const { jsonUrl, basePath, pageSize, gridSelector, dimensions } = config;
  const paginationWindow = config.window ?? 2;
  const paginationBoundary = config.boundary ?? 1;
  const facetsEnabled = config.facets === true;
  const facetsMode = config.facetsMode || "hide";  // "hide" | "disable"
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
      attachFilterListeners();
      attachClearListeners();
      attachTextListeners();
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

  // Equivalent of Python render.page_path(): /base.html → /base-N.html for N>1.
  function pagePath(base, pageNum) {
    if (pageNum === 1) return base;
    const dot = base.lastIndexOf(".");
    return dot < 0
      ? base + "-" + pageNum
      : base.slice(0, dot) + "-" + pageNum + base.slice(dot);
  }

  // Parse current page number from URL path using the same scheme as server.
  function pageFromPath(base) {
    const path = location.pathname;
    if (path === base) return 1;
    const dot = base.lastIndexOf(".");
    if (dot < 0) return 1;
    const stem = base.slice(0, dot);
    const ext = base.slice(dot);
    const match = path.slice(stem.length).match(/^-(\d+)(.*)$/);
    return (match && match[2] === ext) ? parseInt(match[1], 10) : 1;
  }

  function parseUrlState() {
    state.clear();
    const params = new URLSearchParams(location.search);
    for (const [dim, dimCfg] of Object.entries(dimensions)) {
      const raw = params.get(dim);
      if (!raw) continue;
      if (dimCfg.type === "text") {
        // Text queries can contain any character (including commas) — no split.
        state.set(dim, new Set([raw]));
      } else {
        state.set(dim, new Set(raw.split(",").filter(Boolean)));
      }
    }
    currentPage = pageFromPath(basePath);
  }

  function serializeState() {
    const params = new URLSearchParams();
    for (const [dim, values] of state) {
      if (values.size > 0) params.set(dim, [...values].join(","));
    }
    return params.toString();
  }

  // NFKD-normalized text (strip diacritics, lowercase) — used for full-text search.
  function normalizeText(s) {
    return String(s || "").toLowerCase().normalize("NFKD").replace(/[̀-ͯ]/g, "");
  }

  // Build full href for page N: path encodes page number, query encodes filters.
  function pageHref(pageNum) {
    const qs = serializeState();
    return pagePath(basePath, pageNum) + (qs ? "?" + qs : "");
  }

  function updateUrl() {
    history.pushState({}, "", pageHref(currentPage));
  }

  // ── Filter control listeners ──────────────────────────────────────────────

  function attachFilterListeners() {
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
        updateUrl();
        filterAndRender();
      });
    });
  }

  // ── Filter ────────────────────────────────────────────────────────────────

  // Extract slugs a record has for a given dimension (single or many).
  function recordSlugs(record, dim) {
    const dimCfg = dimensions[dim];
    if (!dimCfg) return [];
    const val = record[dim];
    if (dimCfg.many) {
      const valArr = Array.isArray(val) ? val : [];
      const slugObj = record[dim + "_slug"];
      return (slugObj && typeof slugObj === "object" && !Array.isArray(slugObj))
        ? valArr.map((v) => slugObj[v] ?? String(v))
        : valArr.map(String);
    }
    return [String(record[dim + "_slug"] ?? val ?? "")];
  }

  // True if a record matches the filter on ONE dimension (OR within dim,
  // substring match for text dims).
  function matchesDim(record, dim, active) {
    if (active.size === 0) return true;
    const dimCfg = dimensions[dim];
    if (dimCfg && dimCfg.type === "text") {
      const query = normalizeText([...active][0]);
      if (!query) return true;
      const fields = dimCfg.searchFields || [];
      return fields.some((f) => normalizeText(record[f]).includes(query));
    }
    return recordSlugs(record, dim).some((s) => active.has(s));
  }

  // True if a record matches ALL active filters (AND between dims).
  function matchesFilter(record) {
    for (const [dim, active] of state) {
      if (!matchesDim(record, dim, active)) return false;
    }
    return true;
  }

  // Records that match every active filter EXCEPT the one on `excludeDim`.
  // Used for faceted counting: available values per dim reflect the intersection
  // of all OTHER active filters (facet self-exclusion rule).
  function matchesAllExcept(record, excludeDim) {
    for (const [dim, active] of state) {
      if (dim === excludeDim) continue;
      if (!matchesDim(record, dim, active)) return false;
    }
    return true;
  }

  // ── Facets ────────────────────────────────────────────────────────────────

  // For each dim, count how many records would have each slug value
  // if only OTHER dims' filters were applied.
  function computeFacets() {
    const facets = {};
    for (const dim of Object.keys(dimensions)) {
      // Text dims have no discrete values — nothing to facet-count.
      if (dimensions[dim].type === "text") continue;
      const subset = allRecords.filter((r) => matchesAllExcept(r, dim));
      const counts = {};
      for (const record of subset) {
        for (const slug of recordSlugs(record, dim)) {
          if (!slug) continue;
          counts[slug] = (counts[slug] || 0) + 1;
        }
      }
      facets[dim] = counts;
    }
    return facets;
  }

  // ── Sort (parallel to Python values.py::_parse_sort) ─────────────────────

  const SORT_ALIASES = {
    count: "-count,alpha",   // popularity preset
    alpha: "alpha",
  };

  function parseSort(spec) {
    let s = (spec || "count").trim();
    if (s in SORT_ALIASES) s = SORT_ALIASES[s];
    const out = [];
    for (let part of s.split(",")) {
      part = part.trim();
      if (!part) continue;
      const desc = part.startsWith("-");
      const field = part.replace(/^-+/, "");
      if (field === "count" || field === "alpha") out.push([field, desc]);
    }
    return out;
  }

  // Locale-friendly alpha key — strips diacritics so 'č' sorts near 'c'.
  function sortKeyAlpha(text) {
    return (text || "").toLowerCase().normalize("NFKD").replace(/[̀-ͯ]/g, "");
  }

  // Re-order [data-filter-value] elements per dimension based on their current
  // facet counts + display label. Called after applyFacets to sync DOM with
  // dynamic counts.
  function reorderValues() {
    const groups = new Map();
    document.querySelectorAll("[data-filter-value][data-filter-dimension]").forEach((el) => {
      const dim = el.dataset.filterDimension;
      if (!groups.has(dim)) groups.set(dim, []);
      groups.get(dim).push(el);
    });

    for (const [dim, items] of groups) {
      const dimCfg = dimensions[dim];
      if (!dimCfg) continue;
      const parsed = parseSort(dimCfg.sort);
      if (parsed.length === 0) continue;

      const wrapped = items.map((el) => {
        const wrap = el.closest("[data-combobox-option]") || el;
        const countEl = el.querySelector("[data-facet-count]");
        const count = countEl ? (parseInt(countEl.textContent, 10) || 0) : 0;
        const labelEl = el.querySelector(".fbar-item-label");
        const label = labelEl ? labelEl.textContent : el.textContent;
        return { wrap, count, alphaKey: sortKeyAlpha(label) };
      });

      // Stable sort: apply least-significant key first.
      for (const [field, desc] of [...parsed].reverse()) {
        wrapped.sort((a, b) => {
          const va = field === "count" ? a.count : a.alphaKey;
          const vb = field === "count" ? b.count : b.alphaKey;
          if (va < vb) return desc ? 1 : -1;
          if (va > vb) return desc ? -1 : 1;
          return 0;
        });
      }

      const parent = wrapped.length > 0 ? wrapped[0].wrap.parentNode : null;
      if (parent) wrapped.forEach(({ wrap }) => parent.appendChild(wrap));
    }
  }

  // Apply facet counts to the DOM: update count elements, hide/disable
  // zero-count values, disable dims where nothing is available.
  function applyFacets(facets) {
    const dimAvailable = {};

    document.querySelectorAll("[data-filter-value][data-filter-dimension]").forEach((el) => {
      const dim = el.dataset.filterDimension;
      const slug = el.dataset.filterValue;
      const count = (facets[dim] && facets[dim][slug]) || 0;

      // Update visible count if a count element exists
      const countEl = el.querySelector("[data-facet-count]");
      if (countEl) countEl.textContent = count;

      const wrap = el.closest("[data-combobox-option]") || el;
      if (count === 0) {
        if (facetsMode === "hide") {
          wrap.hidden = true;
          wrap.setAttribute("data-facet-hidden", "");
        } else {
          wrap.classList.add("is-disabled");
          wrap.setAttribute("aria-disabled", "true");
          wrap.removeAttribute("data-facet-hidden");
        }
      } else {
        wrap.hidden = false;
        wrap.classList.remove("is-disabled");
        wrap.removeAttribute("aria-disabled");
        wrap.removeAttribute("data-facet-hidden");
      }

      if (!dimAvailable[dim]) dimAvailable[dim] = 0;
      if (count > 0) dimAvailable[dim] += 1;
    });

    // Disable whole dimension when nothing is available (unless it has an
    // active filter — user must be able to unset it).
    document.querySelectorAll("[data-combobox]").forEach((cb) => {
      const dim = cb.dataset.comboboxDim;
      if (!dim) return;
      const hasActive = state.has(dim) && state.get(dim).size > 0;
      const hasAvailable = (dimAvailable[dim] || 0) > 0;
      const disabled = !hasActive && !hasAvailable;
      cb.classList.toggle("is-disabled", disabled);
      const trigger = cb.querySelector("[data-combobox-trigger]");
      if (trigger) trigger.setAttribute("aria-disabled", String(disabled));
    });
  }

  // ── Render ────────────────────────────────────────────────────────────────

  function filterAndRender() {
    const filtered = allRecords.filter(matchesFilter);
    updateFilterStates();
    updateFilterCount(filtered.length, allRecords.length);
    updateActiveList();
    updateClearButton();
    syncTextInputs();

    const facets = facetsEnabled ? computeFacets() : null;
    if (facets) {
      applyFacets(facets);
      reorderValues();
    }

    const total = filtered.length;
    const size = pageSize > 0 ? pageSize : total;
    const totalPages = size > 0 ? Math.max(1, Math.ceil(total / size)) : 1;
    if (currentPage > totalPages) currentPage = 1;

    const start = (currentPage - 1) * size;
    const pageRecords = filtered.slice(start, start + size);

    renderCards(pageRecords);
    renderPagination(currentPage, totalPages);

    // Notify other scripts (e.g. custom widgets) about the updated filter state.
    document.dispatchEvent(new CustomEvent("krizky-filters:update", {
      detail: {
        filtered: filtered.length,
        total: allRecords.length,
        activeState: Object.fromEntries([...state].map(([k, v]) => [k, [...v]])),
        facets: facets,  // null when facets disabled
      },
    }));
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
        } else if ("fieldItemClass" in el.dataset) {
          // Array field: data-field-item-class declares this element expects a list.
          // Treat non-array values (null, string) as empty to avoid showing stale
          // template content from the first record.
          const arr = Array.isArray(val) ? val : [];
          const itemClass = el.dataset.fieldItemClass || "";
          el.innerHTML = arr
            .map((v) => `<span class="${itemClass}">${escapeHtml(String(v))}</span>`)
            .join("");
          el.hidden = arr.length === 0;
        } else if (el.dataset.truncate) {
          const length = parseInt(el.dataset.truncate, 10);
          const killwords = "truncateKillwords" in el.dataset;
          const end = el.dataset.truncateEnd ?? "...";
          const leeway = el.dataset.truncateLeeway !== undefined
            ? parseInt(el.dataset.truncateLeeway, 10) : 5;
          el.textContent = jinjaTruncate(String(val), length, killwords, end, leeway);
        } else if (el.dataset.dateFormat && val) {
          el.textContent = formatDate(String(val), el.dataset.dateFormat);
        } else {
          el.textContent = String(val);
        }
      });
      // data-field-photo: construct photo URL from row ID + size + format
      clone.querySelectorAll("[data-field-photo]").forEach((el) => {
        const rowId = record[el.dataset.fieldPhoto];
        if (!rowId || !config.photosBaseUrl) {
          el.hidden = true;
          return;
        }
        const pad = parseInt(el.dataset.photoPad ?? "3", 10);
        const size = el.dataset.photoSize || "thumb";
        const fmt = el.dataset.photoFormat || "jpg";
        const paddedId = String(rowId).padStart(pad, "0");
        el.src = `${config.photosBaseUrl}/${paddedId}_${size}.${fmt}`;
        el.hidden = false;
        el.onload = () => {
          const thumb = el.closest("[data-thumb]");
          if (thumb) thumb.classList.remove("placeholder");
        };
        el.onerror = () => { el.hidden = true; };
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

  // Equivalent of Jinja2's do_truncate (same defaults: killwords=false, end="...", leeway=5).
  function jinjaTruncate(s, length, killwords, end, leeway) {
    if (s.length <= length + leeway) return s;
    if (killwords) return s.slice(0, length - end.length) + end;
    const cut = s.slice(0, length - end.length);
    const lastSpace = cut.lastIndexOf(" ");
    return (lastSpace >= 0 ? cut.slice(0, lastSpace) : cut) + end;
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

  // Exact JS equivalent of krizky's Python _pagination_pages().
  // Returns array of page numbers with null for ellipsis gaps.
  function paginationPages(current, total, win, boundary) {
    const visible = new Set();
    for (let i = 1; i <= Math.min(boundary, total); i++) visible.add(i);
    for (let i = Math.max(total - boundary + 1, 1); i <= total; i++) visible.add(i);
    for (let i = Math.max(1, current - win); i <= Math.min(total, current + win); i++) visible.add(i);

    const result = [];
    let prev = null;
    for (const p of [...visible].sort((a, b) => a - b)) {
      if (prev !== null && p - prev > 1) result.push(null);
      result.push(p);
      prev = p;
    }
    return result;
  }

  function goToPage(n) {
    currentPage = n;
    updateUrl();
    filterAndRender();
    window.scrollTo(0, 0);
  }

  function renderPagination(page, totalPages) {
    if (!paginationEl) {
      paginationEl = document.querySelector("[data-filter-pagination]");
    }
    if (!paginationEl) return;

    if (totalPages <= 1) {
      paginationEl.hidden = true;
      paginationEl.innerHTML = "";
      return;
    }

    const hasPrev = page > 1;
    const hasNext = page < totalPages;

    const prevBtn = hasPrev
      ? `<a href="${pageHref(page - 1)}" class="page-btn page-prev" data-filter-prev><span class="arrow">‹</span> <span class="btn-text">předchozí</span></a>`
      : `<span class="page-btn page-prev is-disabled"><span class="arrow">‹</span> <span class="btn-text">předchozí</span></span>`;

    const nextBtn = hasNext
      ? `<a href="${pageHref(page + 1)}" class="page-btn page-next" data-filter-next><span class="btn-text">další</span> <span class="arrow">›</span></a>`
      : `<span class="page-btn page-next is-disabled"><span class="btn-text">další</span> <span class="arrow">›</span></span>`;

    const pages = paginationPages(page, totalPages, paginationWindow, paginationBoundary);
    const items = pages
      .map((p) => {
        if (p === null) return `<li class="page-dots" aria-hidden="true">&hellip;</li>`;
        if (p === page) return `<li><a href="${pageHref(p)}" class="page-num is-current" aria-current="page">${p}</a></li>`;
        return `<li><a href="${pageHref(p)}" class="page-num" data-filter-page="${p}">${p}</a></li>`;
      })
      .join("");

    paginationEl.innerHTML = `<nav class="pagination" aria-label="Stránkování">${prevBtn}<ul class="page-list">${items}</ul>${nextBtn}</nav>`;
    paginationEl.hidden = false;

    const prev = paginationEl.querySelector("[data-filter-prev]");
    const next = paginationEl.querySelector("[data-filter-next]");
    if (prev) prev.addEventListener("click", (e) => { e.preventDefault(); goToPage(currentPage - 1); });
    if (next) next.addEventListener("click", (e) => { e.preventDefault(); goToPage(currentPage + 1); });
    paginationEl.querySelectorAll("[data-filter-page]").forEach((a) => {
      a.addEventListener("click", (e) => {
        e.preventDefault();
        goToPage(parseInt(a.dataset.filterPage, 10));
      });
    });
  }

  // ── Filter state display ──────────────────────────────────────────────────

  // Toggle active class on every [data-filter-value] control (pill, checkbox, …).
  function updateFilterStates() {
    document.querySelectorAll("[data-filter-value][data-filter-dimension]").forEach((el) => {
      const dim = el.dataset.filterDimension;
      const slug = el.dataset.filterValue;
      const active = state.get(dim);
      const isActive = active ? active.has(slug) : false;
      el.classList.toggle("pill--active", isActive);
      el.setAttribute("aria-pressed", String(isActive));
    });
  }

  // Update count elements.
  function updateFilterCount(filteredCount, totalCount) {
    document.querySelectorAll("[data-filter-count-filtered]").forEach((el) => {
      el.textContent = filteredCount;
    });
    document.querySelectorAll("[data-filter-count-total]").forEach((el) => {
      el.textContent = totalCount;
    });
    // Single-element variant: <span data-filter-count>{filtered} z {total}</span>
    // Original text is used as template on first call, then stored in data-filter-count-orig.
    document.querySelectorAll("[data-filter-count]").forEach((el) => {
      if (!el.dataset.filterCountOrig) el.dataset.filterCountOrig = el.textContent;
      el.textContent = el.dataset.filterCountOrig
        .replace("{filtered}", filteredCount)
        .replace("{total}", totalCount);
    });
  }

  // Render removable chips for each active filter value into [data-filter-active-list].
  // Label is read from the matching [data-filter-value] control in the DOM;
  // falls back to the raw slug if the control element is not found.
  function updateActiveList() {
    document.querySelectorAll("[data-filter-active-list]").forEach((container) => {
      container.innerHTML = "";
      for (const [dim, values] of state) {
        for (const slug of values) {
          const controlEl = document.querySelector(
            `[data-filter-value="${CSS.escape(slug)}"][data-filter-dimension="${CSS.escape(dim)}"]`
          );
          const label = controlEl ? controlEl.textContent.trim() : slug;
          const chip = document.createElement("button");
          chip.type = "button";
          chip.className = "filter-chip";
          chip.textContent = label;
          chip.addEventListener("click", () => removeFilterValue(dim, slug));
          container.appendChild(chip);
        }
      }
    });
  }

  function removeFilterValue(dim, slug) {
    const active = state.get(dim);
    if (active) {
      active.delete(slug);
      if (active.size === 0) state.delete(dim);
    }
    currentPage = 1;
    updateUrl();
    filterAndRender();
  }

  // Show [data-filter-clear] only when at least one filter is active.
  function updateClearButton() {
    const hasActive = state.size > 0;
    document.querySelectorAll("[data-filter-clear]").forEach((el) => {
      el.hidden = !hasActive;
    });
  }

  function attachClearListeners() {
    // Event delegation handles both static and dynamically inserted clear buttons.
    document.addEventListener("click", (e) => {
      // [data-filter-clear] — clear all active filters
      if (e.target.closest("[data-filter-clear]") && !e.target.closest("[data-filter-clear-dim]")) {
        e.preventDefault();
        state.clear();
        currentPage = 1;
        updateUrl();
        filterAndRender();
        return;
      }
      // [data-filter-clear-dim="dim"] — clear one dimension (e.g. combobox trigger ×)
      const dimBtn = e.target.closest("[data-filter-clear-dim]");
      if (dimBtn) {
        e.preventDefault();
        e.stopPropagation();
        state.delete(dimBtn.dataset.filterClearDim);
        currentPage = 1;
        updateUrl();
        filterAndRender();
      }
    });
  }

  // ── Text input (full-text search) ─────────────────────────────────────────

  const TEXT_DEBOUNCE_MS = 200;

  function attachTextListeners() {
    document.querySelectorAll("[data-filter-text-dimension]").forEach((input) => {
      const dim = input.dataset.filterTextDimension;
      if (!dimensions[dim] || dimensions[dim].type !== "text") return;
      let timer = null;
      input.addEventListener("input", () => {
        clearTimeout(timer);
        timer = setTimeout(() => {
          const q = input.value.trim();
          if (q) {
            state.set(dim, new Set([q]));
          } else {
            state.delete(dim);
          }
          currentPage = 1;
          updateUrl();
          filterAndRender();
        }, TEXT_DEBOUNCE_MS);
      });
    });
  }

  // Reflect URL state back into text inputs (popstate / initial load).
  // Skip inputs currently focused so we never overwrite what the user is typing.
  function syncTextInputs() {
    document.querySelectorAll("[data-filter-text-dimension]").forEach((input) => {
      const dim = input.dataset.filterTextDimension;
      const active = state.get(dim);
      const val = (active && active.size > 0) ? [...active][0] : "";
      if (document.activeElement !== input && input.value !== val) {
        input.value = val;
      }
    });
  }
})();
