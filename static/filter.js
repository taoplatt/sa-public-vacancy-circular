/* Progressive enhancement: filter, sort and paginate the vacancy list.
   With JavaScript off, every row is already in the page (server-rendered) and
   the browser's own find works; this only adds instant narrowing + paging. */
(function () {
  "use strict";
  var list = document.getElementById("job-list");
  if (!list) return;

  var I = window.__I18N__ || {};  // localized UI strings (English fallback)
  var PAGE_SIZE = 20;
  var rows = Array.prototype.slice.call(list.querySelectorAll(".job-row"));
  var today = list.getAttribute("data-today") || "";
  var soonCutoff = list.getAttribute("data-soon") || "";

  var q = document.getElementById("q");
  var fDept = document.getElementById("f-department");
  var fCat = document.getElementById("f-category");
  var fProv = document.getElementById("f-province");
  var fSalary = document.getElementById("f-salary");
  var fSoon = document.getElementById("f-soon");
  var sortSel = document.getElementById("sort");
  var reset = document.getElementById("reset");
  var countEl = document.getElementById("result-count");
  var emptyEl = document.getElementById("empty-state");
  var pager = document.getElementById("pager");

  var page = 1;
  var matched = [];

  // Collapsible filter panel (open on desktop, collapsed on small screens).
  var layout = document.querySelector(".layout");
  var toggleBtn = document.getElementById("toggle-filters");
  var toggleLabel = document.getElementById("toggle-filters-label");
  function setFilters(open) {
    if (!layout) return;
    layout.classList.toggle("filters-collapsed", !open);
    if (toggleBtn) toggleBtn.setAttribute("aria-expanded", open ? "true" : "false");
    if (toggleLabel) toggleLabel.textContent = open ? (I.hideFilters || "Hide filters") : (I.showFilters || "Show filters");
  }
  setFilters(!(window.matchMedia && window.matchMedia("(max-width: 899px)").matches));
  if (toggleBtn) {
    toggleBtn.addEventListener("click", function () {
      setFilters(layout.classList.contains("filters-collapsed"));
    });
  }

  function titleOf(r) {
    var t = r.querySelector(".row-title");
    return t ? t.textContent.toLowerCase() : "";
  }

  function ordered() {
    var mode = sortSel ? sortSel.value : "default";
    var arr = rows.slice();
    if (mode === "level-desc") {
      arr.sort(function (a, b) {
        return (parseInt(b.getAttribute("data-level"), 10) || 0) -
               (parseInt(a.getAttribute("data-level"), 10) || 0);
      });
    } else if (mode === "az") {
      arr.sort(function (a, b) { return titleOf(a) < titleOf(b) ? -1 : titleOf(a) > titleOf(b) ? 1 : 0; });
    } else {
      arr.sort(function (a, b) {
        return (parseInt(a.getAttribute("data-idx"), 10) || 0) -
               (parseInt(b.getAttribute("data-idx"), 10) || 0);
      });
    }
    return arr;
  }

  function salaryOk(row, band) {
    if (!band) return true;
    var v = parseInt(row.getAttribute("data-salary"), 10);
    if (!v) return false;
    var parts = band.split("-");
    var lo = parseInt(parts[0], 10) || 0;
    var hi = parts[1] ? parseInt(parts[1], 10) : Infinity;
    return v >= lo && v < hi;
  }

  function passes(row) {
    var term = (q && q.value ? q.value : "").trim().toLowerCase();
    if (term && row.getAttribute("data-search").indexOf(term) === -1) return false;
    if (fDept && fDept.value && row.getAttribute("data-department") !== fDept.value) return false;
    if (fCat && fCat.value && row.getAttribute("data-category") !== fCat.value) return false;
    if (fProv && fProv.value && row.getAttribute("data-province") !== fProv.value) return false;
    if (fSalary && !salaryOk(row, fSalary.value)) return false;
    if (fSoon && fSoon.checked) {
      var cl = row.getAttribute("data-closing");
      if (!cl || cl < today || (soonCutoff && cl > soonCutoff)) return false;
    }
    return true;
  }

  function recompute() {
    matched = ordered().filter(passes);
    // reflect order in the DOM so the visible page is in sorted order
    for (var i = 0; i < matched.length; i++) list.appendChild(matched[i]);
  }

  function renderPage() {
    var pages = Math.max(1, Math.ceil(matched.length / PAGE_SIZE));
    if (page > pages) page = pages;
    var start = (page - 1) * PAGE_SIZE, end = start + PAGE_SIZE;
    var inMatched = {};
    for (var i = 0; i < matched.length; i++) inMatched[matched[i].getAttribute("data-idx")] = i;
    for (var j = 0; j < rows.length; j++) {
      var r = rows[j];
      var pos = inMatched[r.getAttribute("data-idx")];
      r.hidden = !(pos !== undefined && pos >= start && pos < end);
    }
    if (countEl) countEl.innerHTML = "<strong>" + matched.length + "</strong> " + (matched.length === 1 ? (I.vacancy || "vacancy") : (I.vacancies || "vacancies"));
    if (emptyEl) emptyEl.hidden = matched.length !== 0;
    renderPager(pages);
  }

  function renderPager(pages) {
    if (!pager) return;
    if (pages <= 1) { pager.hidden = true; pager.innerHTML = ""; return; }
    pager.hidden = false;
    pager.innerHTML = "";
    var prev = document.createElement("button");
    prev.type = "button"; prev.textContent = I.prev || "‹ Previous"; prev.disabled = page <= 1;
    prev.addEventListener("click", function () { if (page > 1) { page--; renderPage(); scrollTop(); } });
    var info = document.createElement("span");
    info.className = "page-info";
    info.textContent = (I.pageOf || "Page {page} of {pages}").replace("{page}", page).replace("{pages}", pages);
    var next = document.createElement("button");
    next.type = "button"; next.textContent = I.next || "Next ›"; next.disabled = page >= pages;
    next.addEventListener("click", function () { if (page < pages) { page++; renderPage(); scrollTop(); } });
    pager.appendChild(prev); pager.appendChild(info); pager.appendChild(next);
  }

  function scrollTop() {
    var head = document.querySelector(".results-head");
    if (head) head.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function apply() { page = 1; recompute(); renderPage(); }

  var timer;
  if (q) q.addEventListener("input", function () { clearTimeout(timer); timer = setTimeout(apply, 130); });
  [fDept, fCat, fProv, fSalary, fSoon].forEach(function (el) { if (el) el.addEventListener("change", apply); });
  if (sortSel) sortSel.addEventListener("change", apply);
  if (reset) reset.addEventListener("click", function () {
    if (q) q.value = "";
    [fDept, fCat, fProv, fSalary].forEach(function (el) { if (el) el.value = ""; });
    if (fSoon) fSoon.checked = false;
    if (sortSel) sortSel.value = "default";
    apply();
  });

  apply();
})();
