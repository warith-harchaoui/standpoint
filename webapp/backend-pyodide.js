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
 * ONE model answers every language job. The engine funnels each model call
 * through the memoized-replay contract of `beh_shim.py`: a run either returns
 * a result or reports the one LLM call it is blocked on -- prompt and JSON
 * schema included, byte-for-byte the prompt the server-side model would see.
 * `answerLLM` generates the answer, the cache is seeded, the run replays
 * (see glue.py). The answering model, in order of preference:
 *
 *   1. the OPTIONAL shared inference server (build-time `--llm-server`),
 *      a far larger model on real hardware, when it is reachable at all;
 *   2. this project's own distilled student (Qwen3-0.6B fine-tuned on
 *      Standpoint's three tasks -- pole naming, noun forms, ratings --
 *      quantised for the browser), through transformers.js over WebGPU.
 *      It downloads ONCE, up front at page load with a visible progress
 *      badge, then lives in the browser cache;
 *   3. the engine's own deterministic fallbacks (loading-derived pole words,
 *      naive plural) when neither is available -- except the ratings matrix,
 *      where a made-up neutral answer would be worse than an honest error.
 *
 * Earlier versions ran a second in-page model (a MiniLM embedder scoring pole
 * names against curated vocabularies). That split brain is gone: the student
 * was distilled on the pole-naming task too (100% on the held-out split, both
 * languages), so the page carries one inference engine and one behaviour.
 */
