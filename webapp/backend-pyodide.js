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
 * seed the cache, and run again (see glue.py). Two model tiers, each loaded
 * only when its feature is first used:
 *
 *   - AXIS NAMING (default, automatic): a small multilingual embedding model
 *     (transformers.js MiniLM, a few dozen MB, loaded on first Generate and
 *     browser-cached) scores each pole's criteria against a curated vocabulary
 *     of positive qualities (vocab/<lang>.json) and picks the nearest word;
 *     the engine's own `finalize_poles` still validates/dedupes, with the
 *     loading-derived words as the offline fallback.
 *   - "LAZINESS" AUTO-FILL (one direct LLM call): this project's own distilled
 *     student (Qwen3-0.6B fine-tuned on Standpoint's three tasks, 4-bit, ~640 MB,
 *     downloaded on the first Paresse click then cached) answers the engine's own
 *     localized ratings prompt and the blanks fill in — no panel, no copy-paste.
 *     It runs through transformers.js over WebGPU, the SAME runtime the axis
 *     naming already uses: the page carries one inference engine, not two.
 */
(() => {
  "use strict";

  const PYODIDE_URL = "https://cdn.jsdelivr.net/pyodide/v0.29.0/full/pyodide.js";
  // Pyodide-distribution packages the engine imports; vendored wheels come after.
  const PYODIDE_PACKAGES = ["numpy", "pandas", "scikit-learn", "pyyaml", "micropip"];
  // Same embedding stack as harchaoui.org's in-page semantic search: pinned
  // transformers.js + the multilingual MiniLM (covers the GUI's en/fr/es). v3,
  // not the v2 this started on, because v3 is what can run the distilled student
  // below on WebGPU — one library for both jobs.
  const TRANSFORMERS_URL = "https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.7.6";
  const EMBED_MODEL = "Xenova/paraphrase-multilingual-MiniLM-L12-v2";
  // The distilled student, served from this deployment rather than a model hub:
  // `llm-engine/` next to index.html, holding the tokenizer, the config and
  // onnx/model_q4f16.onnx. Produced by distillation/scripts/05_export_browser.py.
  const LLM_MODEL = "llm-engine";

  // An OPTIONAL shared inference server, injected at build time by
  // `build.py --llm-server` (absent from the default build, which stays purely
  // in-browser). When present and usable it answers Laziness instead of the
  // in-page model: a large model on real hardware beats a 0.6B on a laptop.
  //
  // "Usable" is narrower than "configured", and the page decides rather than
  // guessing. A browser refuses to let an https:// page call an http:// server
  // (mixed content, unbypassable), so an http endpoint is only attempted from
  // an http origin. Everything else falls back to the in-page model, which is
  // always there. The check is made before any request so a blocked call never
  // reaches the console as an error.
  //
  // `path` lets the endpoint be an OpenAI-compatible gateway rather than a raw
  // vLLM (/api/chat/completions on an Open-WebUI, say). `credentials: "include"`
  // goes with a gateway that authenticates by cookie: the visitor's existing SSO
  // session then authorises the call and no token ships in the page. It must
  // stay off for a server answering `Access-Control-Allow-Origin: *`, which
  // browsers refuse to combine with credentials.
  const LLM_SERVER = window.__standpointLLMServer || null;

  function serverUsable() {
    if (!LLM_SERVER || !LLM_SERVER.url) return false;
    const endpointIsHttp = /^http:\/\//i.test(LLM_SERVER.url);
    return !(endpointIsHttp && location.protocol === "https:");
  }

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
  // A message worth reading has to survive the next progress tick. `hold`
  // reserves the badge for a few seconds; ordinary progress writes politely
  // wait their turn rather than overwriting it. Without this the "sign in for
  // the fast path" hint is replaced by a download percentage within one frame,
  // which is exactly when the visitor most needs to read it.
  let badgeHeldUntil = 0;

  function badge(text, done, hold, link) {
    const now = Date.now();
    if (hold) badgeHeldUntil = now + hold;
    else if (now < badgeHeldUntil) return;

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
    // A link, when the message is only actionable by going somewhere. Built as
    // a node rather than innerHTML: `text` is localized content, and nothing
    // that reaches this function should ever be parsed as markup.
    if (link) {
      const a = document.createElement("a");
      a.href = link.href;
      a.target = "_blank";
      a.rel = "noopener";
      a.textContent = " " + link.label;
      a.style.cssText = "color:#93c5fd;text-decoration:underline";
      el.appendChild(a);
    }
    if (done) setTimeout(() => el.remove(), 2500); // fade out once settled
  }

  // --- boot: Pyodide + numeric stack + vendored wheels + shim/glue ----------------
  async function boot() {
    if (bootPromise) return bootPromise;
    bootPromise = (async () => {
      // Light the page's header activity ring for the whole boot (the page
      // wraps its backend calls, but the background boot starts on its own).
      if (window.spBusy) window.spBusy.start();
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
    })()
      .catch((err) => {
        bootPromise = null; // allow a retry on the next call
        badge("Python engine failed: " + err.message);
        throw err;
      })
      .finally(() => {
        if (window.spBusy) window.spBusy.end();
      });
    return bootPromise;
  }

  // --- the shared transformers.js runtime -----------------------------------------
  // One library, two models, two different roots: the MiniLM comes from the
  // model hub, the distilled student from this deployment. transformers.js keeps
  // that root in a module-level `env`, so the only safe way to use both is to
  // set it around each load and to let no two loads overlap — hence the lock.
  //
  // The rejected alternative was `allowLocalModels = true` with a shared
  // `localModelPath`: the hub model is then looked for locally first, which
  // costs four 404s in every visitor's console before the fallback succeeds.
  let transformersPromise = null;
  let pipelineLock = Promise.resolve();

  function loadTransformers() {
    if (transformersPromise) return transformersPromise;
    transformersPromise = import(TRANSFORMERS_URL).catch((err) => {
      transformersPromise = null; // transient network failures may recover later
      throw err;
    });
    return transformersPromise;
  }

  // Build one pipeline with `env` pointed at `host`/`template`, restoring it
  // after, and queued behind any load already in flight.
  function withModelRoot(mod, host, template, build) {
    const run = pipelineLock.then(async () => {
      const prevHost = mod.env.remoteHost;
      const prevTemplate = mod.env.remotePathTemplate;
      mod.env.remoteHost = host;
      mod.env.remotePathTemplate = template;
      try {
        return await build();
      } finally {
        mod.env.remoteHost = prevHost;
        mod.env.remotePathTemplate = prevTemplate;
      }
    });
    pipelineLock = run.catch(() => {}); // a failed load must not wedge the queue
    return run;
  }

  const HUB_HOST = "https://huggingface.co/";
  const HUB_TEMPLATE = "{model}/resolve/{revision}/";

  // --- axis naming: small embedding model + curated vocabulary ---------------------
  // `window.__embedder` is a test seam: headless CI answers with a canned pipeline
  // instead of downloading the real model.
  function ensureEmbedder() {
    if (embedderPromise) return embedderPromise;
    embedderPromise = (window.__embedder
      ? Promise.resolve(window.__embedder)
      : loadTransformers().then((mod) =>
          withModelRoot(mod, HUB_HOST, HUB_TEMPLATE, () =>
            mod.pipeline("feature-extraction", EMBED_MODEL)
          )
        )
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
  // naming (default-on); anything else (noun forms) -> neutral, i.e. the engine's
  // built-in fallback. Auto-fill never reaches here: it is fully client-side.
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
    return neutralAnswer(pending.schema); // noun forms and anything unforeseen
  }

  // --- "Laziness": ONE in-browser LLM call fills the empty cells, nothing else ----
  // This project's own distilled student (see distillation/): Qwen3-0.6B
  // fine-tuned on Standpoint's three tasks, 4-bit, ~640 MB, downloaded on the
  // FIRST Paresse click then cached by the browser. It answers the engine's own
  // localized ratings prompt; the page then writes ONLY the still-empty cells,
  // so nothing the user typed is ever overwritten.
  //
  // It replaced a generic Qwen2.5-1.5B loaded through WebLLM: smaller, better on
  // these three jobs specifically (the distillation README has the numbers), and
  // it runs on the transformers.js the page already loads for the axis naming —
  // so the page went from two in-browser inference engines to one.
  let llmPromise = null; // single-flight generator load

  // `window.__webllm` is a test seam, kept under its original name so the
  // existing headless checks still drive this path: CI has no WebGPU, so the
  // flow runs against a canned generator instead of a 640 MB download.
  function ensureLLM() {
    if (llmPromise) return llmPromise;
    llmPromise = (async () => {
      if (window.__webllm) return window.__webllm;
      if (!navigator.gpu) {
        throw new Error(t("flemme_nogpu", "this browser can't run the in-page AI model (WebGPU missing)."));
      }
      const mod = await loadTransformers();
      // rel("./") is the deployment DIRECTORY, not the page: rel("") would
      // resolve to .../index.html and every model file under it would 404.
      const generator = await withModelRoot(mod, rel("./"), "{model}/", () =>
        mod.pipeline("text-generation", LLM_MODEL, {
          dtype: "q4f16", // matches onnx/model_q4f16.onnx in the deployed folder
          device: "webgpu",
          progress_callback: (report) => {
            const pct = report.progress ? ` ${Math.round(report.progress)}%` : "";
            badge(t("flemme_model", "Loading the AI model… ") + (report.file || "") + pct);
          },
        })
      );
      badge("", true);
      return generator;
    })().catch((err) => {
      llmPromise = null; // transient network / GPU hiccups may recover on retry
      badge("", true);
      throw err;
    });
    return llmPromise;
  }

  // One OpenAI-compatible chat call against the shared server. `response_format`
  // carries the same JSON schema the in-browser path builds, so both paths are
  // held to the same contract: the answer is schema-valid or it is an error.
  async function serverAnswer(prompt, schema, signal) {
    const endpoint =
      LLM_SERVER.url.replace(/\/+$/, "") + (LLM_SERVER.path || "/v1/chat/completions");
    const res = await fetch(endpoint, {
      method: "POST",
      credentials: LLM_SERVER.credentials || "omit",
      headers: {
        "Content-Type": "application/json",
        ...(LLM_SERVER.key ? { Authorization: "Bearer " + LLM_SERVER.key } : {}),
      },
      body: JSON.stringify({
        model: LLM_SERVER.model,
        messages: [{ role: "user", content: prompt }],
        temperature: 0,
        max_tokens: 900,
        response_format: { type: "json_schema", json_schema: { name: "ratings", schema } },
      }),
      signal,
    });
    // 401/403 is not a breakage, it is "you are not signed in to the gateway".
    // Say that specifically -- the fix is one login away, and the fallback that
    // follows would otherwise look like the server simply not existing.
    if (res.status === 401 || res.status === 403) throw new Error("unauthenticated");
    if (!res.ok) throw new Error(`server ${res.status}`);
    const data = await res.json();
    return data.choices[0].message.content;
  }

  // Telling someone to sign in without saying where is not much help, and the
  // page cannot sign them in itself: this host serves static files only, with no
  // server side to complete an SSO handshake. So it points at the gateway's own
  // login, which is one click and one tab away, and after which this page works
  // with no further setup -- the browser sends that session's cookie on the very
  // next call.
  function signInPrompt(hold) {
    badge(
      t(
        "flemme_server_login",
        "Sign in to the shared AI server for the fast path. Using the in-page model meanwhile."
      ),
      false,
      hold,
      { href: LLM_SERVER.loginUrl, label: t("flemme_server_login_link", "Sign in") }
    );
  }

  // Asked once at boot, so the prompt is up before anyone clicks Laziness and
  // waits on it. Deliberately cheap and deliberately silent on failure: an
  // unreachable gateway is the in-page model's cue, not an error to report.
  function probeServerSession() {
    if (!serverUsable() || !LLM_SERVER.loginUrl) return;
    fetch(LLM_SERVER.url.replace(/\/+$/, "") + "/api/models", { credentials: "include" })
      .then((r) => {
        if (r.status === 401 || r.status === 403) signInPrompt(10000);
      })
      .catch(() => {});
  }

  // Qwen3's chat template writes an empty <think></think> pair in front of every
  // assistant turn, so the training targets carried it and the student
  // reproduces it. Left in, JSON.parse fails on answers that are in fact
  // correct. A ```json fence is stripped too, for the same reason.
  function stripReasoning(text) {
    const withoutThink = String(text).replace(/^\s*<think>[\s\S]*?<\/think>\s*/, "");
    const fenced = withoutThink.match(/^\s*```(?:json)?\s*([\s\S]*?)\s*```\s*$/);
    return (fenced ? fenced[1] : withoutThink).trim();
  }

  function buildRatingsPrompt(req) {
    const tpl = strings.ratings_prompt || "";
    return tpl
      .replace("{noun}", req.noun || "Option")
      .replace("{options}", (req.options || []).join(", "))
      .replace("{criteria}", (req.criteria || []).join(", "))
      .replace(/\{\{/g, "{")
      .replace(/\}\}/g, "}"); // {{ }} are literal braces in the template's example
  }

  function gridHasEmptyCell() {
    // The grid's value inputs (not the name/criterion header inputs): one per
    // rating cell, exactly what "Laziness" is allowed to fill.
    return [...document.querySelectorAll("#grid td input:not(.cell-name)")].some(
      (i) => !i.value.trim()
    );
  }

  // 1..5 integer, neutral 3 on anything odd — mirrors the engine's _clamp_rating.
  const clampRating = (v) => {
    const n = Math.round(Number(v));
    return Number.isFinite(n) ? Math.max(1, Math.min(5, n)) : 3;
  };

  async function llmAutofill(req) {
    if (!gridHasEmptyCell()) {
      throw new Error(
        t("flemme_none", "no empty cells to fill — add an option, a criterion, or clear a cell first.")
      );
    }
    // Same shape the server engine constrains its model with: every option maps
    // to an object of its criteria, each an integer.
    const schema = {
      type: "object",
      properties: Object.fromEntries(
        (req.options || []).map((o) => [
          o,
          {
            type: "object",
            properties: Object.fromEntries(
              (req.criteria || []).map((c) => [c, { type: "integer" }])
            ),
            required: req.criteria || [],
          },
        ])
      ),
      required: req.options || [],
    };
    // The shared server first when it can be reached at all: it is a far larger
    // model and it answers in seconds, where the in-page one takes minutes on a
    // CPU fallback. A failure here is not fatal -- the in-page model is still
    // there, and the user gets an answer either way.
    if (serverUsable()) {
      try {
        const answer = JSON.parse(stripReasoning(await serverAnswer(buildRatingsPrompt(req), schema)));
        badge(t("flemme_server", "Filled by the shared AI server."), false, 6000);
        setTimeout(() => {
          badgeHeldUntil = 0;
          badge("", true);
        }, 6000);
        const filled = {};
        for (const o of req.options || []) {
          const row = answer[o] || {};
          filled[o] = Object.fromEntries((req.criteria || []).map((c) => [c, clampRating(row[c])]));
        }
        return filled;
      } catch (err) {
        // Server unreachable, slow, off-contract, or simply not signed in: say
        // so once and carry on with the model that ships in the page.
        if (String(err.message) === "unauthenticated" && LLM_SERVER.loginUrl) {
          signInPrompt(12000);
        }
        console.warn("shared AI server unavailable, using the in-page model:", err);
      }
    }

    const generator = await ensureLLM();
    // The test seam still speaks the old chat-completions shape; the real
    // generator is a transformers.js text-generation pipeline.
    let text;
    if (generator.chat) {
      const reply = await generator.chat.completions.create({
        messages: [{ role: "user", content: buildRatingsPrompt(req) }],
        temperature: 0,
        response_format: { type: "json_object", schema: JSON.stringify(schema) },
      });
      text = reply.choices[0].message.content;
    } else {
      // max_new_tokens is sized for the matrix: the teacher's own answers ran to
      // ~420 tokens, and a truncated answer is unparseable JSON, not a short one.
      const out = await generator(
        [{ role: "user", content: buildRatingsPrompt(req) }],
        { max_new_tokens: 900, do_sample: false, return_full_text: false }
      );
      text = out[0].generated_text;
      if (Array.isArray(text)) text = text[text.length - 1].content;
    }
    const data = JSON.parse(stripReasoning(text));
    // Clamp every rating and backfill gaps, so the grid always gets a full matrix.
    const out = {};
    for (const o of req.options || []) {
      const row = data[o] || {};
      out[o] = Object.fromEntries((req.criteria || []).map((c) => [c, clampRating(row[c])]));
    }
    return out;
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
    // Example tables + string tables are exported at build time: instant, no
    // Python. `name` picks one of the shipped datasets ("" the default), `lang`
    // its language variant: <name>.<lang>.csv when shipped, base <name>.csv
    // otherwise (each dataset has one base file plus translated twins).
    example: async (name, lang) => {
      const id = /^[a-z_]+$/.test(name || "") ? name : "programming_languages";
      if (/^[a-z]{2}$/.test(lang || "")) {
        const localized = await fetch(rel("examples/" + id + "." + lang + ".csv"));
        if (localized.ok) return localized.text();
      }
      const res = await fetch(rel("examples/" + id + ".csv"));
      if (res.ok) return res.text();
      return (await fetch(rel("examples/programming_languages.csv"))).text();
    },
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
    autofill: llmAutofill, // one in-browser LLM call fills the blanks, nothing else
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
    // ...and ask the shared gateway whether this visitor has a session, so the
    // sign-in prompt is up before they click Laziness rather than after it has
    // already fallen back.
    probeServerSession();
  });
})();
