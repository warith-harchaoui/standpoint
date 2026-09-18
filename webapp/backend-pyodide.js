/* Pyodide-backed `window.backend` for the static Standpoint build.
 *
 * The GUI page (built from `standpoint.webgui.GUI_HTML`) routes its six data
 * operations through a `backend` object and only falls back to the FastAPI
 * transport when `window.backend` is undefined. This file is injected BEFORE
 * the page's main script by `build.py`, so the exact same page runs against an
 * in-browser Python engine instead of a server:
 *
 *   - example / i18n  -> plain static files exported at build time (no Python);
 *   - upload / xlsx / position / autofill -> the real standpoint package running
 *     in Pyodide (WebAssembly CPython + numpy/pandas/scikit-learn).
 *
 * Model calls use the memoized-replay contract of `beh_shim.py`: a run either
 * returns a result or reports the one LLM call it is blocked on; we answer it,
 * seed the cache, and run again (see glue.py). The answers follow the approach
 * of harchaoui.org/warith/livre-elephant/rag.html — no big generative model in
 * the page:
 *
 *   - AXIS NAMING (default, automatic): a small multilingual embedding model
 *     (transformers.js MiniLM, a few dozen MB, loaded on first Generate and
 *     browser-cached) scores each pole's criteria against a curated vocabulary
 *     of positive qualities (vocab/<lang>.json) and picks the nearest word;
 *     the engine's own `finalize_poles` still validates/dedupes, with the
 *     loading-derived words as the offline fallback.
 *   - "LAZINESS" AUTO-FILL (delegated): the engine's own localized ratings
 *     prompt is offered in a copy-the-prompt / paste-the-JSON panel, so the
 *     user's favorite AI (ChatGPT, Claude, a local model…) does the rating and
 *     the pasted answer is seeded back through the same replay mechanism.
 */