(() => {
  "use strict";

  const PYODIDE_URL = "https://cdn.jsdelivr.net/pyodide/v0.29.0/full/pyodide.js";
  // Pyodide-distribution packages the engine imports; vendored wheels come after.
  const PYODIDE_PACKAGES = ["numpy", "pandas", "scikit-learn", "pyyaml", "micropip"];
  // Pinned transformers.js: the inference runtime for the distilled student.
  const TRANSFORMERS_URL = "https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.7.6";
  // The distilled student, served from this deployment rather than a model hub:
  // `llm-engine/` next to index.html, holding the tokenizer, the config and
  // onnx/model_q4f16.onnx. Produced by distillation/scripts/05_export_browser.py.
  const LLM_MODEL = "llm-engine";

  // An OPTIONAL shared inference server, injected at build time by
  // `build.py --llm-server` (absent from the default build, which stays purely
  // in-browser). When present and usable it answers the engine's model calls
  // instead of the in-page student: a large model on real hardware beats a
  // 0.6B on a laptop.
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

  let py = null; // the Pyodide instance, once booted
  let bootPromise = null; // single-flight boot guard
  let strings = {}; // last i18n table fetched, for the badge messages

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

  // --- the in-page model: this project's own distilled student --------------------
  // Qwen3-0.6B fine-tuned on Standpoint's three tasks (see distillation/),
  // quantised, downloaded ONCE at page load then cached by the browser. It runs
  // through transformers.js over WebGPU.
  let transformersPromise = null;
  let llmPromise = null; // single-flight generator load

  function loadTransformers() {
    if (transformersPromise) return transformersPromise;
    transformersPromise = import(TRANSFORMERS_URL).catch((err) => {
      transformersPromise = null; // transient network failures may recover later
      throw err;
    });
    return transformersPromise;
  }

  // `window.__webllm` is a test seam, kept under its original name so the
  // existing headless checks still drive this path: CI has no WebGPU, so the
  // flow runs against a canned generator instead of a real download.
  function ensureLLM() {
    if (llmPromise) return llmPromise;
    llmPromise = (async () => {
      if (window.__webllm) return window.__webllm;
      if (!navigator.gpu) {
        throw new Error(t("flemme_nogpu", "this browser can't run the in-page AI model (WebGPU missing)."));
      }
      const mod = await loadTransformers();
      // The student is served from this deployment, not a model hub. rel("./")
      // is the deployment DIRECTORY, not the page: rel("") would resolve to
      // .../index.html and every model file under it would 404.
      mod.env.remoteHost = rel("./");
      mod.env.remotePathTemplate = "{model}/";
      const generator = await mod.pipeline("text-generation", LLM_MODEL, {
        dtype: "q4f16", // matches onnx/model_q4f16.onnx in the deployed folder
        device: "webgpu",
        progress_callback: (report) => {
          const pct = report.progress ? ` ${Math.round(report.progress)}%` : "";
          badge(t("model_loading", "Downloading the AI model (once, then cached)… ") + (report.file || "") + pct);
        },
      });
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
  // carries the engine's own JSON schema, so both paths are held to the same
  // contract: the answer is schema-valid or it is an error.
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
        response_format: { type: "json_schema", json_schema: { name: "answer", schema } },
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

  // Asked once at boot, so the prompt is up before anyone waits on a model
  // call. Deliberately cheap and deliberately silent on failure: an
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

  // 1..5 integer, neutral 3 on anything odd — mirrors the engine's _clamp_rating.
  const clampRating = (v) => {
    const n = Math.round(Number(v));
    return Number.isFinite(n) ? Math.max(1, Math.min(5, n)) : 3;
  };

  // Schema-shaped neutral defaults: empty strings push finalize_poles /
  // noun_forms onto their built-in fallbacks (loading-derived pole words, naive
  // plural); the neutral 3 matches the engine's own backfill for unrated cells.
  function neutralAnswer(schema) {
    if (!schema || schema.type !== "object") return {};
    const out = {};
    for (const [k, sub] of Object.entries(schema.properties || {})) {
      out[k] = sub.type === "object" ? neutralAnswer(sub) : sub.type === "integer" ? 3 : "";
    }
    return out;
  }

  // Force a model answer into the schema's exact shape: extra keys dropped,
  // missing or mistyped values replaced by the neutral default for their slot.
  // The engine re-validates behind this (finalize_poles, _clamp_rating), so the
  // coercion only has to guarantee the shape, never the taste.
  function coerce(schema, data) {
    if (!schema || schema.type !== "object") return data;
    if (typeof data !== "object" || data === null) return neutralAnswer(schema);
    const out = {};
    for (const [k, sub] of Object.entries(schema.properties || {})) {
      const v = data[k];
      if (sub.type === "object") out[k] = coerce(sub, v);
      else if (sub.type === "integer") out[k] = clampRating(v);
      else out[k] = typeof v === "string" ? v : "";
    }
    return out;
  }

  // The ratings matrix is the one call where a neutral fallback would be a lie:
  // a grid quietly filled with 3s looks like an answer and isn't. Its schema is
  // the only nested one (option -> {criterion -> integer}), which is how this
  // tells it apart without naming tasks.
  const needsRealModel = (schema) =>
    Object.values((schema || {}).properties || {}).some((p) => p.type === "object");

  // Ask the in-page student for one answer to the engine's prompt. The test
  // seam still speaks the old chat-completions shape; the real generator is a
  // transformers.js text-generation pipeline.
  async function studentAnswer(prompt, schema) {
    const generator = await ensureLLM();
    let text;
    if (generator.chat) {
      const reply = await generator.chat.completions.create({
        messages: [{ role: "user", content: prompt }],
        temperature: 0,
        response_format: { type: "json_object", schema: JSON.stringify(schema) },
      });
      text = reply.choices[0].message.content;
    } else {
      // max_new_tokens is sized for the largest answer (a full ratings matrix
      // runs to ~420 tokens); greedy decoding stops at EOS long before that on
      // the short ones. A truncated answer is unparseable JSON, not a short one.
      const out = await generator(
        [{ role: "user", content: prompt }],
        { max_new_tokens: 900, do_sample: false, return_full_text: false }
      );
      text = out[0].generated_text;
      if (Array.isArray(text)) text = text[text.length - 1].content;
    }
    return text;
  }

  let serverAnnounced = false; // the "answered by the shared server" note, once

  // One pending model call -> one answer object matching its JSON schema.
  // EVERY engine call lands here -- pole naming, noun forms, the ratings
  // matrix -- and every one is answered from the engine's own prompt: the
  // shared server when usable, the in-page student otherwise, the neutral
  // fallback as a last resort (except the ratings matrix, which errors
  // honestly instead).
  async function answerLLM(pending) {
    if (serverUsable()) {
      try {
        const text = await serverAnswer(pending.prompt, pending.schema);
        if (!serverAnnounced) {
          serverAnnounced = true;
          badge(t("flemme_server", "Answered by the shared AI server."), false, 4000);
          setTimeout(() => {
            badgeHeldUntil = 0;
            badge("", true);
          }, 4000);
        }
        return coerce(pending.schema, JSON.parse(stripReasoning(text)));
      } catch (err) {
        // Server unreachable, slow, off-contract, or simply not signed in: say
        // so once and carry on with the model that ships in the page.
        if (String(err.message) === "unauthenticated" && LLM_SERVER.loginUrl) {
          signInPrompt(12000);
        }
        console.warn("shared AI server unavailable, using the in-page model:", err);
      }
    }
    try {
      const text = await studentAnswer(pending.prompt, pending.schema);
      return coerce(pending.schema, JSON.parse(stripReasoning(text)));
    } catch (err) {
      if (needsRealModel(pending.schema)) throw err; // ratings: error, don't invent
      badge(t("model_offline", "AI model unavailable; using the built-in fallbacks."), true);
      return neutralAnswer(pending.schema);
    }
  }

  // --- the replay driver ----------------------------------------------------------
  // Run one glue call; on {"pending"}, answer + seed + rerun. A run makes at
  // most a handful of model calls (noun forms + pole naming, or one ratings
  // matrix), so the bound is generous, not load-bearing.
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

  // The grid's value inputs (not the name/criterion header inputs): one per
  // rating cell, exactly what "Laziness" is allowed to fill.
  function gridHasEmptyCell() {
    return [...document.querySelectorAll("#grid td input:not(.cell-name)")].some(
      (i) => !i.value.trim()
    );
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
      strings = table; // keep for the badge messages
      return table;
    },
    upload: async (file) => call("upload", { b64: await fileToB64(file), name: file.name || "" }),
    downloadXlsx: async (csv) =>
      b64ToBlob(
        await call("xlsx", { table: csv }),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
      ),
    // "Laziness" runs through the ENGINE's own suggest_ratings (same prompt,
    // parsing and clamping as the server build); the model call it blocks on
    // is answered by answerLLM like every other one.
    autofill: async (req) => {
      if (!gridHasEmptyCell()) {
        throw new Error(
          t("flemme_none", "no empty cells to fill — add an option, a criterion, or clear a cell first.")
        );
      }
      return call("autofill", req);
    },
    position: async (req) => call("position", req),
  };

  window.addEventListener("DOMContentLoaded", () => {
    // Everything downloads up front, not on first click: the Python engine and
    // the model, each with visible progress, so the first Generate is instant
    // and the visitor knows what is being fetched and that it happens once.
    boot().catch(() => {});
    // ...and ask the shared gateway whether this visitor has a session, so the
    // sign-in prompt is up before any model call falls back.
    probeServerSession();
    if (window.spBusy) window.spBusy.start();
    ensureLLM()
      .catch((err) => badge(String(err.message || err), true)) // said once; retried on first use
      .finally(() => {
        if (window.spBusy) window.spBusy.end();
      });
  });
})();
