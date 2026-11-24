// Static (GitHub Pages) version of the experiment – the same flow as the Flask app (webpage/app.py):
// intro (language, instructions, image preload) -> for every block (one category of 4 objects):
// training screen with the 4 objects laid out like the answer buttons -> one screen per trial -> ... -> end.
//
// Every participant gets one sequence picked at random from the pre-generated pool in data.json.
// Each answer is queued in localStorage and sent to Google Sheets right away (config.js: SHEETS_URL);
// unsent answers are retried, so nothing is lost if the network drops or the participant leaves early.
// Progress is kept in localStorage too: reloading the page mid-test continues at the same image.

"use strict";

const CONFIG = window.CONFIG || {};
const STATE_KEY = "ksy-state";
const QUEUE_KEY = "ksy-queue";
const TEST_KEYS = ["theme", "view", "zoom", "answer_mode", "colors", "exposure_ms", "next_delay_s"];

let DATA;      // data.json
let state;     // participant progress, saved in localStorage
let queue;     // answers not yet confirmed by Google Sheets

// ---------- Storage ----------

function load(key, fallback) {
  try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; }
}
function store(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* private window: keep in memory only */ }
}
const saveState = () => store(STATE_KEY, state);

// ---------- Helpers ----------

const app = () => document.getElementById("app");
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const fmt = (text, values) => text.replace(/\{(\w+)\}/g, (m, k) => (k in values ? values[k] : m));
const t = () => DATA.ui[state.lang];
const item = (name) => DATA.item_names[state.lang]?.[name] ?? name;