(() => {
  "use strict";

  const PYODIDE_URL = "https://cdn.jsdelivr.net/pyodide/v0.29.0/full/pyodide.js";
  // Pyodide-distribution packages the engine imports; vendored wheels come after.
  const PYODIDE_PACKAGES = ["numpy", "pandas", "scikit-learn", "pyyaml", "micropip"];
  // Same embedding stack as harchaoui.org's in-page semantic search: pinned
  // transformers.js + the multilingual MiniLM (covers the GUI's en/fr/es).
  const TRANSFORMERS_URL = "https://cdn.jsdelivr.net/npm/@xenova/transformers@2.17.2";
  const EMBED_MODEL = "Xenova/paraphrase-multilingual-MiniLM-L12-v2";
  const LANGS = ["en", "fr", "es"];

  let py = null; // the Pyodide instance, once booted
  let bootPromise = null; // single-flight boot guard
  let embedderPromise = null; // single-flight embedding-pipeline load
  let strings = {}; // last i18n table fetched, for the panel + badge messages
  let lastPoleCtx = null; // per-pole criteria of the position run in flight
  const vocabCache = {}; // lang -> {words, vecs} (session memo over localStorage)

  // Resolve a bundle-relative path against the page URL, so the app works at any
  // mount point (e.g. https://deraison.ai/standpoint/) without a <base> tag.
  const rel = (p) => new URL(p, document.baseURI).href;
  const t = (key, fallback) => strings[key] || fallback;

  // --- tiny boot badge ----------------------------------------------------------
  // The page's own #status element belongs to the main script; the engine keeps its
  // progress in a separate, unobtrusive fixed badge (bottom-right).
  function badge(text, done) {
    let el = document.getElementById("engineBadge");
    if (!el) {
      el = document.createElement("div");
      el.id = "engineBadge";
      el.setAttribute("role", "status");
      el.style.cssText =
        "position:fixed;right:.75rem;bottom:.75rem;z-index:50;font:12px Roboto Mono,monospace;" +
        "padding:.35rem .6rem;border-radius:.5rem;background:#171717;color:#fafafa;opacity:.85";
      document.body.appendChild(el);
    }
    el.textContent = text;
    if (done) setTimeout(() => el.remove(), 2500); // fade out once settled
  }

  // --- boot: Pyodide + numeric stack + vendored wheels + shim/glue ----------------
  async function boot() {
    if (bootPromise) return bootPromise;
    bootPromise = (async () => {
      badge("Python engine: loading runtime…");
      await new Promise((res, rej) => {
        const s = document.createElement("script");
        s.src = PYODIDE_URL;
        s.onload = res;
        s.onerror = () => rej(new Error("pyodide.js failed to load"));
        document.head.appendChild(s);
      });
      py = await loadPyodide();
      badge("Python engine: numeric stack…");
      await py.loadPackage(PYODIDE_PACKAGES);
      badge("Python engine: standpoint…");
      // The build manifest lists the vendored wheels in install order (deps first).
      const manifest = await (await fetch(rel("py/manifest.json"))).json();
      py.globals.set("SHIM_SRC", await (await fetch(rel("py/beh_shim.py"))).text());
      py.globals.set("GLUE_SRC", await (await fetch(rel("py/glue.py"))).text());
      py.globals.set("WHEEL_URLS", py.toPy(manifest.wheels.map((w) => rel("wheels/" + w))));
      await py.runPythonAsync(`
import pathlib, sysconfig
import micropip

# The LLM shim must shadow the real helper BEFORE standpoint is importable.
_site = pathlib.Path(sysconfig.get_paths()["purelib"])
(_site / "best_engine_ai_helper.py").write_text(SHIM_SRC)

# Vendored pure-Python wheels (langdetect, openpyxl chain, standpoint itself).
# deps=False: the numeric stack is already loaded and the LLM helper is shimmed.
for _url in WHEEL_URLS:
    await micropip.install(_url, deps=False)

(_site / "standpoint_glue.py").write_text(GLUE_SRC)
import standpoint_glue  # imports standpoint -> fails loudly here if anything is missing
`);
      badge("Python engine ready", true);
    })().catch((err) => {
      bootPromise = null; // allow a retry on the next call
      badge("Python engine failed: " + err.message);
      throw err;
    });
    return bootPromise;
  }

  // --- axis naming: small embedding model + curated vocabulary ---------------------
  // `window.__embedder` is a test seam: headless CI answers with a canned pipeline
  // instead of downloading the real model.
  function ensureEmbedder() {
    if (embedderPromise) return embedderPromise;
    embedderPromise = (window.__embedder
      ? Promise.resolve(window.__embedder)
      : import(TRANSFORMERS_URL).then((mod) => {
          mod.env.allowLocalModels = false;
          return mod.pipeline("feature-extraction", EMBED_MODEL);
        })
    ).catch((err) => {
      embedderPromise = null; // transient network failures may recover later
      throw err;
    });
    return embedderPromise;
  }

  // Normalized embedding of one text (unit vector, so cosine = dot product).
  async function embedOne(pipe, text) {
    const out = await pipe(text, { pooling: "mean", normalize: true });
    return Array.from(out.data);
  }

  const dot = (a, b) => {
    let s = 0;
    for (let i = 0; i < a.length; i++) s += a[i] * b[i];
    return s;
  };

  // djb2 over the embedded texts, to key the localStorage embedding cache:
  // editing the vocabulary (or bumping the model) invalidates the cached vectors.
  function vocabKey(lang, texts) {
    let h = 5381;
    for (const c of texts.join(" ") + EMBED_MODEL) h = ((h << 5) + h + c.charCodeAt(0)) | 0;
    return "sp-vocab-" + lang + "-" + (h >>> 0).toString(36);
  }

  // The vocabulary of candidate pole names for `lang`, with embeddings: computed
  // once (a few seconds), then kept in localStorage so later visits skip it.
  // Entries are either a plain word or {w, g}: `w` is the label shown on the map,
  // `g` a disambiguating gloss that is what actually gets embedded (a curated
  // index: e.g. "Ecological" is glossed toward emissions, so a software
  // "Ecosystem" pole can't fall into it on lexical similarity alone).
  async function vocabFor(lang) {
    if (vocabCache[lang]) return vocabCache[lang];
    const raw = await (await fetch(rel("vocab/" + lang + ".json"))).json();
    const words = raw.map((e) => (typeof e === "string" ? e : e.w));
    const texts = raw.map((e) => (typeof e === "string" ? e : e.g || e.w));
    const key = vocabKey(lang, texts);
    let vecs = null;
    try {
      vecs = JSON.parse(localStorage.getItem(key) || "null");
    } catch (e) {
      /* corrupted cache -> recompute */
    }
    if (!vecs || vecs.length !== texts.length) {
      const pipe = await ensureEmbedder();
      vecs = [];
      for (const g of texts) vecs.push((await embedOne(pipe, g)).map((v) => +v.toFixed(5)));
      try {
        localStorage.setItem(key, JSON.stringify(vecs));
      } catch (e) {
        /* quota exceeded -> fine, the session memo below still applies */
      }
    }
    vocabCache[lang] = { words, vecs };
    return vocabCache[lang];
  }

  // Name the four poles from the run's per-pole criteria (see glue.pole_context):
  // each pole becomes ONE text (its criteria, strongest first, joined) embedded as
  // a phrase — context disambiguates better than averaging single-word vectors
  // ("Ecosystem, Job Market, Tooling" reads as software maturity, where the bare
  // word "Ecosystem" drifts toward "Ecological"). The nearest vocabulary word
  // wins; a greedy strongest-claim-first pass keeps the four names distinct.
  // Empty answers ("" on a pole with no criteria) fall through to the engine's
  // loading-derived fallback via `finalize_poles`.
  async function nameAxes(ctx) {
    const lang = LANGS.includes(ctx.lang) ? ctx.lang : "en";
    const { words, vecs } = await vocabFor(lang);
    const pipe = await ensureEmbedder();

    // One phrase per pole: its top criteria (already strongest-first) joined.
    const poleIds = ["left", "right", "bottom", "top"];
    const poleVecs = {};
    for (const id of poleIds) {
      const crits = (ctx.poles[id] || []).slice(0, 4); // keep the phrase focused
      if (!crits.length) continue; // nothing loads there -> let the engine fall back
      poleVecs[id] = await embedOne(pipe, crits.map((c) => c.text).join(", "));
    }

    // Greedy assignment, strongest claim first, each word used at most once.
    const answer = { left: "", right: "", bottom: "", top: "" };
    const taken = new Set();
    const pending = Object.keys(poleVecs);
    while (pending.length) {
      let best = null;
      for (const id of pending) {
        for (let j = 0; j < words.length; j++) {
          if (taken.has(j)) continue;
          const s = dot(poleVecs[id], vecs[j]);
          if (!best || s > best.s) best = { id, j, s };
        }
      }
      if (!best) break;
      answer[best.id] = words[best.j];
      taken.add(best.j);
      pending.splice(pending.indexOf(best.id), 1);
    }
    return answer;
  }

  // --- "Laziness" delegation panel --------------------------------------------------
  // The pending auto-fill call carries the engine's own localized ratings prompt;
  // this panel hands it to the user's AI and takes the JSON answer back. Injected
  // nodes carry data-i18n so the page's localizer follows the language toggle.
  let panelOpen = false;
  function delegatePanel(pending) {
    if (panelOpen) return Promise.reject(new Error(t("delegate_cancelled", "cancelled")));
    panelOpen = true;
    return new Promise((resolve, reject) => {
      const overlay = document.createElement("div");
      overlay.id = "delegateOverlay";
      overlay.className =
        "fixed inset-0 z-40 flex items-center justify-center bg-black/40 p-4";
      overlay.innerHTML = `
        <div class="bg-white dark:bg-neutral-900 rounded-2xl shadow-xl max-w-2xl w-full p-5 flex flex-col gap-3">
          <h3 class="font-semibold text-lg" data-i18n="delegate_title"></h3>
          <p class="text-sm text-neutral-600 dark:text-neutral-300" data-i18n="delegate_intro"></p>
          <textarea id="dlgPrompt" readonly rows="6"
            class="w-full border rounded-lg p-2 text-xs font-mono bg-neutral-50 dark:bg-neutral-800"></textarea>
          <button id="dlgCopy" class="self-start px-3 py-1.5 rounded-lg border text-sm hover:bg-neutral-100 dark:hover:bg-neutral-800" data-i18n="delegate_copy"></button>
          <textarea id="dlgPaste" rows="6"
            class="w-full border rounded-lg p-2 text-xs font-mono"></textarea>
          <p id="dlgError" class="text-sm text-red-600 hidden"></p>
          <div class="flex gap-2 justify-end">
            <button id="dlgCancel" class="px-3 py-1.5 rounded-lg border text-sm" data-i18n="delegate_cancel"></button>
            <button id="dlgApply" class="px-3 py-1.5 rounded-lg bg-neutral-900 text-white text-sm dark:bg-neutral-100 dark:text-neutral-900" data-i18n="delegate_apply"></button>
          </div>
        </div>`;
      document.body.appendChild(overlay);
      const $id = (id) => overlay.querySelector("#" + id);
      // Localize the injected nodes now; the page's applyI18n takes over on toggle.
      overlay.querySelectorAll("[data-i18n]").forEach((el) => {
        const k = el.getAttribute("data-i18n");
        el.textContent = t(k, k);
      });
      $id("dlgPrompt").value = pending.prompt;
      $id("dlgPaste").placeholder = t("delegate_paste", "Paste the AI's JSON answer here");
      $id("dlgCopy").onclick = () => {
        navigator.clipboard.writeText(pending.prompt);
        $id("dlgCopy").textContent = t("delegate_copied", "Prompt copied!");
      };
      const close = () => {
        panelOpen = false;
        overlay.remove();
      };
      $id("dlgCancel").onclick = () => {
        close();
        reject(new Error(t("delegate_cancelled", "cancelled")));
      };
      $id("dlgApply").onclick = () => {
        // Tolerate the common wrappers models add around JSON (``` fences, prose).
        const raw = $id("dlgPaste").value.trim();
        const body = raw.replace(/^```[a-z]*\s*/i, "").replace(/```\s*$/, "");
        try {
          const start = body.indexOf("{");
          const end = body.lastIndexOf("}");
          const obj = JSON.parse(start >= 0 ? body.slice(start, end + 1) : body);
          close();
          resolve(obj);
        } catch (err) {
          const e = $id("dlgError");
          e.textContent = t("delegate_bad_json", "That doesn't parse as JSON: ") + err.message;
          e.classList.remove("hidden");
        }
      };
    });
  }

  // --- model answers -----------------------------------------------------------------
  // Schema-shaped neutral defaults: empty strings push finalize_poles / noun_forms
  // onto their built-in fallbacks (loading-derived pole words, naive plural); the
  // neutral 3 matches the engine's own backfill for unrated cells.
  function neutralAnswer(schema) {
    if (!schema || schema.type !== "object") return {};
    const out = {};
    for (const [k, sub] of Object.entries(schema.properties || {})) {
      out[k] = sub.type === "object" ? neutralAnswer(sub) : sub.type === "integer" ? 3 : "";
    }
    return out;
  }

  // One pending model call -> one answer object matching its JSON schema. The
  // schema's shape says which engine call this is: the four pole keys -> embedding
  // naming (default-on); a matrix of objects -> the delegation panel; anything
  // else (noun forms) -> neutral, i.e. the engine's built-in fallback.
  async function answerLLM(pending) {
    const props = (pending.schema || {}).properties || {};
    const keys = Object.keys(props);
    if (["left", "right", "bottom", "top"].every((k) => keys.includes(k)) && lastPoleCtx) {
      try {
        badge(t("naming_loading", "Naming the axes… (first-time model load, a few seconds)"));
        const names = await nameAxes(lastPoleCtx);
        badge("", true);
        return names;
      } catch (err) {
        badge(t("naming_offline", "Naming model unavailable; axes named from the criteria."), true);
        return neutralAnswer(pending.schema);
      }
    }
    if (keys.length && Object.values(props).every((p) => p.type === "object")) {
      return delegatePanel(pending); // rejects on cancel -> surfaces as err_flemme
    }
    return neutralAnswer(pending.schema); // noun forms and anything unforeseen
  }

  // --- the replay driver ----------------------------------------------------------
  // Run one glue call; on {"pending"}, answer + seed + rerun. A Generate makes at
  // most a handful of model calls, so the bound is generous, not load-bearing.
  async function call(fn, args) {
    await boot();
    for (let round = 0; round < 8; round++) {
      py.globals.set("_fn", fn);
      py.globals.set("_arg", JSON.stringify(args || {}));
      const out = JSON.parse(py.runPython("standpoint_glue.glue_call(_fn, _arg)"));
      if (out.pending) {
        const answer = await answerLLM(out.pending);
        py.globals.set("_k", out.pending.key);
        py.globals.set("_a", JSON.stringify(answer));
        py.runPython("standpoint_glue.glue_seed(_k, _a)");
        continue;
      }
      if (out.error) throw new Error(out.error);
      return out.ok;
    }
    throw new Error("engine did not converge (too many pending model calls)");
  }

  // Binary-safe file -> base64 (the transport glue.py decodes).
  function fileToB64(file) {
    return new Promise((res, rej) => {
      const r = new FileReader();
      r.onload = () => res(String(r.result).split(",", 2)[1] || "");
      r.onerror = () => rej(new Error("could not read the file"));
      r.readAsDataURL(file);
    });
  }

  const b64ToBlob = (b64, type) =>
    new Blob([Uint8Array.from(atob(b64), (c) => c.charCodeAt(0))], { type });

  // --- the backend contract (same six operations as the FastAPI default) ----------
  window.backend = {
    // Starter table + string tables are exported at build time: instant, no Python.
    example: async () => (await fetch(rel("example.csv"))).text(),
    i18n: async (lang) => {
      const res = await fetch(rel("i18n/" + encodeURIComponent(lang) + ".json"));
      const table = res.ok
        ? await res.json()
        : await (await fetch(rel("i18n/en.json"))).json(); // unknown lang -> English
      strings = table; // keep for the delegation panel + badge messages
      return table;
    },
    upload: async (file) => call("upload", { b64: await fileToB64(file), name: file.name || "" }),
    downloadXlsx: async (csv) =>
      b64ToBlob(
        await call("xlsx", { table: csv }),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
      ),
    autofill: async (req) => call("autofill", req),
    // A position run first fetches its per-pole criteria (deterministic, never
    // pending), so the embedding namer can answer the pole call it will trigger.
    position: async (req) => {
      try {
        lastPoleCtx = await call("pole_context", req);
      } catch (e) {
        lastPoleCtx = null; // context is best-effort; fallback naming still works
      }
      return call("position", req);
    },
  };

  window.addEventListener("DOMContentLoaded", () => {
    // Boot in the background so the engine is usually ready before the first
    // Generate; failures surface in the badge and again on the first real call.
    boot().catch(() => {});
  });
})();
