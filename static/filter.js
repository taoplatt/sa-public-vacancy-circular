/* Progressive enhancement: client-side filtering + sorting of vacancy cards.
   With JavaScript off, every card is already in the page (server-rendered) and
   the browser's own find works. This only adds instant narrowing on top. */
(function () {
  "use strict";
  var grid = document.getElementById("job-grid");
  if (!grid) return;

  var cards = Array.prototype.slice.call(grid.querySelectorAll(".card"));
  var q = document.getElementById("q");
  var fProvince = document.getElementById("f-province");
  var fCategory = document.getElementById("f-category");
  var fLevel = document.getElementById("f-level");
  var fSoon = document.getElementById("f-soon");
  var sortSel = document.getElementById("sort");
  var reset = document.getElementById("reset");
  var count = document.getElementById("result-count");
  var empty = document.getElementById("empty-state");
  var today = grid.getAttribute("data-today") || "";

  function soonCutoff() {
    if (!today) return "";
    var d = new Date(today + "T00:00:00");
    d.setDate(d.getDate() + 14);
    return d.toISOString().slice(0, 10);
  }
  var cutoff = soonCutoff();

  function inBand(level, band) {
    if (!band) return true;
    if (!level) return false;
    var n = parseInt(level, 10);
    if (band === "1-4") return n >= 1 && n <= 4;
    if (band === "5-8") return n >= 5 && n <= 8;
    if (band === "9-12") return n >= 9 && n <= 12;
    if (band === "13-16") return n >= 13;
    return true;
  }

  function apply() {
    var term = (q && q.value ? q.value : "").trim().toLowerCase();
    var prov = fProvince ? fProvince.value : "";
    var cat = fCategory ? fCategory.value : "";
    var band = fLevel ? fLevel.value : "";
    var soon = fSoon ? fSoon.checked : false;
    var shown = 0;

    for (var i = 0; i < cards.length; i++) {
      var c = cards[i];
      var ok = true;
      if (term && c.getAttribute("data-search").indexOf(term) === -1) ok = false;
      if (ok && prov && c.getAttribute("data-province") !== prov) ok = false;
      if (ok && cat && c.getAttribute("data-category") !== cat) ok = false;
      if (ok && !inBand(c.getAttribute("data-level"), band)) ok = false;
      if (ok && soon) {
        var cl = c.getAttribute("data-closing");
        if (!cl || cl < today || (cutoff && cl > cutoff)) ok = false;
      }
      c.hidden = !ok;
      if (ok) shown++;
    }
    if (count) count.textContent = shown + (shown === 1 ? " vacancy" : " vacancies");
    if (empty) empty.hidden = shown !== 0;
  }

  function sortCards() {
    if (!sortSel) return;
    var mode = sortSel.value;
    var arr = cards.slice();
    arr.sort(function (a, b) {
      if (mode === "closing") {
        var ca = a.getAttribute("data-closing") || "9999-99-99";
        var cb = b.getAttribute("data-closing") || "9999-99-99";
        return ca < cb ? -1 : ca > cb ? 1 : 0;
      }
      if (mode === "level-desc") {
        return (parseInt(b.getAttribute("data-level"), 10) || 0) -
               (parseInt(a.getAttribute("data-level"), 10) || 0);
      }
      return (parseInt(a.getAttribute("data-idx"), 10) || 0) -
             (parseInt(b.getAttribute("data-idx"), 10) || 0);
    });
    for (var i = 0; i < arr.length; i++) grid.appendChild(arr[i]);
  }

  var timer;
  function debounced() { clearTimeout(timer); timer = setTimeout(apply, 120); }

  if (q) q.addEventListener("input", debounced);
  [fProvince, fCategory, fLevel, fSoon].forEach(function (el) {
    if (el) el.addEventListener("change", apply);
  });
  if (sortSel) sortSel.addEventListener("change", function () { sortCards(); apply(); });
  if (reset) reset.addEventListener("click", function () {
    if (q) q.value = "";
    [fProvince, fCategory, fLevel].forEach(function (el) { if (el) el.value = ""; });
    if (fSoon) fSoon.checked = false;
    if (sortSel) sortSel.value = "default";
    sortCards();
    apply();
  });

  apply();
})();