function randomHex(bytes) {
  const buf = crypto.getRandomValues(new Uint8Array(bytes));
  return Array.from(buf, (b) => b.toString(16).padStart(2, "0")).join("");
}
function randomInt(n) {
  return crypto.getRandomValues(new Uint32Array(1))[0] % n;
}
function localTimestamp() {  // like Python's datetime.now().isoformat(timespec="seconds")
  const d = new Date(), p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

/** Overridable from the test panel in test mode, otherwise the default from app.py. */
function setting(key) {
  const defaults = { theme: DATA.choices.theme[0], view: DATA.choices.view[0], zoom: "random", ...DATA.settings };
  return state.test && state.opts[key] !== undefined ? state.opts[key] : defaults[key];
}

function sequence() { return DATA.sequences[state.seq]; }

function trials() {
  return sequence().trials.map(([imageIndex, zoom, options, block, answerMode]) => {
    const img = DATA.images[imageIndex];
    return {
      image_id: img.id, image: `images/${img.id}.webp`, correct: img.correct,
      occlusion_percentage: img.occlusion_percentage, key_parts_shown: img.key_parts_shown,
      options: options.map((i) => DATA.items[i]), zoom, block, answer_mode: answerMode,
    };
  });
}

/** "random" = the per-block mode from the sequence (half text, half image); test panel can force one. */
function trialAnswerMode(trial) {
  const choice = setting("answer_mode");
  return choice === "random" ? trial.answer_mode : choice;
}

function trialZoom(trial) {
  const choice = String(setting("zoom"));
  return choice !== "random" && DATA.choices.zoom.includes(choice) ? Number(choice) : trial.zoom;
}

// ---------- Participant ----------

/** New participant and random sequence; keeps language and test-panel settings (like "/" in app.py). */
function newParticipant() {
  state = {
    build: DATA.build, lang: state?.lang ?? DATA.default_language,
    test: state?.test ?? false, opts: state?.opts ?? {},
    participant: randomHex(4), seq: randomInt(DATA.sequences.length), screen: "intro",
  };
  saveState();
}

function go(screen) {
  state.screen = screen;
  saveState();
  render();
}

// ---------- Saving answers ----------

let sending = false;
let retryTimer = null;

function enqueue(row) {
  queue.push(row);
  store(QUEUE_KEY, queue);
  flushQueue();
}

function payload(rows) {
  return JSON.stringify({ columns: DATA.csv_columns, rows });
}

async function flushQueue() {
  updateSaveStatus();
  if (sending || queue.length === 0) return;
  if (!CONFIG.SHEETS_URL) {
    console.warn("SHEETS_URL is empty (config.js) – answers are kept only in this browser:", queue);
    return;
  }
  sending = true;
  const batch = queue.slice(0, 50);
  try {
    // text/plain = a "simple" request: no CORS preflight, which Apps Script does not answer.
    const response = await fetch(CONFIG.SHEETS_URL, {
      method: "POST", headers: { "Content-Type": "text/plain;charset=utf-8" }, body: payload(batch),
    });
    const result = await response.json();
    if (!result.ok) throw new Error(result.error || "not saved");
    const sent = new Set(batch.map((r) => r.row_id));
    queue = queue.filter((r) => !sent.has(r.row_id));   // answers added meanwhile stay queued
    store(QUEUE_KEY, queue);
    sending = false;
    if (queue.length) flushQueue();
  } catch (error) {
    sending = false;
    console.warn("Saving failed, retrying in 5 s:", error);
    clearTimeout(retryTimer);
    retryTimer = setTimeout(flushQueue, 5000);
  }
  updateSaveStatus();
}

/** Last chance when the tab is closed: fire-and-forget. Rows stay queued; the sheet ignores duplicates. */
function beaconQueue() {
  if (CONFIG.SHEETS_URL && queue.length && navigator.sendBeacon) {
    navigator.sendBeacon(CONFIG.SHEETS_URL, new Blob([payload(queue.slice(0, 50))], { type: "text/plain;charset=utf-8" }));
  }
}

function updateSaveStatus() {
  const status = document.getElementById("save-status");
  if (status) status.textContent = queue.length ? t().saving : t().saved;
  const info = document.getElementById("queue-info");
  if (info) info.textContent = `unsent ${queue.length}${CONFIG.SHEETS_URL ? "" : " (no SHEETS_URL)"}`;
}

// ---------- Rendering ----------

function render() {
  const lang = state.lang;
  document.documentElement.lang = lang;
  document.documentElement.dataset.theme = setting("theme");
  document.body.className = `view-${setting("view")} colors-${setting("colors")}`;
  document.title = t().title;
  renderTestPanel();
  window.scrollTo(0, 0);
  ({ intro: renderIntro, trial: renderTrial, end: renderEnd })[state.screen]();
}

function renderTestPanel() {
  const panel = document.getElementById("test-panel");
  if (!state.test) { panel.style.display = "none"; panel.innerHTML = ""; return; }
  panel.style.display = "";
  const links = (key, values, label = (v) => v) => values.map((v) =>
    `<a href="#" data-set="${key}" data-value="${esc(v)}" ${String(v) === String(key === "lang" ? state.lang : setting(key)) ? 'class="on"' : ""}>${esc(label(v))}</a>`).join(" ");
  panel.innerHTML = `
    <strong>TEST</strong>
    ${links("lang", Object.keys(DATA.languages))}
    <span>|</span> ${links("theme", DATA.choices.theme)}
    <span>|</span> ${links("view", DATA.choices.view)}
    <span>|</span> zoom ${links("zoom", DATA.choices.zoom, (z) => (z === "random" ? z : `${z}×`))}
    <span>|</span> answers ${links("answer_mode", DATA.choices.answer_mode)}
    <span>|</span> images ${links("colors", DATA.choices.colors)}
    <span>|</span>
    <form id="test-form">
      <label>exposure <input type="number" name="exposure_ms" value="${setting("exposure_ms")}" min="50" max="10000" step="50"> ms</label>
      <label>next <input type="number" name="next_delay_s" value="${setting("next_delay_s")}" min="0" max="30"> s</label>
      <button>set</button>
    </form>
    <span>|</span> <a href="#" data-restart>restart</a>
    <span class="info">participant ${state.participant} · seed ${sequence().seed} · <span id="queue-info"></span></span>`;
  for (const a of panel.querySelectorAll("[data-set]")) {
    a.addEventListener("click", (event) => {
      event.preventDefault();
      if (a.dataset.set === "lang") state.lang = a.dataset.value;
      else state.opts[a.dataset.set] = a.dataset.value;
      saveState();
      render();
    });
  }
  panel.querySelector("#test-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    const clamp = (v, low, high) => Math.max(low, Math.min(high, Math.round(Number(v))));
    if (form.get("exposure_ms") !== "") state.opts.exposure_ms = clamp(form.get("exposure_ms"), 50, 10000);
    if (form.get("next_delay_s") !== "") state.opts.next_delay_s = clamp(form.get("next_delay_s"), 0, 30);
    saveState();
    render();
  });
  panel.querySelector("[data-restart]").addEventListener("click", (event) => {
    event.preventDefault();
    newParticipant();
    render();
  });
  updateSaveStatus();
}

const preloaded = [];
function preload(src) {
  const img = new Image();
  img.src = src;
  preloaded.push(img);  // keep a reference so the browser keeps it cached
}

/** Estimated test length as a range of whole minutes – same formula as duration_minutes() in app.py. */
function durationMinutes(list) {
  const blocks = new Set(list.map((trial) => trial.block)).size;
  const seconds = list.length * (setting("exposure_ms") / 1000 + DATA.settings.seconds_per_answer)
    + blocks * DATA.settings.seconds_per_training;
  const low = Math.max(1, Math.floor(seconds / 60));
  return { low, high: low + 1 };
}

