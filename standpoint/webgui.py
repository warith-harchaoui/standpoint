"""The single-page Standpoint GUI as one self-contained HTML string.

No build step, no framework, no npm: vanilla JavaScript + Tailwind (Play CDN) +
vega-embed (to render the Vega-Lite spec live in the browser) + marked (to render the
Markdown analysis). `standpoint.api` serves this at ``GET /gui``.

Kept as a Python string (rather than a static file) so it ships inside the package
and the ``dev-gui`` investigation stays a two-file backend + one-string frontend.
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
  <title>Standpoint — table to quadrant</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/vega@5"></script>
  <script src="https://cdn.jsdelivr.net/npm/vega-lite@5"></script>
  <script src="https://cdn.jsdelivr.net/npm/vega-embed@6"></script>
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <style>
    /* "Good Colors" palette — https://harchaoui.org/warith/colors/ — used across the
       whole UI, not only the figure, so the chrome echoes the map's role colours. */
    :root {
      --red:#FF3B30; --blue:#007AFF; --green:#28CD41; --purple:#AF52DE; --brown:#A52A2A;
      --red-l:#FFD8D6; --blue-l:#CCE4FF; --green-l:#D4F5D9; --purple-l:#EFDCF8;
      --ink:#1c1c1e; --paper:#F8F8F8;
    }
    body { font-family: Roboto, -apple-system, Helvetica, Arial, sans-serif; background: var(--paper); }
    .cell { width: 4.5rem; }
    /* A small coloured accent bar that heads each step. */
    .accent { width: .6rem; height: 1.6rem; border-radius: .3rem; display: inline-block; }
    /* Visible keyboard focus everywhere (accessibility). */
    input:focus-visible, select:focus-visible, button:focus-visible, label:focus-within {
      outline: 2px solid var(--blue); outline-offset: 2px;
    }
    #chart.checker { background-image:
      linear-gradient(45deg,#eee 25%,transparent 25%),
      linear-gradient(-45deg,#eee 25%,transparent 25%),
      linear-gradient(45deg,transparent 75%,#eee 75%),
      linear-gradient(-45deg,transparent 75%,#eee 75%);
      background-size: 20px 20px;
      background-position: 0 0, 0 10px, 10px -10px, -10px 0; }
    /* The analysis panel, coloured to echo the map (Tailwind's CDN has no prose
       plugin, so the rendered Markdown is themed here by hand). */
    .analysis { color:#1c1c1e; line-height:1.65; }
    .analysis h1 { font-size:1.5rem; font-weight:800; color:var(--red); margin:.1rem 0 .6rem; }
    .analysis h2 { font-size:1.05rem; font-weight:700; color:var(--blue);
      border-bottom:2px solid var(--blue-l); padding-bottom:.25rem; margin:1.4rem 0 .5rem; }
    .analysis p { margin:.6rem 0; }
    .analysis strong { color:var(--purple); }
    .analysis ul { margin:.5rem 0; padding-left:1.25rem; list-style:disc; }
    .analysis li { margin:.3rem 0; }
    /* Option names tinted by their role, matching the dots on the map. */
    .role-best  { color:var(--red);    font-weight:700; }
    .role-worst { color:var(--brown);  font-weight:700; }
    .role-top   { color:var(--purple); font-weight:700; }
    .role-right { color:var(--blue);   font-weight:700; }
  </style>
</head>
<body class="text-slate-800">
  <div class="max-w-6xl mx-auto px-6 py-10 space-y-10">

    <header class="rounded-2xl px-8 py-9 shadow-sm"
            style="background:linear-gradient(120deg,#CCE4FF 0%,#EFDCF8 55%,#FFD8D6 100%)">
      <div class="flex items-center gap-4">
        <span class="flex gap-2" aria-hidden="true">
          <span class="w-4 h-4 rounded-full ring-2 ring-white" style="background:#FF3B30"></span>
          <span class="w-4 h-4 rounded-full ring-2 ring-white" style="background:#AF52DE"></span>
          <span class="w-4 h-4 rounded-full ring-2 ring-white" style="background:#007AFF"></span>
          <span class="w-4 h-4 rounded-full ring-2 ring-white" style="background:#A52A2A"></span>
        </span>
        <h1 class="text-4xl font-extrabold tracking-tight text-slate-900">Standpoint</h1>
      </div>
    </header>

    <!-- 1 · Your table -->
    <section class="bg-white rounded-2xl shadow-sm p-7 space-y-6">
      <div class="flex items-center gap-3">
        <span class="accent" style="background:#007AFF"></span>
        <h2 class="text-xl font-semibold">1 &middot; Your table</h2>
      </div>

      <div class="flex items-center gap-2 flex-wrap">
        <button id="addRow" class="px-3 py-2 rounded-lg text-sm font-medium" style="background:#D4F5D9;color:#14532d">+ Option (row)</button>
        <button id="addCol" class="px-3 py-2 rounded-lg text-sm font-medium" style="background:#D4F5D9;color:#14532d">+ Criterion (column)</button>
        <button id="loadExample" class="px-3 py-2 rounded-lg bg-slate-100 hover:bg-slate-200 text-sm">Reset to example</button>
        <span class="mx-1 text-slate-300">|</span>
        <label class="px-3 py-2 rounded-lg text-sm font-medium cursor-pointer" style="background:#CCE4FF;color:#0b3d91">
          Upload CSV / XLSX
          <input id="upload" type="file" accept=".csv,.xlsx,.xls,.md,.txt" class="hidden" />
        </label>
        <button id="dlCsv" class="px-3 py-2 rounded-lg bg-slate-100 hover:bg-slate-200 text-sm">Download CSV</button>
        <button id="dlXlsx" class="px-3 py-2 rounded-lg bg-slate-100 hover:bg-slate-200 text-sm">Download XLSX</button>
      </div>
      <p class="text-xs text-slate-500 leading-relaxed">
        Higher is better by default.<br>
        Toggle ⬇️ / ⬆️ on a column to choose whether it is lower or higher that is better.
      </p>

      <div class="overflow-x-auto">
        <table class="border-collapse text-sm" id="grid"></table>
      </div>
    </section>

    <!-- 2 · Options -->
    <section class="bg-white rounded-2xl shadow-sm p-7 space-y-6">
      <div class="flex items-center gap-3">
        <span class="accent" style="background:#AF52DE"></span>
        <h2 class="text-xl font-semibold">2 &middot; Options</h2>
      </div>

      <div class="space-y-4 max-w-xl">
        <label class="flex items-center justify-between gap-4 text-sm">
          <span class="font-medium">Reference <span class="text-slate-400">(placed top-right)</span></span>
          <select id="reference" class="border rounded-lg px-3 py-2 min-w-[13rem]"></select>
        </label>

        <label class="flex items-center justify-between gap-4 text-sm">
          <span class="font-medium">Figure background</span>
          <select id="bg" class="border rounded-lg px-3 py-2 min-w-[13rem]">
            <option value="transparent">transparent</option>
            <option value="white" selected>white</option>
          </select>
        </label>

        <label class="flex items-start gap-3 text-sm">
          <input type="checkbox" id="useLlm" class="w-4 h-4 mt-0.5" />
          <span>Name the axes and write the analysis with the local model
            <span class="text-slate-400">(slower; needs Ollama)</span></span>
        </label>
      </div>

      <button id="run" class="px-6 py-3 rounded-xl text-white font-semibold shadow-sm"
              style="background:#007AFF">Generate quadrant &rarr;</button>
    </section>

    <p id="status" role="status" aria-live="polite" class="text-sm text-slate-500 hidden"></p>
    <p id="error" role="alert" aria-live="assertive" class="text-sm font-medium hidden" style="color:#FF3B30"></p>

    <!-- 3 · Quadrant -->
    <section class="bg-white rounded-2xl shadow-sm p-7 space-y-5">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-3">
          <span class="accent" style="background:#FF3B30"></span>
          <h2 class="text-xl font-semibold">3 &middot; Quadrant</h2>
        </div>
        <div class="flex gap-2">
          <button id="dlPng" class="text-xs px-3 py-1.5 rounded-lg font-medium hidden" style="background:#CCE4FF;color:#0b3d91">PNG</button>
          <button id="dlSvg" class="text-xs px-3 py-1.5 rounded-lg font-medium hidden" style="background:#CCE4FF;color:#0b3d91">SVG</button>
        </div>
      </div>
      <div id="chart" class="min-h-[420px] flex items-center justify-center overflow-x-auto text-slate-400">
        Generate to see the map.
      </div>
    </section>

    <!-- Analysis -->
    <section class="bg-white rounded-2xl shadow-sm p-7 space-y-5">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-3">
          <span class="accent" style="background:#28CD41"></span>
          <h2 class="text-xl font-semibold">Analysis</h2>
        </div>
        <button id="dlMd" class="text-xs px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 hidden">Download Markdown</button>
      </div>
      <div id="comments" class="analysis max-w-none text-slate-400">
        The written interpretation appears here once you generate.
      </div>
    </section>
  </div>

<script>
// --- tiny state: header cells, lower-is-better flags, and data rows -----------
let headers = [];      // criteria names (excluding the first "option" column)
let firstCol = "Option";
let lowerCols = new Set();  // indices (into headers) marked lower-is-better
let rows = [];         // each: {name: string, values: string[]}

const $ = (id) => document.getElementById(id);

// Parse CSV text into our state (first column = option names, rest numeric).
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

// Rebuild the editable table and the reference dropdown from state.
function renderGrid() {
  const g = $("grid");
  g.innerHTML = "";
  // header row: first-column name, then each criterion with ↓ toggle + delete
  const htr = document.createElement("tr");
  htr.innerHTML = `<th class="p-1"><input aria-label="Name of the options column"
      class="cell font-semibold border rounded px-1 py-0.5"
      value="${firstCol}" oninput="firstCol=this.value"/></th>`;
  headers.forEach((h, i) => {
    const th = document.createElement("th");
    th.className = "p-1 align-bottom";
    th.innerHTML = `
      <div class="flex flex-col items-center gap-1">
        <input aria-label="Criterion ${i + 1} name" class="cell border rounded px-1 py-0.5 text-center" value="${h}"
               oninput="headers[${i}]=this.value"/>
        <div class="flex gap-1 text-xs">
          <button aria-label="${lowerCols.has(i) ? 'Lower is better — click to make higher better' : 'Higher is better — click to make lower better'}"
                  title="${lowerCols.has(i) ? 'lower is better (click to flip)' : 'higher is better (click to flip)'}"
                  class="px-1 rounded ${lowerCols.has(i) ? 'bg-amber-100' : 'bg-slate-100'} hover:bg-slate-200"
                  onclick="toggleLower(${i})">${lowerCols.has(i) ? '⬇️' : '⬆️'}</button>
          <button aria-label="Delete column" title="delete column" class="px-1 rounded bg-slate-100 hover:bg-red-100"
                  onclick="delCol(${i})">✕</button>
        </div>
      </div>`;
    htr.appendChild(th);
  });
  g.appendChild(htr);
  // data rows
  rows.forEach((r, ri) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td class="p-1"><input aria-label="Option ${ri + 1} name"
        class="cell border rounded px-1 py-0.5" value="${r.name}"
        oninput="rows[${ri}].name=this.value; syncReference()"/></td>`;
    r.values.forEach((v, ci) => {
      const td = document.createElement("td");
      td.className = "p-1";
      td.innerHTML = `<input aria-label="Rating of ${r.name || ("option " + (ri + 1))} on ${headers[ci] || ("criterion " + (ci + 1))}"
          class="cell border rounded px-1 py-0.5 text-center" value="${v}"
          oninput="rows[${ri}].values[${ci}]=this.value"/>`;
      tr.appendChild(td);
    });
    const del = document.createElement("td");
    del.innerHTML = `<button aria-label="Delete option ${ri + 1}" title="delete row" class="px-1 text-xs rounded bg-slate-100 hover:bg-red-100"
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
  sel.innerHTML = rows.map((r, i) => `<option value="${i}">${r.name || ("row " + i)}</option>`).join("");
  if (cur && cur < rows.length) sel.value = cur;
}

$("addRow").onclick = () => { rows.push({ name: "New", values: headers.map(() => "3") }); renderGrid(); };
$("addCol").onclick = () => { headers.push("Criterion"); rows.forEach((r) => r.values.push("3")); renderGrid(); };
$("loadExample").onclick = () => fetch("/api/example").then((r) => r.text()).then(loadCsv);

// Upload a CSV or XLSX file: the server normalizes it to CSV (XLSX via pandas).
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
    $("error").textContent = "Upload failed: " + err.message;
    $("error").classList.remove("hidden");
  }
  e.target.value = "";  // allow re-uploading the same file
};

// Serialize the grid back to CSV, tagging lower-is-better columns with "(↓)".
function toCsv() {
  const head = [firstCol, ...headers.map((h, i) => (lowerCols.has(i) ? `${h} (↓)` : h))];
  const body = rows.map((r) => [r.name, ...r.values].join(","));
  return [head.join(","), ...body].join("\n");
}

// Download the current grid: CSV is built client-side; XLSX is built by the server.
$("dlCsv").onclick = () => download("standpoint.csv", toCsv(), "text/csv");
$("dlXlsx").onclick = async () => {
  const res = await fetch("/api/download/xlsx", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ table: toCsv() }),
  });
  if (!res.ok) { $("error").textContent = "XLSX export failed."; $("error").classList.remove("hidden"); return; }
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = "standpoint.xlsx"; a.click();
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

// --- generate: POST the table, render the spec + markdown --------------------
let lastMd = "", chartView = null;
$("run").onclick = async () => {
  $("error").classList.add("hidden");
  $("status").textContent = $("useLlm").checked
    ? "Running PCA and asking the local model… (this can take ~10–25 s)"
    : "Running PCA…";
  $("status").classList.remove("hidden");
  try {
    const res = await fetch("/api/position", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        table: toCsv(),
        reference: $("reference").value,
        lower: "",                 // lower-is-better is carried by the (↓) markers
        use_llm: $("useLlm").checked,
      }),
    });
    if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
    const data = await res.json();
    // Render the quadrant. Background toggle applies to the preview only.
    const spec = data.vega;
    spec.background = $("bg").value === "white" ? "white" : null;
    $("chart").classList.toggle("checker", $("bg").value === "transparent");
    $("chart").textContent = "";
    // No vega-embed "⋯" menu — the explicit PNG / SVG buttons replace it.
    const embed = await vegaEmbed("#chart", spec, { actions: false });
    chartView = embed.view;  // used by the explicit PNG / SVG export buttons
    $("dlPng").classList.remove("hidden"); $("dlSvg").classList.remove("hidden");
    // Render the analysis, then tint each option name by its role so the prose
    // echoes the dots on the map (leader red, weakest brown, top purple, right blue).
    lastMd = data.markdown;
    $("comments").className = "analysis max-w-none";
    $("comments").innerHTML = colorizeRoles(
      marked.parse(data.markdown || "*(no analysis — enable the model)*"),
      data.roles || {},
    );
    $("dlMd").classList.remove("hidden");
    $("status").classList.add("hidden");
  } catch (e) {
    $("status").classList.add("hidden");
    $("error").textContent = "Error: " + e.message;
    $("error").classList.remove("hidden");
  }
};

// Client-side downloads for the text deliverables.
function download(name, text, type) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type }));
  a.download = name; a.click(); URL.revokeObjectURL(a.href);
}
$("dlMd").onclick = () => download("standpoint.md", lastMd, "text/markdown");

// Export the rendered quadrant straight from the Vega view (honours the background
// toggle): rasterized PNG (2x) or vector SVG.
async function exportImage(fmt, filename) {
  if (!chartView) return;
  try {
    const url = await chartView.toImageURL(fmt, fmt === "png" ? 2 : 1);
    const a = document.createElement("a"); a.href = url; a.download = filename; a.click();
  } catch (err) {
    $("error").textContent = "Image export failed: " + err.message;
    $("error").classList.remove("hidden");
  }
}
$("dlPng").onclick = () => exportImage("png", "standpoint.png");
$("dlSvg").onclick = () => exportImage("svg", "standpoint.svg");

// Start with the shipped example so the page is alive on load.
fetch("/api/example").then((r) => r.text()).then(loadCsv);
</script>
</body>
</html>
"""
