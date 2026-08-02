"""The single-page Standpoint GUI as one self-contained HTML string.

No build step, no framework, no npm: vanilla JavaScript + Tailwind (Play CDN) +
vega-embed (to render the Vega-Lite spec live in the browser) + marked (to render the
Markdown analysis). `standpoint.api` serves this at ``GET /gui``.

Kept as a Python string (rather than a static file) so it ships inside the package:
the whole GUI is a two-file backend plus this one-string frontend.
"""

from __future__ import annotations

# The whole page. Tailwind classes carry the styling; the <script> holds a small,
# dependency-free controller: build an editable grid, serialize it to CSV, POST it,
# then render the returned Vega-Lite spec and Markdown.
GUI_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="description" content="Standpoint turns a comparison table into a 2D positioning map with a written analysis. Everything runs on your machine." />
  <title>Standpoint: table to quadrant</title>
  <!-- App icon set generated from assets/logo.png; served by api.py under /static. -->
  <link rel="icon" href="/favicon.ico" sizes="any" />
  <link rel="icon" type="image/png" sizes="32x32" href="/static/favicon-32.png" />
  <link rel="icon" type="image/png" sizes="16x16" href="/static/favicon-16.png" />
  <link rel="apple-touch-icon" sizes="180x180" href="/static/apple-touch-icon.png" />
  <link rel="manifest" href="/site.webmanifest" />
  <meta name="theme-color" content="#0B0B0C" />
  <!-- Roboto family, to match the sprezzature look and feel (harchaoui.org). -->
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700;800&family=Roboto+Serif:wght@400;500;600&family=Roboto+Mono&display=swap" rel="stylesheet" />
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/vega@5"></script>
  <script src="https://cdn.jsdelivr.net/npm/vega-lite@5"></script>
  <script src="https://cdn.jsdelivr.net/npm/vega-embed@6"></script>
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <style>
    /* The "Good Colors" DATA palette (https://harchaoui.org/warith/colors/) is
       reserved for DATA only: the dots on the map and the role-tinted names in the
       analysis. The UI chrome (accents, buttons, headings) stays NEUTRAL slate/ink,
       so a colour in this app always means "data", never decoration. */
    :root {
      --red:#FF3B30; --blue:#007AFF; --purple:#AF52DE; --brown:#A52A2A;  /* roles */
      --ink:#171717; --paper:#FAFAFA; --slate:#a3a3a3;                    /* chrome */
    }
    body { font-family: Roboto, system-ui, -apple-system, Helvetica, Arial, sans-serif;
           background: var(--paper); -webkit-font-smoothing: antialiased; }
    /* Sprezzature look and feel (harchaoui.org/warith/sprezzature): a serif display
       headline over sans body copy, and a small monospace "eyebrow" tag above it. */
    .headline { font-family: "Roboto Serif", Georgia, serif; }
    .eyebrow { font-family: "Roboto Mono", ui-monospace, SFMono-Regular, monospace; }
    /* Grid inputs sized to their content: numeric value cells fill their column
       (see the w-full inputs in renderGrid), while option (row) names and criterion
       (column) names get fixed room so nothing truncates and columns stay aligned. */
    .cell-name { width: 12rem; }    /* option / row names + first-column header */
    .cell-head { width: 7rem; }     /* criterion / column names (header) */
    /* A small NEUTRAL accent bar that heads each step (chrome, not data). */
    .accent { width: .6rem; height: 1.6rem; border-radius: .3rem; display: inline-block; background: var(--slate); }
    /* Visible keyboard focus everywhere (accessibility), neutral, not the data blue. */
    input:focus-visible, select:focus-visible, button:focus-visible, label:focus-within {
      outline: 2px solid #64748b; outline-offset: 2px;
    }
    #chart.checker { background-image:
      linear-gradient(45deg,#eee 25%,transparent 25%),
      linear-gradient(-45deg,#eee 25%,transparent 25%),
      linear-gradient(45deg,transparent 75%,#eee 75%),
      linear-gradient(-45deg,transparent 75%,#eee 75%);
      background-size: 20px 20px;
      background-position: 0 0, 0 10px, 10px -10px, -10px 0; }
    /* Scale the rendered map down to fit the card (SVG stays crisp); exports use
       the Vega view at native resolution, so this only affects on-screen size. */
    #chart svg, #chart canvas { max-width: 100%; height: auto; display: block; margin: 0 auto; }
    /* The analysis panel, coloured to echo the map (Tailwind's CDN has no prose
       plugin, so the rendered Markdown is themed here by hand). */
    .analysis { color:#1c1c1e; line-height:1.65; }
    .analysis h1 { font-size:1.5rem; font-weight:800; color:var(--ink); margin:.1rem 0 .6rem; }
    .analysis h2 { font-size:1.05rem; font-weight:700; color:var(--ink);
      border-bottom:2px solid #e2e8f0; padding-bottom:.25rem; margin:1.4rem 0 .5rem; }
    .analysis p { margin:.6rem 0; }
    .analysis strong { color:var(--ink); }
    .analysis ul { margin:.5rem 0; padding-left:1.25rem; list-style:disc; }
    .analysis li { margin:.3rem 0; }
    /* Option names tinted by their role, matching the dots on the map. */
    .role-best  { color:var(--red);    font-weight:700; }
    .role-worst { color:var(--brown);  font-weight:700; }
    .role-top   { color:var(--purple); font-weight:700; }
    .role-right { color:var(--blue);   font-weight:700; }

    /* --- Dark theme -------------------------------------------------------
       Driven by a `dark` class on <html> (toggled by the header 🌞/🌛 button and
       persisted in localStorage). Rather than sprinkle Tailwind `dark:` variants over
       every element, we remap the handful of neutral chrome utilities the page uses;
       `.dark .x` (specificity 0,2,0) beats the base `.x`, so order does not matter.
       The DATA palette (role tints, map dots) is deliberately left untouched. */
    html.dark { color-scheme: dark; }
    .dark body { background:#0B0B0C; color:#d4d4d4; }
    /* Cards sit at (almost) the same lightness as the page in dark mode, exactly like
       sprezzature's figure cards: the border alone carries the separation, no lighter
       "floating panel" fill. Light mode already works this way (white on --paper). */
    .dark .bg-white { background-color:#0a0a0a !important; }
    .dark .card { border-color:#262626 !important; }
    .dark .text-slate-900 { color:#f5f5f5 !important; }
    .dark .text-slate-800 { color:#e5e5e5 !important; }
    .dark .text-slate-700 { color:#d4d4d4 !important; }
    .dark .text-slate-600, .dark .text-slate-500 { color:#a3a3a3 !important; }
    .dark .text-slate-400 { color:#737373 !important; }
    .dark .text-slate-300 { color:#404040 !important; }
    .dark .bg-slate-100 { background-color:#262626 !important; }
    .dark .bg-slate-200 { background-color:#404040 !important; }
    .dark .hover\:bg-slate-100:hover { background-color:#262626 !important; }
    .dark .hover\:bg-slate-200:hover { background-color:#404040 !important; }
    .dark .hover\:bg-red-100:hover { background-color:#7f1d1d !important; }
    .dark .border-slate-400 { border-color:#525252 !important; }
    .dark input, .dark select { background-color:#0B0B0C; color:#e5e5e5; border-color:#404040; }
    .dark #run { background:#e5e5e5 !important; color:#0B0B0C !important; }
    .dark .analysis { color:#d4d4d4; }
    .dark .analysis h1, .dark .analysis h2, .dark .analysis strong { color:#f5f5f5; }
    .dark .analysis h2 { border-color:#262626; }
    /* Subtle card border, sprezzature style (neutral-200/70 in light); no shadow, the
       border alone separates a card from the page (dark variant set above). */
    .card { border:1px solid rgba(229,229,229,.7); }
    /* Header toggle buttons: transparent pills, sprezzature nav style (their lang/theme
       buttons carry no background until hovered, unlike a permanently-filled chip). */
    .toggle-btn { font-size:1.15rem; line-height:1; width:2.25rem; height:2.25rem;
      display:flex; align-items:center; justify-content:center; border-radius:9999px;
      background:transparent; transition:background-color .15s; }
    .toggle-btn:hover { background:#f5f5f5; }
    .dark .toggle-btn:hover { background:#262626; }
    /* GitHub star link, echoing the sprezzature nav pill: transparent, hover fill. */
    .gh-link { display:inline-flex; align-items:center; gap:.35rem; font-size:.875rem;
      font-weight:500; padding:.4rem .75rem; border-radius:9999px; background:transparent;
      color:#404040; white-space:nowrap; transition:background-color .15s; }
    .gh-link:hover { background:#f5f5f5; }
    .dark .gh-link { color:#d4d4d4; }
    .dark .gh-link:hover { background:#262626; }
    /* Sticky, translucent, blurred nav bar: full-width band with an inner max-width
       container, exactly the sprezzature header treatment. */
    .site-header { position:sticky; top:0; z-index:40; -webkit-backdrop-filter:blur(8px);
      backdrop-filter:blur(8px); background:rgba(250,250,250,.8);
      border-bottom:1px solid rgba(229,229,229,.7); }
    .dark .site-header { background:rgba(11,11,12,.8); border-bottom-color:#262626; }
    .site-footer { border-top:1px solid rgba(229,229,229,.7); }
    .dark .site-footer { border-top-color:#262626; }
    /* Secondary (outlined) buttons: one visual language for every non-primary action,
       thin border, neutral hover. Never the data-blue accent (chrome stays neutral so a
       colour in this app always means "data"; see the palette comment above). */
    .btn { display:inline-flex; align-items:center; gap:.35rem; border-radius:.5rem;
      border:1px solid #d4d4d4; background:#ffffff; color:#404040; font-weight:500;
      padding:.5rem .85rem; font-size:.875rem; white-space:nowrap;
      transition:border-color .15s, background-color .15s; }
    .btn:hover { border-color:#a3a3a3; background:#fafafa; }
    .dark .btn { border-color:#404040; background:transparent; color:#d4d4d4; }
    .dark .btn:hover { border-color:#737373; background:#171717; }
    .btn-sm { padding:.3rem .65rem; font-size:.75rem; }
  </style>
</head>
<body class="text-slate-800">
  <!-- Sticky, translucent nav bar (sprezzature style): full-width band, thin, with the
       brand mark on the left and the language / theme toggles on the right. The page
       title and tagline live in the hero below, not here, so the bar stays slim. -->
  <header class="site-header">
    <nav class="max-w-[1400px] mx-auto px-4 sm:px-6 py-3 flex items-center justify-between gap-4" aria-label="Primary">
      <div class="flex items-center gap-2">
        <!-- The logo is the product metaphor: an old chart where every place has its
             position. It is chrome, not data, so it carries no palette meaning. -->
        <img src="/static/logo-header.png" alt="Standpoint logo: an old map with a compass rose"
             width="28" height="28" class="w-7 h-7 rounded shrink-0" />
        <span class="font-semibold tracking-tight text-slate-900">Standpoint</span>
      </div>
      <!-- Language (🇫🇷/🇬🇧) and theme (🌞/🌛) toggles. Both persist in localStorage;
           the language one re-localizes the whole page, including the LLM output. -->
      <div class="flex items-center gap-1">
        <a id="ghLink" class="gh-link" href="https://github.com/warith-harchaoui/standpoint"
           target="_blank" rel="noopener" data-i18n="github">⭐️ on GitHub</a>
        <button id="langToggle" class="toggle-btn" type="button" data-i18n-aria="lang_aria" aria-label="Switch language">🇬🇧</button>
        <button id="themeToggle" class="toggle-btn" type="button" data-i18n-aria="theme_light_aria" aria-label="Switch theme">🌛</button>
      </div>
    </nav>
  </header>

  <div class="max-w-[1400px] mx-auto px-4 sm:px-6 py-6 sm:py-10 space-y-8 sm:space-y-10">

    <!-- Hero: a small monospace "eyebrow" tag over a serif display headline, sprezzature
         style (their eyebrow carries the page/skill slug; ours carries the product's). -->
    <div>
      <p class="eyebrow text-sm text-slate-500">standpoint</p>
      <h1 class="headline mt-1 text-3xl sm:text-4xl font-bold tracking-tight text-slate-900" data-i18n="baseline">Know where each option actually stands.</h1>
    </div>

    <!-- 1 · Your table -->
    <section class="card bg-white rounded-xl p-5 sm:p-7 space-y-6">
      <div class="flex items-center gap-3">
        <span class="accent"></span>
        <h2 class="text-xl font-semibold" data-i18n="table_title">Table</h2>
      </div>

      <div class="flex items-center gap-2 flex-wrap">
        <!-- Start from an empty grid; then build it up row by row and column by column. -->
        <button id="newTable" class="btn" data-i18n="new_table">🆕 New Table</button>
        <button id="addRow" class="btn" data-i18n="add_row">＋ Option (row)</button>
        <button id="addCol" class="btn" data-i18n="add_col">＋ Criterion (column)</button>
        <span class="mx-1 text-slate-300 hidden sm:inline">|</span>
        <!-- "Laziness / Paresse": fill every empty cell from the model's knowledge once
             the row and column names are typed (common for a headers-only upload). -->
        <button id="flemme" class="btn" data-i18n="flemme" data-i18n-aria="flemme_aria">😴 Laziness (auto-fill)</button>
      </div>
      <!-- File actions (import / export) on their own line, separate from grid-editing. -->
      <div class="flex items-center gap-2 flex-wrap">
        <label class="btn cursor-pointer">
          <span data-i18n="upload">Upload CSV / XLSX</span>
          <input id="upload" type="file" accept=".csv,.xlsx,.xls,.md,.txt" class="hidden" />
        </label>
        <button id="dlCsv" class="btn" data-i18n="download_csv">Download CSV</button>
        <button id="dlXlsx" class="btn" data-i18n="download_xlsx">Download XLSX</button>
      </div>
      <p class="text-xs text-slate-500 leading-relaxed">
        <span data-i18n="hint_higher">Higher is better by default.</span><br>
        <span data-i18n="hint_toggle">Toggle ⬇️ / ⬆️ on a column to set whether lower or higher is the better score.</span>
      </p>

      <div class="overflow-x-auto">
        <table class="border-collapse text-sm" id="grid"></table>
      </div>
    </section>

    <!-- 2 · Options -->
    <section class="card bg-white rounded-xl p-5 sm:p-7 space-y-6">
      <div class="flex items-center gap-3">
        <span class="accent"></span>
        <h2 class="text-xl font-semibold" data-i18n="options_title">Options</h2>
      </div>

      <div class="space-y-4 max-w-xl">
        <label class="flex items-center justify-between gap-4 text-sm">
          <span class="font-medium" data-i18n="reference_label">Chosen top-right reference</span>
          <select id="reference" class="border rounded-lg px-3 py-2 min-w-[13rem]"></select>
        </label>

        <label class="flex items-center gap-3 text-sm">
          <input type="checkbox" id="bgTransparent" class="w-4 h-4" />
          <span class="font-medium" data-i18n="transparent_bg">Transparent background</span>
        </label>
      </div>

      <button id="run" class="px-6 py-3 rounded-xl text-white font-semibold shadow-sm hover:opacity-90"
              style="background:#171717" data-i18n="generate">Generate quadrant</button>
    </section>

    <p id="status" role="status" aria-live="polite" class="text-sm text-slate-500 hidden"></p>
    <p id="error" role="alert" aria-live="assertive" class="text-sm font-medium hidden" style="color:#FF3B30"></p>

    <!-- 3 · Quadrant -->
    <section class="card bg-white rounded-xl p-5 sm:p-7 space-y-5">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-3">
          <span class="accent"></span>
          <h2 class="text-xl font-semibold" data-i18n="quadrant_title">Quadrant</h2>
        </div>
        <div class="flex gap-2">
          <button id="dlPng" class="btn btn-sm hidden">PNG</button>
          <button id="dlSvg" class="btn btn-sm hidden">SVG</button>
        </div>
      </div>

      <!-- Editable axis poles: filled with the model's names after a run, so the user
           can rename any of the four and see the map re-label live (client-side; the
           model is not called again). Laid out like a compass to mirror the map: top
           over left ✚ right over bottom. Hidden until the first quadrant exists. -->
      <div id="poleEditor" class="hidden space-y-3">
        <div class="flex items-baseline gap-2 flex-wrap">
          <span class="text-sm font-semibold text-slate-700" data-i18n="poles_title">Axis poles</span>
          <span class="text-xs text-slate-500" data-i18n="poles_hint">Rename the four poles; the map updates live.</span>
        </div>
        <div class="grid grid-cols-3 gap-2 w-full max-w-md items-center">
          <span></span>
          <input id="poleTop" type="text" data-i18n-aria="aria_pole_top" aria-label="Top pole name"
                 class="border rounded-lg px-2 py-1 text-sm text-center w-full" />
          <span></span>
          <input id="poleLeft" type="text" data-i18n-aria="aria_pole_left" aria-label="Left pole name"
                 class="border rounded-lg px-2 py-1 text-sm text-center w-full" />
          <span class="text-center text-slate-400 text-sm select-none" aria-hidden="true">✚</span>
          <input id="poleRight" type="text" data-i18n-aria="aria_pole_right" aria-label="Right pole name"
                 class="border rounded-lg px-2 py-1 text-sm text-center w-full" />
          <span></span>
          <input id="poleBottom" type="text" data-i18n-aria="aria_pole_bottom" aria-label="Bottom pole name"
                 class="border rounded-lg px-2 py-1 text-sm text-center w-full" />
          <span></span>
        </div>
      </div>

      <div id="chart" class="min-h-[420px] flex items-center justify-center overflow-x-auto text-slate-400" data-i18n="chart_placeholder">
        Generate to see the map.
      </div>
    </section>

    <!-- Analysis -->
    <section class="card bg-white rounded-xl p-5 sm:p-7 space-y-5">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-3">
          <span class="accent"></span>
          <h2 class="text-xl font-semibold" data-i18n="analysis_title">Basic Analysis</h2>
        </div>
        <button id="dlMd" class="btn btn-sm hidden" data-i18n="download_md">Download Markdown</button>
      </div>
      <div id="comments" class="analysis max-w-none text-slate-400" data-i18n="analysis_placeholder">
        The written interpretation appears here once you generate.
      </div>
    </section>
  </div>

  <!-- Minimal footer, sprezzature style: a full-width band with a border-top divider
       and one muted line, echoing the local-first pitch from the hero. -->
  <footer class="site-footer mt-4">
    <div class="max-w-[1400px] mx-auto px-4 sm:px-6 py-6 text-sm text-slate-500" data-i18n="footer_note">
      Local-first: your table never leaves this machine.
    </div>
  </footer>

<script>
// --- tiny state: header cells, lower-is-better flags, and data rows -----------
let headers = [];      // criteria names (excluding the first "option" column)
let firstCol = "Option";
let lowerCols = new Set();  // indices (into headers) marked lower-is-better
let rows = [];         // each: {name: string, values: string[]}

// UI language + theme, the localized string table, and the export filename stem.
let LANG = localStorage.getItem("sp-lang") || "en";
let THEME = localStorage.getItem("sp-theme") || "light";
let T = {};             // gui strings for LANG, fetched from /api/i18n
let hasResult = false;  // once true, keep the rendered chart/analysis on relayout
let slug = "standpoint";  // export stem, set from the table's plural after a run

const $ = (id) => document.getElementById(id);

// Localized string with {placeholder} interpolation; falls back to the key.
function t(key, vars) {
  let s = T[key] != null ? T[key] : key;
  if (vars) for (const k in vars) s = s.split("{" + k + "}").join(vars[k]);
  return s;
}

// Filename stem from a display name: lowercase, words joined by hyphens. Used for
// the pre-generate CSV/XLSX downloads; post-generate exports use the server slug.
function clientSlug(text) {
  const s = (text || "").toLowerCase().normalize("NFKD").replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  return s || "standpoint";
}
function fileStem() { return hasResult ? slug : clientSlug(firstCol); }

// Parse CSV text into our state (first column = option names, rest numeric). Cells
// may legitimately be blank (an upload can carry only row and column names).
function loadCsv(text) {
  const lines = text.trim().split(/\r?\n/).filter((l) => l.length);
  const head = lines[0].split(",");
  firstCol = head[0];
  headers = head.slice(1);
  lowerCols = new Set();
  rows = lines.slice(1).map((l) => {
    const c = l.split(",");
    return { name: c[0], values: headers.map((_, i) => c[i + 1] ?? "") };
  });
  renderGrid();
}

// Rebuild the editable table and the reference dropdown from state. All labels come
// from the string table so the grid re-localizes when the language toggle flips.
function renderGrid() {
  const g = $("grid");
  g.innerHTML = "";
  // header row: first-column name, then each criterion with ↓ toggle + delete
  const htr = document.createElement("tr");
  htr.innerHTML = `<th class="p-1"><input aria-label="${t("aria_options_col")}"
      class="cell-name font-semibold border rounded px-2 py-1"
      value="${firstCol}" oninput="firstCol=this.value"/></th>`;
  headers.forEach((h, i) => {
    const th = document.createElement("th");
    th.className = "p-1 align-bottom";
    const low = lowerCols.has(i);
    th.innerHTML = `
      <div class="flex flex-col items-center gap-1">
        <input aria-label="${t("aria_criterion", {n: i + 1})}" class="cell-head border rounded px-1 py-1 text-center text-xs" value="${h}"
               oninput="headers[${i}]=this.value"/>
        <div class="flex gap-1 text-xs">
          <button aria-label="${low ? t("aria_lower") : t("aria_higher")}"
                  title="${low ? t("title_lower") : t("title_higher")}"
                  class="px-1 rounded ${low ? 'bg-slate-300' : 'bg-slate-100'} hover:bg-slate-200"
                  onclick="toggleLower(${i})">${low ? '⬇️' : '⬆️'}</button>
          <button aria-label="${t("aria_del_col")}" title="${t("title_del_col")}" class="px-1 rounded bg-slate-100 hover:bg-red-100"
                  onclick="delCol(${i})">✕</button>
        </div>
      </div>`;
    htr.appendChild(th);
  });
  g.appendChild(htr);
  // data rows
  rows.forEach((r, ri) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td class="p-1"><input aria-label="${t("aria_option", {n: ri + 1})}"
        class="cell-name border rounded px-2 py-1 font-medium" value="${r.name}"
        oninput="rows[${ri}].name=this.value; syncReference()"/></td>`;
    r.values.forEach((v, ci) => {
      const td = document.createElement("td");
      td.className = "p-1";
      const opt = r.name || t("aria_option", {n: ri + 1});
      const crit = headers[ci] || t("aria_criterion", {n: ci + 1});
      td.innerHTML = `<input aria-label="${t("aria_rating", {opt: opt, crit: crit})}"
          class="w-full border rounded px-1 py-1 text-center" value="${v}"
          oninput="rows[${ri}].values[${ci}]=this.value"/>`;
      tr.appendChild(td);
    });
    const del = document.createElement("td");
    del.innerHTML = `<button aria-label="${t("aria_del_row", {n: ri + 1})}" title="${t("title_del_row")}" class="px-1 text-xs rounded bg-slate-100 hover:bg-red-100"
        onclick="delRow(${ri})">✕</button>`;
    tr.appendChild(del);
    g.appendChild(tr);
  });
  syncReference();
}

function toggleLower(i) { lowerCols.has(i) ? lowerCols.delete(i) : lowerCols.add(i); renderGrid(); }
function delCol(i) { headers.splice(i, 1); rows.forEach((r) => r.values.splice(i, 1));
                     lowerCols = new Set(); renderGrid(); }
function delRow(i) { rows.splice(i, 1); renderGrid(); }

// Keep the reference dropdown in step with the option names.
function syncReference() {
  const sel = $("reference"); const cur = sel.value;
  sel.innerHTML = rows.map((r, i) => `<option value="${i}">${r.name || t("ref_fallback", {i: i})}</option>`).join("");
  if (cur && cur < rows.length) sel.value = cur;
}

$("addRow").onclick = () => { rows.push({ name: t("new_option"), values: headers.map(() => "3") }); renderGrid(); };
$("addCol").onclick = () => { headers.push(t("new_criterion")); rows.forEach((r) => r.values.push("3")); renderGrid(); };
// New Table: a blank slate with one empty option and one empty criterion, so the user
// can build a table from scratch, adding rows and columns as they go.
$("newTable").onclick = () => {
  firstCol = "Option";
  headers = [""];
  rows = [{ name: "", values: [""] }];
  hasResult = false;
  baseSpec = null; basePoles = null;  // drop the old map's poles; editor hides until the next run
  $("poleEditor").classList.add("hidden");
  renderGrid();
};

// Upload a CSV or XLSX file: the server normalizes it to CSV (XLSX via pandas). An
// upload with only headers and no values is fine; "Laziness" can fill the rest.
$("upload").onchange = async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  $("error").classList.add("hidden");
  const fd = new FormData(); fd.append("file", file);
  try {
    const res = await fetch("/api/upload", { method: "POST", body: fd });
    if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
    loadCsv(await res.text());
  } catch (err) {
    $("error").textContent = t("err_upload") + err.message;
    $("error").classList.remove("hidden");
  }
  e.target.value = "";  // allow re-uploading the same file
};

// --- "Laziness / Paresse": fill the empty cells from the model's knowledge --------
$("flemme").onclick = async () => {
  const btn = $("flemme");
  if (btn.disabled) return;
  const options = rows.map((r) => r.name).filter((s) => s && s.trim());
  const criteria = headers.filter((h) => h && h.trim());
  $("error").classList.add("hidden");
  if (!options.length || !criteria.length) {
    $("error").textContent = t("err_flemme") + t("err_generic");
    $("error").classList.remove("hidden");
    return;
  }
  btn.disabled = true;
  btn.classList.add("opacity-60", "cursor-not-allowed");
  $("status").textContent = t("flemme_running");
  $("status").classList.remove("hidden");
  try {
    const res = await fetch("/api/autofill", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ noun: firstCol, options, criteria, lang: LANG }),
    });
    if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
    const data = await res.json();
    const ratings = data.ratings || {};
    // Fill only blank cells, so anything the user already typed is preserved.
    rows.forEach((r) => {
      const rr = ratings[r.name] || {};
      r.values = headers.map((h, i) => {
        const cur = (r.values[i] ?? "").toString().trim();
        if (cur) return r.values[i];
        return rr[h] != null ? String(rr[h]) : "";
      });
    });
    renderGrid();
    $("status").classList.add("hidden");
  } catch (err) {
    $("status").classList.add("hidden");
    $("error").textContent = t("err_flemme") + err.message;
    $("error").classList.remove("hidden");
  } finally {
    btn.disabled = false;
    btn.classList.remove("opacity-60", "cursor-not-allowed");
  }
};

// Serialize the grid back to CSV, tagging lower-is-better columns with "(↓)".
function toCsv() {
  const head = [firstCol, ...headers.map((h, i) => (lowerCols.has(i) ? `${h} (↓)` : h))];
  const body = rows.map((r) => [r.name, ...r.values].join(","));
  return [head.join(","), ...body].join("\n");
}

// Download the current grid: CSV is built client-side; XLSX is built by the server.
$("dlCsv").onclick = () => download(fileStem() + ".csv", toCsv(), "text/csv");
$("dlXlsx").onclick = async () => {
  const res = await fetch("/api/download/xlsx", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ table: toCsv() }),
  });
  if (!res.ok) { $("error").textContent = t("err_xlsx"); $("error").classList.remove("hidden"); return; }
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = fileStem() + ".xlsx"; a.click();
  URL.revokeObjectURL(a.href);
};

// Tint each highlighted option name in the rendered analysis by its role, so the
// text matches the coloured dots on the map. DOM-walk the text nodes (never touch
// tags/attributes) and wrap whole-word name matches, longest name first.
function colorizeRoles(html, roles) {
  const roleClass = { best: "role-best", worst: "role-worst", top: "role-top", right: "role-right" };
  const names = Object.entries(roles)
    .filter(([, r]) => roleClass[r])
    .sort((a, b) => b[0].length - a[0].length);
  if (!names.length) return html;
  const tmp = document.createElement("div");
  tmp.innerHTML = html;
  const walker = document.createTreeWalker(tmp, NodeFilter.SHOW_TEXT);
  const textNodes = [];
  while (walker.nextNode()) textNodes.push(walker.currentNode);
  for (const node of textNodes) {
    let out = node.nodeValue, hit = false;
    for (const [name, role] of names) {
      const esc = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      const re = new RegExp(`(^|[^\\w])(${esc})(?=[^\\w]|$)`, "g");
      if (re.test(out)) { hit = true; out = out.replace(re, `$1<span class="${roleClass[role]}">$2</span>`); }
    }
    if (hit) { const s = document.createElement("span"); s.innerHTML = out; node.replaceWith(s); }
  }
  return tmp.innerHTML;
}

// --- editable axis poles ------------------------------------------------------
// After a run we keep the server's Vega spec (baseSpec) and the model's four pole
// names (basePoles = [left, right, bottom, top]) pristine. Every draw rebuilds the
// spec from them, applying whatever the user typed into the pole inputs, so renaming
// a pole re-labels the map instantly with no extra model call, and the PNG / SVG
// exports (rendered from the same view) pick up the new names for free.
let baseSpec = null, basePoles = null;

// Fill the four pole inputs with the model's names and reveal the compass editor.
function renderPoleEditors() {
  if (!basePoles || basePoles.length !== 4) return;
  const [left, right, bottom, top] = basePoles;
  $("poleLeft").value = left; $("poleRight").value = right;
  $("poleBottom").value = bottom; $("poleTop").value = top;
  $("poleEditor").classList.remove("hidden");
}

// Rebuild the Vega spec from the pristine server spec: swap each pole label for the
// user's text (keyed by the ORIGINAL name, so duplicate labels never confuse it) and
// set the preview background from the toggle. Pure client-side; the model is not re-run.
function buildSpec() {
  const spec = JSON.parse(JSON.stringify(baseSpec));
  if (basePoles && basePoles.length === 4) {
    const wanted = [$("poleLeft").value, $("poleRight").value, $("poleBottom").value, $("poleTop").value];
    const rename = {};
    basePoles.forEach((p, i) => { rename[p] = (wanted[i] || "").trim() || p; });  // blank -> keep original
    // The four pole words are the only single-datum text layers carrying a `t` field.
    (spec.layer || []).forEach((L) => {
      const v = L && L.data && L.data.values;
      if (Array.isArray(v) && v.length === 1 && v[0] && "t" in v[0] && v[0].t in rename) {
        v[0].t = rename[v[0].t];
      }
    });
  }
  spec.background = $("bgTransparent").checked ? null : "white";  // checked = transparent
  return spec;
}

// Draw (or redraw) the quadrant from the current spec + pole inputs + background.
async function drawChart() {
  if (!baseSpec) return;
  const spec = buildSpec();
  $("chart").classList.toggle("checker", $("bgTransparent").checked);
  $("chart").textContent = "";
  // No vega-embed "⋯" menu: the explicit PNG / SVG buttons replace it. SVG renderer
  // so the map stays crisp when CSS scales it to fit the card.
  const embed = await vegaEmbed("#chart", spec, { actions: false, renderer: "svg" });
  chartView = embed.view;  // used by the explicit PNG / SVG export buttons
}

// --- generate: POST the table, render the spec + markdown --------------------
let lastMd = "", chartView = null;
$("run").onclick = async () => {
  const btn = $("run");
  // A run calls a local model and can take a while on a cold start; lock the
  // button (and mark it busy for assistive tech) so a second click can't fire a
  // concurrent request. The `finally` below always restores it.
  if (btn.disabled) return;
  btn.disabled = true;
  btn.setAttribute("aria-busy", "true");
  btn.classList.add("opacity-60", "cursor-not-allowed");
  btn.textContent = t("generating");
  $("error").classList.add("hidden");
  $("status").textContent = t("status_running");
  $("status").classList.remove("hidden");
  try {
    const res = await fetch("/api/position", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        table: toCsv(),
        reference: $("reference").value,
        lower: "",                 // lower-is-better is carried by the (↓) markers
        lang: LANG,                // the toggle drives the language of the whole output
      }),
    });
    if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
    const data = await res.json();
    slug = data.slug || "standpoint";  // name exports after the table's subject
    // Keep the server spec and the model's pole names pristine; the compass editor
    // (renderPoleEditors) fills its inputs and every draw rebuilds from them, so the
    // user can rename a pole and see the map relabel live without another model call.
    baseSpec = data.vega;
    basePoles = (data.poles || []).slice();
    renderPoleEditors();
    await drawChart();  // honours the background toggle and any pole edits
    $("dlPng").classList.remove("hidden"); $("dlSvg").classList.remove("hidden");
    // Render the analysis, then tint each option name by its role so the prose
    // echoes the dots on the map (leader red, weakest brown, top purple, right blue).
    lastMd = data.markdown;
    $("comments").className = "analysis max-w-none";
    $("comments").innerHTML = colorizeRoles(
      marked.parse(data.markdown || t("no_analysis")),
      data.roles || {},
    );
    $("dlMd").classList.remove("hidden");
    hasResult = true;  // keep the chart/analysis on a later language relayout
    $("status").classList.add("hidden");
  } catch (e) {
    $("status").classList.add("hidden");
    $("error").textContent = t("err_generic") + e.message;
    $("error").classList.remove("hidden");
  } finally {
    // Always restore the button, whether the run succeeded or errored.
    btn.disabled = false;
    btn.removeAttribute("aria-busy");
    btn.classList.remove("opacity-60", "cursor-not-allowed");
    btn.textContent = t("generate");
  }
};

// Client-side downloads for the text deliverables.
function download(name, text, type) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type }));
  a.download = name; a.click(); URL.revokeObjectURL(a.href);
}
$("dlMd").onclick = () => download(slug + ".md", lastMd, "text/markdown");

// Export the rendered quadrant straight from the Vega view (honours the background
// toggle): rasterized PNG (2x) or vector SVG.
async function exportImage(fmt) {
  if (!chartView) return;
  try {
    const url = await chartView.toImageURL(fmt, fmt === "png" ? 2 : 1);
    const a = document.createElement("a"); a.href = url; a.download = slug + "." + fmt; a.click();
  } catch (err) {
    $("error").textContent = t("err_image") + err.message;
    $("error").classList.remove("hidden");
  }
}
$("dlPng").onclick = () => exportImage("png");
$("dlSvg").onclick = () => exportImage("svg");

// Renaming any pole (debounced so fast typing doesn't thrash the renderer) or flipping
// the background redraws the map live from the pristine base spec.
function debounce(fn, ms) { let h; return (...a) => { clearTimeout(h); h = setTimeout(() => fn(...a), ms); }; }
const redrawSoon = debounce(() => { if (baseSpec) drawChart(); }, 200);
["poleTop", "poleLeft", "poleRight", "poleBottom"].forEach((id) => $(id).addEventListener("input", redrawSoon));
$("bgTransparent").addEventListener("change", () => { if (baseSpec) drawChart(); });

// --- language + theme toggles -------------------------------------------------
// Apply the fetched string table to every [data-i18n] / [data-i18n-aria] node, then
// re-render the grid so its labels follow. The chart and analysis are skipped once a
// result is on screen, so flipping the language never wipes a rendered map.
function applyI18n() {
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    if ((el.id === "chart" || el.id === "comments") && hasResult) return;
    const k = el.getAttribute("data-i18n");
    if (T[k] != null) el.textContent = T[k];
  });
  document.querySelectorAll("[data-i18n-aria]").forEach((el) => {
    const k = el.getAttribute("data-i18n-aria");
    if (T[k] != null) el.setAttribute("aria-label", T[k]);
  });
  document.documentElement.lang = LANG;
  updateToggles();
  renderGrid();
}

// The toggle glyphs show the CURRENT language flag and the theme you would switch TO.
function updateToggles() {
  $("langToggle").textContent = LANG === "fr" ? "🇫🇷" : "🇬🇧";
  const dark = document.documentElement.classList.contains("dark");
  $("themeToggle").textContent = dark ? "🌞" : "🌛";
  if (T.theme_dark_aria) $("themeToggle").setAttribute("aria-label", dark ? T.theme_dark_aria : T.theme_light_aria);
}

async function loadI18n() {
  try {
    const res = await fetch("/api/i18n?lang=" + encodeURIComponent(LANG));
    T = (await res.json()).strings || {};
  } catch (e) { T = {}; }
  applyI18n();
}

function setTheme(theme) {
  THEME = theme;
  document.documentElement.classList.toggle("dark", theme === "dark");
  localStorage.setItem("sp-theme", theme);
  updateToggles();
}

$("langToggle").onclick = () => {
  LANG = LANG === "fr" ? "en" : "fr";
  localStorage.setItem("sp-lang", LANG);
  loadI18n();
};
$("themeToggle").onclick = () => setTheme(THEME === "dark" ? "light" : "dark");

// --- boot ---------------------------------------------------------------------
setTheme(THEME);  // apply the saved theme before first paint of interactive chrome
// Localize, then load the shipped example so the page is alive and translated on load.
loadI18n().then(() => fetch("/api/example").then((r) => r.text()).then(loadCsv));
</script>
</body>
</html>
"""