function renderIntro() {
  const tx = t(), list = trials();
  // Preload every image while the participant reads the instructions.
  for (const trial of list) preload(trial.image);
  for (const src of Object.values(DATA.training_images)) preload(src);

  let exposure = String(setting("exposure_ms") / 1000);
  if (state.lang !== "en") exposure = exposure.replace(".", ",");
  app().innerHTML = `
    <div class="language-choice">
      ${esc(tx.choose_language)}:
      ${Object.entries(DATA.languages).map(([code, name]) =>
        `<a href="#" data-lang="${code}" class="lang-button ${code === state.lang ? "on" : ""}">${esc(name)}</a>`).join("")}
    </div>
    <h1>${esc(tx.title)}</h1>
    <p>${esc(tx.thanks)}</p>
    <ul class="instructions">
      <li>${fmt(tx.instr_count, { n: list.length })}</li>
      <li>${fmt(tx.instr_exposure, { s: exposure })}</li>
      <li>${tx.instr_choose}</li>
      <li>${tx.instr_groups}</li>
      <li>${tx.instr_speed}</li>
      <li>${fmt(tx.instr_anon, durationMinutes(list))}</li>
    </ul>
    <form class="about" id="about">
      <h2>${esc(tx.about_title)}</h2>
      ${radioGroup("age_group", tx.age_label, DATA.age_groups, tx.age_groups)}
      ${radioGroup("device", tx.device_label, DATA.devices, tx.devices)}
      <button class="primary" id="continue">${esc(tx.continue)}</button>
    </form>`;
  for (const a of app().querySelectorAll("[data-lang]")) {
    a.addEventListener("click", (event) => {
      event.preventDefault();
      state.lang = a.dataset.lang;
      saveState();
      render();
    });
  }
  // Keep the choices when the language is switched (the screen is re-rendered).
  const about = document.getElementById("about");
  for (const key of ["age_group", "device"]) {
    if (state[key]) about.querySelector(`input[name="${key}"][value="${CSS.escape(state[key])}"]`)?.click();
  }
  about.addEventListener("change", (event) => { state[event.target.name] = event.target.value; saveState(); });
  // The browser checks the required radio buttons before "submit" fires.
  about.addEventListener("submit", (event) => {
    event.preventDefault();
    const form = new FormData(about);
    Object.assign(state, {
      age_group: form.get("age_group"), device: form.get("device"), screen_size: `${screen.width}x${screen.height}`,
      index: 0, correct: 0, trained_block: 0, started_at: Date.now(),
    });
    go("trial");
  });
}

function radioGroup(name, legend, codes, labels) {
  return `<fieldset>
    <legend>${esc(legend)}</legend>
    ${codes.map((code) => `<label class="choice"><input type="radio" name="${name}" value="${esc(code)}" required> ${esc(labels[code])}</label>`).join("")}
  </fieldset>`;
}

/** Before each block: its 4 objects, unoccluded, in the same layout as the answer buttons. */
function renderTraining(trial, blocks) {
  const tx = t(), mode = trialAnswerMode(trial);
  app().innerHTML = `
    <h1>${esc(fmt(tx.training_title, { i: trial.block, n: blocks }))}</h1>
    <p>${esc(tx.training_text)}</p>
    <p class="answer-mode-note">${mode === "image" ? tx.training_mode_image : tx.training_mode_text}</p>
    <div class="answers answers-${esc(mode)}">
      ${trial.options.map((name) => `
        <figure class="training-card">
          ${DATA.training_images[name] ? `<img src="${esc(DATA.training_images[name])}" alt="${esc(item(name))}">` : ""}
          <figcaption>${esc(item(name))}</figcaption>
        </figure>`).join("")}
    </div>
    <button class="primary" id="start">${esc(trial.block === 1 ? tx.start : tx.continue)}</button>`;
  document.getElementById("start").addEventListener("click", () => {
    state.trained_block = trial.block;
    go("trial");
  });
}

function renderTrial() {
  const list = trials();
  if (state.index >= list.length) { go("end"); return; }
  const tx = t(), trial = list[state.index], zoom = trialZoom(trial);
  if (state.trained_block !== trial.block) {   // new block: show its objects first
    renderTraining(trial, list[list.length - 1].block);
    return;
  }
  const exposureMs = Number(setting("exposure_ms"));
  const answerMode = trialAnswerMode(trial);

  const option = (name) => (answerMode === "image" && DATA.training_images[name]
    // Image mode falls back to the name for items without a training image.
    ? `<button value="${esc(name)}"><img src="${esc(DATA.training_images[name])}" alt="${esc(item(name))}"></button>`
    : `<button value="${esc(name)}">${esc(item(name))}</button>`);

  app().innerHTML = `
    <p class="progress">${esc(fmt(tx.progress, { i: state.index + 1, n: list.length }))}
      ${state.test ? `<span id="countdown"></span> · ${esc(trial.image_id)} · ${esc(item(trial.correct))} · zoom ${zoom}×` : ""}</p>
    <div id="image-frame">
      <img id="stimulus" src="${esc(trial.image)}" alt="" style="--zoom: ${zoom}">
    </div>
    <div id="answer-form" hidden>
      <p class="question">${esc(tx.question)}</p>
      <div id="answers" class="answers answers-${esc(answerMode)}">${trial.options.map(option).join("")}</div>
    </div>`;

  // Same timing as static/trial.js: show the image for exposureMs, then hide it and show the answers;
  // the reaction time runs from that moment to the answer click.
  const image = document.getElementById("stimulus");
  const answers = document.getElementById("answer-form");
  const countdown = document.getElementById("countdown");
  let answersShownAt = 0, answered = false;

  function showAnswers() {
    document.getElementById("image-frame").hidden = true;
    answers.hidden = false;
    answersShownAt = performance.now();
  }
  function startExposure() {
    const start = performance.now();
    setTimeout(showAnswers, exposureMs);
    if (countdown) {
      const tick = setInterval(() => {
        const left = Math.max(0, exposureMs - (performance.now() - start));
        countdown.textContent = `· ${(left / 1000).toFixed(1)} s`;
        if (left === 0) clearInterval(tick);
      }, 50);
    }
  }
  if (image.complete) startExposure();
  else image.addEventListener("load", startExposure, { once: true });

  answers.addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (!button || answered) return;
    answered = true;
    const rt = Math.round(performance.now() - answersShownAt);
    const chosen = button.value;
    const isCorrect = Number(chosen === trial.correct);

    enqueue({
      row_id: `${state.participant}-${state.index + 1}`,
      test: state.test,
      participant: state.participant,
      seed: sequence().seed,
      language: state.lang,
      age_group: state.age_group,
      device: state.device,
      screen: state.screen_size,
      trial_order: state.index + 1,
      block: trial.block,
      image_id: trial.image_id,
      occlusion_percentage: trial.occlusion_percentage,
      key_parts_shown: trial.key_parts_shown,
      options: trial.options.join("|"),
      correct_answer: trial.correct,
      chosen_answer: chosen,
      is_correct: isCorrect,
      reaction_time_ms: rt,
      exposure_ms: exposureMs,
      zoom,
      answer_mode: answerMode,
      colors: setting("colors"),
      timestamp: localTimestamp(),
    });
    // Advance right away, so a reload never repeats an answered trial.
    state.index += 1;
    state.correct += isCorrect;
    saveState();

    if (!state.test) { render(); return; }

    // Test mode: show the result, then continue after a countdown.
    for (const b of answers.querySelectorAll("button")) {
      b.disabled = true;
      if (b.value === trial.correct) b.classList.add("correct");
      else if (b === button) b.classList.add("wrong");
    }
    let left = Number(setting("next_delay_s"));
    const tick = () => {
      countdown.textContent = `· RT ${rt} ms · next in ${left} s`;
      if (left-- === 0) render();
      else setTimeout(tick, 1000);
    };
    tick();
  });
}

function renderEnd() {
  const tx = t();
  app().innerHTML = `
    <h1>${esc(tx.done)}</h1>
    <p>${esc(fmt(tx.summary, { correct: state.correct, total: state.index, seconds: Math.round((Date.now() - state.started_at) / 1000) }))}</p>
    <p class="muted" id="save-status"></p>`;
  updateSaveStatus();
}

// ---------- Start ----------

async function init() {
  try {
    DATA = await fetch("data.json", { cache: "no-cache" }).then((r) => r.json());
  } catch (error) {
    app().textContent = "Could not load data.json – open the page through a web server, not as a file.";
    throw error;
  }
  queue = load(QUEUE_KEY, []);
  state = load(STATE_KEY, null);

  const params = new URLSearchParams(location.search);

  // Continue an unfinished test after a reload; otherwise (or after a rebuild of data.json) start fresh.
  const resumable = state && state.build === DATA.build && state.screen === "trial" && DATA.sequences[state.seq];
  if (!resumable) newParticipant();
  if (params.has("test")) state.test = params.get("test") !== "0";
  if (!CONFIG.ALLOW_TEST_MODE) state.test = false;
  if (!DATA.ui[state.lang]) state.lang = DATA.default_language;
  saveState();
  render();

  flushQueue();
  window.addEventListener("online", flushQueue);
  window.addEventListener("pagehide", beaconQueue);
}

init();
