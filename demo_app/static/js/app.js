// Copyright (c) 2026 Sankalp Gaonkar. EVP demo v2 frontend logic (no external libraries).
"use strict";
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const APP = ["N", "E", "S", "W"];
const NAMES = { N: "North", E: "East", S: "South", W: "West" };
const DIR = { N: [0, 1], S: [0, -1], E: [-1, 0], W: [1, 0] }; // travel direction (screen, y down)
const COL = { G: "#22c55e", Y: "#f5b301", R: "#ef4444" };
const state = {
  cfg: null, job: null, res: null, mode: "preemption", overlay: "all",
  t: 0, playing: false, lastTs: null, speed: 1, vidDur: 0, simDur: 0,
  inject: [], logRows: [], frameTimes: [],
  processingSample: false,
};

// ---------------------------------------------------------------- utilities
function api(path, opt = {}) {
  return fetch(path, opt).then(async r => {
    const ct = r.headers.get("content-type") || "";
    const body = ct.includes("json") ? await r.json() : await r.text();
    if (!r.ok) throw new Error((body && body.error) || `HTTP ${r.status}`);
    return body;
  });
}
function toast(msg, ms = 3200) {
  const t = $("#toast"); t.textContent = msg; t.hidden = false;
  clearTimeout(toast._h); toast._h = setTimeout(() => (t.hidden = true), ms);
}
const fmt = (x, d = 1) => (x === null || x === undefined || Number.isNaN(x)) ? "–" : Number(x).toFixed(d);
function cssVar(n) { return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); }
function bsearch(arr, t, key = x => x) { // last index with key <= t
  let lo = 0, hi = arr.length - 1, ans = -1;
  while (lo <= hi) { const m = (lo + hi) >> 1; if (key(arr[m]) <= t) { ans = m; lo = m + 1; } else hi = m - 1; }
  return ans;
}
function fitCanvas(c) {
  const r = c.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
  const w = Math.max(1, Math.round(r.width * dpr)), h = Math.max(1, Math.round(r.height * dpr));
  if (c.width !== w || c.height !== h) { c.width = w; c.height = h; }
  const ctx = c.getContext("2d"); ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return [ctx, r.width, r.height];
}
function setStep(n) {
  ["#st1", "#st2", "#st3"].forEach((id, i) => {
    $(id).classList.toggle("active", i + 1 === n); $(id).classList.toggle("done", i + 1 < n);
  });
}
function show(view) {
  ["start", "processing", "dashboard"].forEach(v => ($("#" + v).hidden = v !== view));
  $("#newBtn").hidden = view === "start";
}

// ---------------------------------------------------------------- theme
function initTheme() {
  const saved = localStorage.getItem("evp-theme");
  if (saved) document.documentElement.dataset.theme = saved;
  $("#themeBtn").onclick = () => {
    const t = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = t; localStorage.setItem("evp-theme", t);
  };
}

// ---------------------------------------------------------------- start view
async function initStart() {
  try {
    const h = await api("/api/health");
    $("#modelChip").textContent = "Model: " + h.ev_model.split("/").pop();
    const ms = $("#modelSel"); ms.innerHTML = "";
    Object.entries(h.models).forEach(([k, m]) => { if (!m.present) return; const o = document.createElement("option"); o.value = k; o.textContent = m.label; if (k === h.ev_model_key) o.selected = true; ms.appendChild(o); });
    const showHint = () => { const m = h.models[ms.value] || {}; const p = $("#modelHint"); if (p) { p.textContent = m.hint || ""; p.hidden = !m.hint; } };
    ms.onchange = () => { const m = h.models[ms.value]; $("#modelChip").textContent = "Model: " + m.file; showHint(); };
    showHint();
    if (!h.ffmpeg) toast("ffmpeg not found — run: pip install imageio-ffmpeg", 6000);
  } catch (e) { $("#modelChip").textContent = "Server not reachable"; }
  try { state.cfg = await api("/api/config"); } catch (e) { }
  const drop = $("#drop"), file = $("#file");
  drop.addEventListener("dragover", e => { e.preventDefault(); drop.classList.add("over"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("over"));
  drop.addEventListener("drop", e => { e.preventDefault(); drop.classList.remove("over"); if (e.dataTransfer.files[0]) upload(e.dataTransfer.files[0]); });
  drop.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); file.click(); } });
  file.addEventListener("change", () => file.files[0] && upload(file.files[0]));
  try {
    const s = await api("/api/samples");
    $("#samples").innerHTML = s.length ? "" : '<div class="muted">No sample clips found in demo_app/samples/.</div>';
    s.forEach(x => {
      const d = document.createElement("div"); d.className = "sample";
      d.innerHTML = `<b></b><button class="btn small">Run</button><span class="s-note"></span><span class="s-cred"></span>`;
      d.querySelector("b").textContent = x.title; d.querySelector(".s-note").textContent = x.note;
      d.querySelector(".s-cred").textContent = [x.credit, x.licence].filter(Boolean).join(" · ");
      d.querySelector("button").onclick = () => runSample(x.file, x.title);
      $("#samples").appendChild(d);
    });
  } catch (e) { $("#samples").innerHTML = '<div class="muted">Could not load samples.</div>'; }
  $("#newBtn").onclick = () => { stop(); clearProcessingVideo(); state.res = null; show("start"); setStep(1); history.replaceState(null, "", "/"); };
}
function clearProcessingVideo() {
  const v = $("#procVideo");
  v.pause(); v.removeAttribute("src"); v.load(); v.hidden = true;
  state.processingSample = false;
}
function startSettings() {
  return { approach: $("#approachSel").value, initial_state: $("#initSel").value, model: $("#modelSel").value };
}
async function upload(f) {
  clearProcessingVideo();
  $("#uploadErr").hidden = true;
  const ext = "." + (f.name.split(".").pop() || "").toLowerCase();
  if (state.cfg && !state.cfg.allowed_ext.includes(ext)) {
    $("#uploadErr").textContent = `“${f.name}” is not a supported video format (${ext}). Use MP4, AVI, MOV, MKV or WEBM.`;
    $("#uploadErr").hidden = false; return;
  }
  if (state.cfg && f.size > state.cfg.max_upload_mb * 1048576) {
    $("#uploadErr").textContent = `File is ${(f.size / 1048576).toFixed(0)} MB; the limit is ${state.cfg.max_upload_mb} MB.`;
    $("#uploadErr").hidden = false; return;
  }
  const fd = new FormData(); fd.append("video", f);
  const s = startSettings(); Object.entries(s).forEach(([k, v]) => fd.append(k, v));
  show("processing"); setStep(2); $("#procName").textContent = f.name; $("#procStage").textContent = "Uploading…";
  $("#procErr").hidden = true; $("#procPreview").hidden = true;
  try {
    const r = await api("/api/upload", { method: "POST", body: fd });
    poll(r.job.id);
  } catch (e) { failProc(e.message); }
}
async function runSample(file, title) {
  show("processing"); setStep(2); $("#procName").textContent = title; $("#procStage").textContent = "Starting…";
  $("#procErr").hidden = true; $("#procPreview").hidden = true;
  const video = $("#procVideo");
  state.processingSample = true;
  video.src = `/api/samples/${encodeURIComponent(file)}/video`;
  video.hidden = false; video.load();
  video.play().catch(() => { });
  try {
    const r = await api(`/api/samples/${encodeURIComponent(file)}/run`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(startSettings())
    });
    poll(r.job.id);
  } catch (e) { failProc(e.message); }
}
function failProc(msg) {
  $("#procErr").innerHTML = ""; const p = document.createElement("div");
  p.textContent = msg; $("#procErr").appendChild(p);
  const b = document.createElement("button"); b.className = "btn small"; b.style.marginTop = "8px"; b.textContent = "Try another video";
  b.onclick = () => { show("start"); setStep(1); }; $("#procErr").appendChild(b);
  $("#procErr").hidden = false; $("#procStage").textContent = "Stopped";
}
async function poll(id) {
  let j;
  try { j = await api(`/api/jobs/${id}`); } catch (e) { return failProc(e.message); }
  state.job = j;
  const pct = Math.round((j.progress || 0) * 100);
  $("#procPct").textContent = pct + "%"; $("#procBar").style.width = pct + "%"; $("#procStage").textContent = j.stage || "";
  if (j.live) {
    $("#pT").textContent = fmt(j.live.t) + " s"; $("#pV").textContent = j.live.vehicles;
    $("#pE").textContent = fmt(j.live.ev, 2); $("#pF").textContent = j.live.fps ? j.live.fps + " frames/s" : "–";
    const img = $("#procPreview"); img.hidden = false; img.src = `/api/jobs/${id}/preview.jpg?ts=${Date.now()}`;
    if (state.processingSample) {
      const video = $("#procVideo"); video.pause(); video.hidden = true;
    }
  }
  if (j.status === "error") return failProc(j.error || "Processing failed.");
  if (j.status === "done") return loadResult(id);
  setTimeout(() => poll(id), 600);
}

// ---------------------------------------------------------------- dashboard
async function loadResult(id, initialT = 0) {
  let res;
  try { res = await api(`/api/jobs/${id}/result`); } catch (e) { return failProc(e.message); }
  clearProcessingVideo();
  state.res = res; state.jobId = id; state.inject = [];
  history.replaceState(null, "", `/?job=${id}` + (initialT ? `&t=${initialT}` : ""));
  show("dashboard"); setStep(3);
  const v = $("#video"); v.src = `/api/jobs/${id}/video`; v.load();
  v.playbackRate = state.speed;
  state.vidDur = res.analysis.duration;
  $("#csvBtn").href = `/api/jobs/${id}/report.csv`;
  applyResult(true);
  state.t = initialT; seek(initialT);
}
function applyResult(first) {
  const r = state.res, a = r.analysis;
  state.simDur = r.sim.duration;
  state.frameTimes = a.per_frame.map(f => f.t);
  $("#tEnd").textContent = fmt(state.simDur, 0);
  $("#endT").textContent = fmt(state.vidDur, 1) + " s";
  const p = a.perf || {};
  $("#modelChip").textContent = "Model: " + (p.ev_model_file || "?");
  $("#videoFoot").textContent = `${p.ev_model_file || ""} · ${a.video_info.width}×${a.video_info.height} · ${fmt(a.duration)} s · ${p.frames_analysed} frames analysed at ` +
    `${fmt(p.analysed_fps)} frames/s on this computer (EV model ${fmt(p.ev_ms_median)} ms, COCO model ${fmt(p.coco_ms_median)} ms per frame)`;
  const notes = r.notes || [];
  $("#notesBanner").hidden = !notes.length;
  $("#notesBanner").innerHTML = notes.length ? "<b>Notes for this video</b><ul>" + notes.map(n => `<li>${esc(n)}</li>`).join("") + "</ul>" : "";
  if (first) initSettings();
  renderCounts(); buildLog(); renderResult(); drawTimeline();
}
function esc(s) { return String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]); }
function sim() { return state.res.sim[state.mode]; }

// ---- counts (real)
function renderCounts() {
  const a = state.res.analysis, c = a.counts;
  const order = ["car", "motorcycle", "bus", "truck", "ambulance", "fire brigade", "police"];
  const max = Math.max(1, ...Object.values(c));
  const box = $("#countsList"); box.innerHTML = "";
  order.filter(k => c[k] || ["car", "motorcycle", "bus", "truck"].includes(k)).forEach(k => {
    const ev = ["ambulance", "fire brigade", "police"].includes(k);
    const d = document.createElement("div"); d.className = "cnt" + (ev ? " ev" : "");
    d.innerHTML = `<span>${k}</span><span class="cbar"><i style="width:${(100 * (c[k] || 0) / max).toFixed(0)}%"></i></span><b>${c[k] || 0}</b>`;
    box.appendChild(d);
  });
  const sus = a.ev_suspected.length;
  $("#countsFoot").innerHTML = `Unique vehicles over the clip (tracked, seen in ≥3 frames). In frame now: <b id="inFrame">0</b>` +
    (sus ? ` · ${sus} suspected EV not confirmed` : "");
}

// ---- event log: detection (real) + signal (simulated)
function buildLog() {
  const a = state.res.analysis, cp = a.confirm_params, rows = [];
  const va = state.res.sim.params.sim.video_approach;
  a.ev_tracks.forEach(e => {
    rows.push({ t: e.first_t, c: "#f59e0b", src: "DETECTION", text: `${e.cls} first detected (track ${e.tid})` });
    if (e.confirmed_t !== null) rows.push({
      t: e.confirmed_t, c: "#ef4444", src: "DETECTION",
      text: `${e.cls} CONFIRMED · conf ${fmt(e.confirmed_conf, 2)} · ${cp.confirm_frames} consecutive frames ≥ ${cp.confirm_conf} → ${NAMES[va]} preemption request` +
        (e.final_cls && e.final_cls !== e.cls ? ` (later frames mostly say ${e.final_cls})` : "")
    });
    else if (e.suspected_t !== null) rows.push({
      t: e.suspected_t, c: "#f59e0b", src: "DETECTION",
      text: `${e.cls} SUSPECTED (max conf ${fmt(e.max_conf, 2)}) — not confirmed, no preemption`
    });
  });
  rows.push({ t: state.vidDur, c: "#93a0bb", src: "VIDEO", text: "Video ends — simulation continues with the detected arrivals" });
  const kindCol = { preempt_start: "#f5b301", preempt_green: "#22c55e", ev_stopline: "#ef4444", ev_cleared: "#22c55e", recovery: "#4f8cff", normal: "#4f8cff", ev_no_preempt: "#93a0bb", ev_queued: "#f59e0b", ev_request: "#ef4444", preempt_timeout: "#f59e0b" };
  sim().events.forEach(e => rows.push({ t: e.t, c: kindCol[e.kind] || "#93a0bb", src: "SIM", text: e.text }));
  rows.sort((x, y) => x.t - y.t);
  state.logRows = rows;
  const log = $("#log"); log.innerHTML = "";
  rows.forEach((r, i) => {
    const d = document.createElement("div"); d.className = "ev-row";
    d.innerHTML = `<span class="tt">t=${fmt(r.t)}s</span><span class="dot" style="background:${r.c}"></span><span></span>`;
    d.lastChild.textContent = r.text;
    const s = document.createElement("span"); s.className = "src"; s.textContent = r.src; d.lastChild.appendChild(s);
    d.onclick = () => { seek(Math.max(0, r.t - 0.5)); };
    r.el = d; log.appendChild(d);
  });
}
function updateLog(t) {
  let last = -1;
  state.logRows.forEach((r, i) => { const p = r.t <= t + 0.05; r.el.classList.toggle("past", p); if (p) last = i; });
  state.logRows.forEach((r, i) => r.el.classList.toggle("now", i === last));
  if (last !== state._lastLog) {
    state._lastLog = last;
    const el = state.logRows[last] && state.logRows[last].el;
    if (el) { const box = $("#log"); box.scrollTop = Math.max(0, el.offsetTop - box.offsetTop - 120); }
  }
}

// ---- results (simulated)
function renderResult() {
  const s = state.res.sim, comp = s.comparison;
  const box = $("#resultBox");
  const pm = s.preemption.metrics, fm = s.fixed.metrics;
  if (!comp.length) {
    box.innerHTML = `<div class="muted small" style="margin-bottom:8px">No emergency vehicle was confirmed, so the signal stayed on its normal cycle.</div>` +
      `<div class="res-row"><span>Mean delay, all vehicles</span><b>${fmt(pm.mean_delay_s)} s</b></div>` +
      `<div class="res-row"><span>Vehicles through</span><b>${pm.vehicles_completed}</b></div>` +
      `<div class="muted small">Tip: add a test EV in Scenario controls to see preemption.</div>`;
    return;
  }
  const c = comp[0];
  const mx = Math.max(1, c.delay_preempt_s || 0, c.delay_fixed_s || 0);
  const bar = (lab, v, col, note) => `<div class="b2"><span>${lab}</span><span class="t"><i style="width:${(100 * (v || 0) / mx).toFixed(0)}%;background:${col}"></i></span><b>${v === null ? "n/a" : fmt(v) + "s"}</b></div>` + (note || "");
  const saved = (c.delay_fixed_s !== null && c.delay_preempt_s !== null) ? c.delay_fixed_s - c.delay_preempt_s : null;
  box.innerHTML =
    `<div class="res-row"><span>Detection → green<br><span class="muted small">confirmation to ${NAMES[c.approach]} green</span></span><span class="big">${c.response_s === null ? "–" : fmt(c.response_s) + "s"}</span></div>` +
    `<div class="muted small" style="margin-top:6px">${esc(c.cls)} delay at the junction</div>` +
    `<div class="bars2">${bar("Preemption", c.delay_preempt_s, "#22c55e")}${bar("Fixed-time", c.delay_fixed_s, "#ef4444", c.cleared_fixed ? "" : '<div class="muted small">not cleared within the simulated window</div>')}</div>` +
    (saved !== null ? `<div class="res-row"><span>EV time saved</span><b>${fmt(saved)} s</b></div>` : "") +
    `<div class="res-row"><span>Other vehicles, mean delay</span><b>${fmt(pm.mean_delay_s)} / ${fmt(fm.mean_delay_s)} s</b></div>` +
    `<div class="muted small">preemption / fixed-time · ${comp.length > 1 ? comp.length + " EVs in this run · " : ""}simulated, not measured on a real junction</div>`;
}

// ---- settings
function initSettings() {
  const sp = state.res.sim.params.sim, sg = state.res.sim.params.signal, cp = state.res.analysis.confirm_params;
  $("#sApproach").value = sp.video_approach; $("#sInit").value = sg.initial_state.startsWith("video") ? sg.initial_state : "video_red";
  const obs = state.res.sim.rate_used_vpm;
  const rows = $("#densRows"); rows.innerHTML = '<div class="muted small" style="margin-top:8px">Other approaches (vehicles per minute; observed on video: ' + fmt(state.res.sim.observed_rate_vpm) + ')</div>';
  APP.forEach(a => {
    const d = document.createElement("div"); d.className = "dens"; d.dataset.a = a;
    const val = sp.densities[a] === undefined || sp.densities[a] === null ? obs : sp.densities[a];
    d.innerHTML = `<span>${NAMES[a]}</span><input type="range" min="0" max="40" step="1" value="${Math.round(val)}"><span class="v"></span>`;
    const inp = d.querySelector("input"), v = d.querySelector(".v");
    const upd = () => (v.textContent = inp.value + " /min"); inp.oninput = upd; upd();
    rows.appendChild(d);
  });
  syncDensRows();
  $("#sApproach").onchange = syncDensRows;
  const sl = (id, out, val, dec) => { const r = $(id); r.value = val; const u = () => ($(out).textContent = dec ? Number(r.value).toFixed(2) : r.value); r.oninput = u; u(); };
  sl("#rSus", "#vSus", cp.suspect_conf, true); sl("#rConf", "#vConf", cp.confirm_conf, true); sl("#rFr", "#vFr", cp.confirm_frames, false);
  const ib = $("#injBtns"); ib.innerHTML = "";
  APP.forEach(a => {
    const b = document.createElement("button"); b.className = "btn small"; b.textContent = "+ EV on " + NAMES[a];
    b.onclick = () => { state.inject.push({ approach: a, t: Math.round(state.t * 10) / 10, cls: "ambulance" }); showInj(); toast(`Test ambulance on ${NAMES[a]} at t=${fmt(state.t)} s — press Re-run`); };
    ib.appendChild(b);
  });
  showInj();
  $("#rerunBtn").onclick = rerun;
}
function syncDensRows() {
  const va = $("#sApproach").value;
  $$(".dens").forEach(d => (d.hidden = d.dataset.a === va));
}
function showInj() {
  $("#injList").textContent = state.inject.length ? "Pending test EVs: " + state.inject.map(i => `${NAMES[i.approach]} @ ${fmt(i.t)}s`).join(", ") : "";
}
async function rerun() {
  const btn = $("#rerunBtn"); btn.disabled = true; $("#rerunMsg").textContent = "Simulating…";
  const dens = {}; $$(".dens").forEach(d => { if (!d.hidden) dens[d.dataset.a] = Number(d.querySelector("input").value); });
  const body = {
    approach: $("#sApproach").value, initial_state: $("#sInit").value, densities: dens, inject: state.inject,
    confirm: { suspect_conf: Number($("#rSus").value), confirm_conf: Number($("#rConf").value), confirm_frames: Number($("#rFr").value) }
  };
  try {
    const r = await api(`/api/jobs/${state.jobId}/simulate`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    state.res = r; applyResult(false); seek(Math.min(state.t, state.simDur));
    $("#rerunMsg").textContent = "Updated ✓";
  } catch (e) { $("#rerunMsg").textContent = e.message; }
  btn.disabled = false; setTimeout(() => ($("#rerunMsg").textContent = ""), 2500);
}

// ---------------------------------------------------------------- playback clock
function play() {
  if (state.t >= state.simDur - 0.05) seek(0);
  state.playing = true; state.lastTs = null; $("#playBtn").textContent = "❚❚ Pause";
  const v = $("#video");
  if (state.t < state.vidDur - 0.03) { v.playbackRate = state.speed; v.play().catch(() => { }); }
}
function stop() {
  state.playing = false; $("#playBtn").textContent = "▶ Play"; $("#video").pause();
}
function seek(t) {
  if (!state.res) return;
  state.t = Math.max(0, Math.min(t, state.simDur || 0));
  const v = $("#video");
  if (state.t < state.vidDur) { try { v.currentTime = state.t; } catch (e) { } if (state.playing) v.play().catch(() => { }); }
  else { v.pause(); try { v.currentTime = Math.max(0, state.vidDur - 0.05); } catch (e) { } }
  state.lastTs = null; renderAll();
}
function tick(ts) {
  if (state.res && state.playing) {
    const v = $("#video");
    if (state.t < state.vidDur - 0.03 && !v.paused && !v.ended && v.readyState >= 2) {
      state.t = v.currentTime; // video is the master clock while it plays
    } else if (state.lastTs !== null) {
      state.t += (ts - state.lastTs) / 1000 * state.speed;
    }
    state.lastTs = ts;
    if (state.t >= state.simDur) { state.t = state.simDur; stop(); }
  }
  if (state.res) renderAll();
  requestAnimationFrame(tick);
}
function renderAll() {
  const t = state.t;
  $("#tNow").textContent = fmt(t);
  $("#endedMask").hidden = t < state.vidDur - 0.02;
  drawOverlay(t); drawSim(t); drawTimelineHead(t); updateGauge(t); updateLoad(t); updateLog(t); updatePhase(t);
}

// ---------------------------------------------------------------- video overlay (real detections)
function drawOverlay(t) {
  const c = $("#overlay"), [ctx, W, H] = fitCanvas(c), a = state.res.analysis;
  ctx.clearRect(0, 0, W, H);
  if (t > state.vidDur + 0.05) return;
  const i = bsearch(state.frameTimes, t + 0.02);
  if (i < 0) return;
  const fw = a.video_info.width, fh = a.video_info.height, sc = Math.min(W / fw, H / fh);
  const ox = (W - fw * sc) / 2, oy = (H - fh * sc) / 2;
  const X = x => ox + x * sc, Y = y => oy + y * sc;
  const pf = a.per_frame[i];
  const inF = $("#inFrame"); if (inF) inF.textContent = pf.n;
  ctx.lineWidth = 1.5; ctx.font = "600 11px " + cssVar("--font");
  if (state.overlay === "all") {
    a.boxes[i].forEach(([x1, y1, x2, y2, tid, cls, counted]) => {
      ctx.strokeStyle = counted ? "rgba(122,162,255,.95)" : "rgba(122,162,255,.45)";
      ctx.strokeRect(X(x1), Y(y1), (x2 - x1) * sc, (y2 - y1) * sc);
      const lab = `${cls} #${tid}`; const tw = ctx.measureText(lab).width + 8;
      ctx.fillStyle = "rgba(15,22,41,.78)"; ctx.fillRect(X(x1), Y(y1) - 15, tw, 15);
      ctx.fillStyle = "#cfe0ff"; ctx.fillText(lab, X(x1) + 4, Y(y1) - 4);
    });
  }
  if (state.overlay !== "none") {
    a.ev_per_frame[i].forEach(e => {
      const [x1, y1, x2, y2] = e.box, conf = e.state === "CONFIRMED", sus = e.state === "SUSPECTED";
      const col = conf ? "#ef4444" : sus ? "#f59e0b" : "rgba(245,158,11,.6)";
      ctx.save(); ctx.lineWidth = conf ? 3.5 : 2.5; ctx.strokeStyle = col;
      if (!conf) ctx.setLineDash([7, 5]);
      ctx.strokeRect(X(x1), Y(y1), (x2 - x1) * sc, (y2 - y1) * sc); ctx.restore();
      ctx.font = "700 12px " + cssVar("--font");
      const lab = `${e.cls.toUpperCase()} ${e.conf.toFixed(2)} · ${e.state === "CANDIDATE" ? "LOW CONF" : e.state}`;
      const tw = ctx.measureText(lab).width + 10;
      ctx.fillStyle = col; ctx.fillRect(X(x1), Y(y2), tw, 18);
      ctx.fillStyle = "#fff"; ctx.fillText(lab, X(x1) + 5, Y(y2) + 13);
    });
  }
  if (pf.ev_state === "CONFIRMED" || pf.ev_state === "SUSPECTED") {
    const conf = pf.ev_state === "CONFIRMED";
    const narrow = W < 560;
    const msg = conf ? (narrow ? `🚨 EV CONFIRMED · ${pf.ev_cls}` : `🚨 EMERGENCY VEHICLE CONFIRMED · ${pf.ev_cls}`) : `? possible ${pf.ev_cls} · not confirmed`;
    ctx.font = "800 12px " + cssVar("--font"); const w = ctx.measureText(msg).width + 20;
    const by = narrow ? 38 : 8;
    ctx.fillStyle = conf ? "rgba(220,38,38,.92)" : "rgba(217,119,6,.9)"; roundRect(ctx, W - w - 10, by, w, 24, 8); ctx.fill();
    ctx.fillStyle = "#fff"; ctx.fillText(msg, W - w, by + 17);
  }
  // HUD
  ctx.font = "700 12px " + cssVar("--mono");
  const hud = `t = ${t.toFixed(1)} s   vehicles in frame: ${pf.n}`;
  ctx.fillStyle = "rgba(5,8,16,.7)"; ctx.fillRect(8, 8, ctx.measureText(hud).width + 16, 24);
  ctx.fillStyle = "#fff"; ctx.fillText(hud, 16, 25);
}

// ---------------------------------------------------------------- intersection simulation (canvas)
function signalAt(t) {
  const h = sim().signals; const i = bsearch(h, t, x => x[0]);
  const row = h[Math.max(0, i)]; return { s: row[1], mode: row[2], idx: Math.max(0, i) };
}
function nextChange(t, a) {
  const h = sim().signals, k = APP.indexOf(a); const cur = signalAt(t).s[k];
  for (const row of h) if (row[0] > t && row[1][k] !== cur) return row[0] - t;
  return null;
}
function drawSim(t) {
  const c = $("#sim"), [ctx, W, H] = fitCanvas(c), S = sim(), P = state.res.sim.params.sim;
  const L = S.L, BOX = S.box, LW = S.lane_w, half = BOX / 2, road = 2 * 2 * LW; // 4 lanes total width 14 m
  const view = 58;                          // metres from centre to the nearest canvas edge
  const sc = Math.min(W, H) / (2 * view);
  const cx = W / 2, cy = H / 2;
  const light = document.documentElement.dataset.theme === "light";
  ctx.fillStyle = cssVar("--grass"); ctx.fillRect(0, 0, W, H);
  // pavement blocks
  ctx.fillStyle = light ? "#dfe6dc" : "#1d2b23";
  const rw = (road / 2 + 1.5) * sc;
  [[0, 0], [1, 0], [0, 1], [1, 1]].forEach(([i, j]) => {
    const x0 = i ? cx + rw : -20, y0 = j ? cy + rw : -20, x1 = i ? W + 20 : cx - rw, y1 = j ? H + 20 : cy - rw;
    roundRect(ctx, x0, y0, x1 - x0, y1 - y0, 4 * sc); ctx.fill();
  });
  // roads
  ctx.fillStyle = cssVar("--road");
  ctx.fillRect(cx - road / 2 * sc, 0, road * sc, H); ctx.fillRect(0, cy - road / 2 * sc, W, road * sc);
  ctx.fillStyle = cssVar("--road2"); ctx.fillRect(cx - road / 2 * sc, cy - road / 2 * sc, road * sc, road * sc);
  const dash = (x1, y1, x2, y2, d) => { ctx.setLineDash(d || []); ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke(); ctx.setLineDash([]); };
  // centre lines (double yellow) and lane dividers
  ctx.lineWidth = Math.max(1, 0.15 * sc); ctx.strokeStyle = "#e9c46a";
  const g = 0.18 * sc, e1 = cy - half * sc, e2 = cy + half * sc, f1 = cx - half * sc, f2 = cx + half * sc;
  [[-g], [g]].forEach(([o]) => {
    dash(cx + o, 0, cx + o, e1); dash(cx + o, e2, cx + o, H); dash(0, cy + o, f1, cy + o); dash(f2, cy + o, W, cy + o);
  });
  ctx.strokeStyle = cssVar("--mark");
  [-LW, LW].forEach(o => {
    const d = [3 * sc, 3 * sc];
    dash(cx + o * sc, 0, cx + o * sc, e1, d); dash(cx + o * sc, e2, cx + o * sc, H, d);
    dash(0, cy + o * sc, f1, cy + o * sc, d); dash(f2, cy + o * sc, W, cy + o * sc, d);
  });
  // crosswalks (zebra) just outside the conflict box
  ctx.fillStyle = light ? "rgba(255,255,255,.9)" : "rgba(230,234,243,.5)";
  for (let k = -road / 2 + 0.5; k < road / 2 - 0.3; k += 1.4) {
    const w = 0.7 * sc, len = 3 * sc, off = (half - 3.4) * sc;
    ctx.fillRect(cx + k * sc, cy - off - len, w, len); ctx.fillRect(cx + k * sc, cy + off, w, len);
    ctx.fillRect(cx - off - len, cy + k * sc, len, w); ctx.fillRect(cx + off, cy + k * sc, len, w);
  }
  const sig = signalAt(t);
  const lhs = P.drive_side !== "right";
  const leftOf = a => { const [dx, dy] = DIR[a]; return lhs ? [dy, -dx] : [-dy, dx]; };
  // stop lines in signal colour
  APP.forEach((a, k) => {
    const st = sig.s[k], [dx, dy] = DIR[a], [lx, ly] = leftOf(a);
    const px = cx + (-dx * half) * sc, py = cy + (-dy * half) * sc;
    ctx.strokeStyle = COL[st]; ctx.lineWidth = Math.max(3, 0.6 * sc); ctx.setLineDash([]);
    if (st !== "R") { ctx.shadowColor = COL[st]; ctx.shadowBlur = 10; }
    ctx.beginPath(); ctx.moveTo(px + lx * 0.3 * sc, py + ly * 0.3 * sc); ctx.lineTo(px + lx * (2 * LW) * sc, py + ly * (2 * LW) * sc); ctx.stroke();
    ctx.shadowBlur = 0;
  });
  // approach names at the road ends + camera marker on the video approach
  APP.forEach(a => {
    const [dx, dy] = DIR[a], [lx, ly] = leftOf(a);
    const ex = cx - dx * (Math.abs(dx) ? W / 2 - 16 : 0), ey = cy - dy * (Math.abs(dy) ? H / 2 - 14 : 0);
    ctx.font = "800 11px " + cssVar("--font"); ctx.textAlign = "center"; ctx.textBaseline = "middle";
    const isV = a === P.video_approach, lab = NAMES[a].toUpperCase() + (isV ? (W < 560 ? " ◉ camera" : "  ◉ camera (" + P.camera_distance_m + " m upstream)") : "");
    const tw = ctx.measureText(lab).width + 14;
    const lo = (road / 2 + 2) * sc + (Math.abs(lx) ? tw / 2 : 12);
    const px = ex + lx * lo, py = ey + ly * lo;
    ctx.fillStyle = isV ? "rgba(45,212,191,.18)" : "rgba(5,8,16,.55)"; roundRect(ctx, px - tw / 2, py - 10, tw, 20, 6); ctx.fill();
    if (isV) { ctx.strokeStyle = "#2dd4bf"; ctx.lineWidth = 1; ctx.stroke(); }
    ctx.fillStyle = isV ? "#2dd4bf" : "rgba(255,255,255,.8)"; ctx.fillText(lab, px, py + 0.5);
    ctx.textAlign = "left"; ctx.textBaseline = "alphabetic";
  });
  // vehicles
  const flash = Math.floor(t * 4) % 2 === 0;
  const evNow = [];
  S.trajectories.forEach(v => { if (!v.ev) return; const k = Math.round((t - v.t0) / S.dt); if (k >= 0 && k < v.s.length) evNow.push({ a: v.a, s: v.s[k] }); });
  S.trajectories.forEach(v => {
    const k = Math.round((t - v.t0) / S.dt);
    if (k < 0 || k >= v.s.length) return;
    const s = v.s[k], sPrev = v.s[Math.max(0, k - 3)];
    const speed = (s - sPrev) / (Math.max(1, Math.min(3, k)) * S.dt);
    const u = s - L - half; // front, relative to centre along travel axis
    if (Math.abs(u) > Math.max(W, H) / (2 * sc) + 14) return;
    const [dx, dy] = DIR[v.a], [lx, ly] = leftOf(v.a);
    let lat = v.lane === 0 ? LW * 1.5 : LW * 0.5;
    if (P.rescue_lane) {
      if (v.ev) {               // EV drives along the lane divider while it passes queued traffic
        const f = s < L ? 1 : Math.max(0, 1 - (s - L) / 10);
        lat = lat + (LW - lat) * f;
      } else if (s < L) {       // ordinary vehicles pull aside when an EV comes up behind them
        let push = 0;
        evNow.forEach(e => { if (e.a === v.a) { const d = s - e.s; if (d > -9 && d < 28) push = Math.max(push, d < 0 ? 1 : 1 - d / 28); } });
        lat += (v.lane === 0 ? 1.1 : -1.2) * push;
      }
    }
    const len = { car: 4.5, motorcycle: 2.2, bus: 11, truck: 9, ambulance: 6, "fire brigade": 9, police: 4.8 }[v.type] || 4.5;
    const wid = { motorcycle: 0.9, bus: 2.5, truck: 2.5, "fire brigade": 2.5 }[v.type] || 1.9;
    const mx = cx + (dx * (u - len / 2) + lx * lat) * sc, my = cy + (dy * (u - len / 2) + ly * lat) * sc;
    ctx.save(); ctx.translate(mx, my); ctx.rotate(Math.atan2(dy, dx));
    const Lp = len * sc, Wp = wid * sc;
    let body = carColor(v);
    if (v.ev) {
      ctx.shadowColor = flash ? "#ef4444" : "#3b82f6"; ctx.shadowBlur = 16;
      body = v.type === "fire brigade" ? "#dc2626" : v.type === "police" ? "#e5e7eb" : "#f8fafc";
    }
    ctx.fillStyle = body; roundRect(ctx, -Lp / 2, -Wp / 2, Lp, Wp, Math.min(3, Wp / 3)); ctx.fill(); ctx.shadowBlur = 0;
    if (v.ev) {
      ctx.fillStyle = "#ef4444"; ctx.fillRect(-Lp * 0.05, -Wp / 2, Lp * 0.12, Wp);           // red stripe
      ctx.fillStyle = flash ? "#ef4444" : "#3b82f6"; ctx.fillRect(Lp * 0.12, -Wp / 2 + 1, Lp * 0.08, Wp / 2 - 1);
      ctx.fillStyle = flash ? "#3b82f6" : "#ef4444"; ctx.fillRect(Lp * 0.12, 0, Lp * 0.08, Wp / 2 - 1);
    } else {
      ctx.fillStyle = "rgba(10,15,25,.55)"; ctx.fillRect(Lp * 0.12, -Wp / 2 + 1, Lp * 0.2, Wp - 2); // windscreen
    }
    if (v.sus) { ctx.strokeStyle = "#f59e0b"; ctx.lineWidth = 2; ctx.setLineDash([4, 3]); ctx.strokeRect(-Lp / 2 - 2, -Wp / 2 - 2, Lp + 4, Wp + 4); ctx.setLineDash([]); }
    if (speed < 1.0 && s < L) { ctx.fillStyle = "#ff3b3b"; ctx.fillRect(-Lp / 2 - 1, -Wp / 2 + 0.5, 2, Wp * 0.3); ctx.fillRect(-Lp / 2 - 1, Wp / 2 - 0.5 - Wp * 0.3, 2, Wp * 0.3); }
    if (v.src === "video") { ctx.fillStyle = "#ffffff"; ctx.beginPath(); ctx.arc(-Lp * 0.15, 0, Math.max(1.6, Wp * 0.18), 0, 7); ctx.fill(); }
    ctx.restore();
    if (v.ev) {
      ctx.font = "800 11px " + cssVar("--font"); ctx.fillStyle = "#fff"; ctx.strokeStyle = "rgba(0,0,0,.65)"; ctx.lineWidth = 3;
      const lab = v.type.toUpperCase(); ctx.strokeText(lab, mx + 12, my - 10); ctx.fillText(lab, mx + 12, my - 10);
    }
  });
  // signal heads at the near-left corner of each approach
  APP.forEach((a, k) => {
    const st = sig.s[k], [dx, dy] = DIR[a], [lx, ly] = leftOf(a);
    const off = road / 2 + 4.2, back = half + 4.2;
    const px = cx + (-dx * back + lx * off) * sc, py = cy + (-dy * back + ly * off) * sc;
    drawHead(ctx, px, py, st, a, nextChange(t, a), a === P.video_approach);
  });
  // banner
  const mode = sig.mode;
  const txt = state.mode === "fixed" ? "FIXED-TIME CONTROL (no preemption)" :
    mode === "PREEMPT_CLEAR" ? "PREEMPTION · clearing conflicting traffic" : mode === "PREEMPT_GREEN" ? "PREEMPTION · emergency vehicle has green" :
      mode === "RECOVERY" ? "RECOVERY · returning to normal cycle" : "NORMAL CYCLE";
  const bc = state.mode === "fixed" ? "rgba(147,160,187,.9)" : mode === "PREEMPT_GREEN" ? "#ef4444" : mode === "PREEMPT_CLEAR" ? "#f5b301" : mode === "RECOVERY" ? "#4f8cff" : "rgba(34,197,94,.9)";
  ctx.font = "800 12px " + cssVar("--font"); const tw = ctx.measureText(txt).width + 22;
  ctx.fillStyle = "rgba(5,8,16,.78)"; roundRect(ctx, 10, 10, tw, 26, 8); ctx.fill();
  ctx.fillStyle = bc; ctx.beginPath(); ctx.arc(21, 23, 4, 0, 7); ctx.fill();
  ctx.fillStyle = "#fff"; ctx.fillText(txt, 30, 27);
  ctx.font = "700 10px " + cssVar("--mono"); ctx.fillStyle = "rgba(255,255,255,.7)"; ctx.textAlign = "right";
  ctx.fillText(`SIMULATED · t = ${t.toFixed(1)} s`, W - 12, H - 10); ctx.textAlign = "left";
  // alert when the video has just confirmed an emergency vehicle
  const va = P.video_approach;
  state.res.analysis.ev_confirmed.forEach(e => {
    if (t >= e.confirmed_t && t < e.confirmed_t + 4.5) {
      const msg = W < 560 ? `${e.cls.toUpperCase()} CONFIRMED ${e.confirmed_t.toFixed(1)} s → ` + (state.mode === "fixed" ? "no preemption" : `preempt ${va}`)
        : `${e.cls.toUpperCase()} CONFIRMED IN VIDEO at ${e.confirmed_t.toFixed(1)} s (conf ${e.confirmed_conf.toFixed(2)}) → ` +
        (state.mode === "fixed" ? "fixed-time: no preemption" : `preempting ${NAMES[va].toUpperCase()}`);
      ctx.font = "800 12px " + cssVar("--font"); const w = ctx.measureText(msg).width + 26;
      const a = 0.75 + 0.25 * Math.sin(t * 10);
      ctx.fillStyle = `rgba(220,38,38,${a})`; roundRect(ctx, W / 2 - w / 2, H - 46, w, 28, 9); ctx.fill();
      ctx.fillStyle = "#fff"; ctx.textAlign = "center"; ctx.fillText(msg, W / 2, H - 28); ctx.textAlign = "left";
    }
  });
}
function carColor(v) {
  const pal = ["#7aa2ff", "#93c5fd", "#a5b4fc", "#c4b5fd", "#67e8f9", "#fca5a5", "#fdba74", "#bef264", "#e5e7eb", "#94a3b8"];
  if (v.type === "bus") return "#f59e0b"; if (v.type === "truck") return "#64748b"; if (v.type === "motorcycle") return "#f472b6";
  return pal[v.id % pal.length];
}
function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
}
function drawHead(ctx, x, y, st, a, rem, isVideo) {
  const w = 18, h = 46;
  ctx.fillStyle = "#0b0f19"; ctx.strokeStyle = isVideo ? "#2dd4bf" : "#46526e"; ctx.lineWidth = isVideo ? 2 : 1;
  roundRect(ctx, x - w / 2, y - h / 2, w, h, 5); ctx.fill(); ctx.stroke();
  [["R", -14], ["Y", 0], ["G", 14]].forEach(([c, oy]) => {
    const on = st === c;
    ctx.beginPath(); ctx.arc(x, y + oy, 5.6, 0, 7);
    ctx.fillStyle = on ? COL[c] : "rgba(255,255,255,.08)";
    if (on) { ctx.shadowColor = COL[c]; ctx.shadowBlur = 14; }
    ctx.fill(); ctx.shadowBlur = 0;
  });
  ctx.textAlign = "center"; ctx.textBaseline = "middle";
  ctx.fillStyle = "rgba(5,8,16,.78)"; roundRect(ctx, x - 22, y + h / 2 + 3, 44, 17, 5); ctx.fill();
  ctx.font = "800 10px " + cssVar("--mono"); ctx.fillStyle = COL[st];
  ctx.fillText(a + " " + (rem === null ? "—" : Math.ceil(rem) + "s"), x, y + h / 2 + 12);
  ctx.textAlign = "left"; ctx.textBaseline = "alphabetic";
}

// ---------------------------------------------------------------- timeline
function drawTimeline() { state._tlCache = null; drawTimelineHead(state.t); }
function drawTimelineHead(t) {
  const c = $("#timeline"), [ctx, W, H] = fitCanvas(c), S = sim(), a = state.res.analysis, cp = a.confirm_params;
  const padL = 58, padR = 14, top = 8, rowH = 16, gap = 4;
  const X = tt => padL + (W - padL - padR) * tt / state.simDur;
  ctx.clearRect(0, 0, W, H);
  ctx.font = "600 11px " + cssVar("--font"); ctx.textBaseline = "middle";
  // video region
  ctx.fillStyle = "rgba(45,212,191,.08)"; ctx.fillRect(X(0), 0, X(state.vidDur) - X(0), H - 16);
  ctx.fillStyle = cssVar("--muted"); ctx.fillText("video", X(0) + 4, H - 22);
  // signal rows
  APP.forEach((ap, k) => {
    const y = top + k * (rowH + gap);
    ctx.fillStyle = cssVar("--muted"); ctx.fillText(NAMES[ap], 6, y + rowH / 2);
    const h = S.signals;
    for (let i = 0; i < h.length; i++) {
      const t0 = h[i][0], t1 = i + 1 < h.length ? h[i + 1][0] : state.simDur;
      ctx.fillStyle = COL[h[i][1][k]]; ctx.globalAlpha = 0.85;
      ctx.fillRect(X(t0), y, Math.max(1, X(t1) - X(t0)), rowH);
    }
    ctx.globalAlpha = 1;
  });
  // preemption bands
  const yC = top + 4 * (rowH + gap) + 6, hC = H - yC - 24;
  // EV confidence chart
  ctx.fillStyle = cssVar("--muted"); ctx.fillText("EV conf", 6, yC + hC / 2);
  ctx.strokeStyle = cssVar("--line"); ctx.strokeRect(X(0), yC, X(state.simDur) - X(0), hC);
  const Yc = v => yC + hC - v * hC;
  [[cp.suspect_conf, "#f59e0b"], [cp.confirm_conf, "#ef4444"]].forEach(([v, col]) => {
    ctx.strokeStyle = col; ctx.setLineDash([4, 4]); ctx.globalAlpha = .7; ctx.beginPath(); ctx.moveTo(X(0), Yc(v)); ctx.lineTo(X(state.simDur), Yc(v)); ctx.stroke(); ctx.setLineDash([]); ctx.globalAlpha = 1;
    ctx.fillStyle = col; ctx.fillText(v.toFixed(2), X(state.simDur) - 30, Yc(v) - 6);
  });
  // vehicle count area (scaled)
  const maxN = Math.max(1, ...a.per_frame.map(f => f.n));
  ctx.fillStyle = "rgba(122,162,255,.14)"; ctx.beginPath(); ctx.moveTo(X(0), Yc(0));
  a.per_frame.forEach(f => ctx.lineTo(X(f.t), Yc(0.9 * f.n / maxN))); ctx.lineTo(X(a.per_frame[a.per_frame.length - 1].t), Yc(0)); ctx.closePath(); ctx.fill();
  ctx.strokeStyle = "#4f8cff"; ctx.lineWidth = 2; ctx.beginPath();
  a.per_frame.forEach((f, i) => { const x = X(f.t), y = Yc(f.ev); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); }); ctx.stroke();
  // markers
  const marks = [];
  a.ev_tracks.forEach(e => { if (e.confirmed_t !== null) marks.push([e.confirmed_t, "#ef4444", "confirmed"]); });
  S.events.forEach(e => { if (e.kind === "preempt_green") marks.push([e.t, "#22c55e", "EV green"]); if (e.kind === "ev_cleared") marks.push([e.t, "#2dd4bf", "EV cleared"]); if (e.kind === "normal") marks.push([e.t, "#4f8cff", "normal"]); });
  marks.forEach(([tt, col, lab], i) => {
    ctx.strokeStyle = col; ctx.lineWidth = 1.5; ctx.beginPath(); ctx.moveTo(X(tt), top); ctx.lineTo(X(tt), yC + hC); ctx.stroke();
    ctx.fillStyle = col; ctx.font = "700 10px " + cssVar("--font"); ctx.fillText(lab, X(tt) + 3, yC + 9 + (i % 3) * 11);
  });
  // axis
  ctx.fillStyle = cssVar("--muted"); ctx.font = "500 10px " + cssVar("--mono");
  const stepT = state.simDur > 120 ? 20 : state.simDur > 50 ? 10 : 5;
  for (let s = 0; s <= state.simDur + 0.01; s += stepT) { ctx.fillText(s + "s", X(s) - 8, H - 7); }
  // playhead
  ctx.strokeStyle = cssVar("--text"); ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(X(t), 0); ctx.lineTo(X(t), H - 14); ctx.stroke();
  ctx.fillStyle = cssVar("--text"); ctx.beginPath(); ctx.moveTo(X(t) - 6, 0); ctx.lineTo(X(t) + 6, 0); ctx.lineTo(X(t), 8); ctx.fill();
  ctx.textBaseline = "alphabetic";
  state._tl = { padL, padR, W };
}
function initTimelineClick() {
  const c = $("#timeline");
  const go = e => { const r = c.getBoundingClientRect(), g = state._tl; if (!g) return; const x = e.clientX - r.left; seek(state.simDur * (x - g.padL) / (r.width - g.padL - g.padR)); };
  let drag = false;
  c.addEventListener("mousedown", e => { drag = true; go(e); });
  window.addEventListener("mousemove", e => drag && go(e));
  window.addEventListener("mouseup", () => (drag = false));
}

// ---------------------------------------------------------------- gauge, load, phase
function updateGauge(t) {
  const c = $("#gauge"), ctx = c.getContext("2d"), a = state.res.analysis, cp = a.confirm_params;
  const W = c.width, H = c.height; ctx.clearRect(0, 0, W, H);
  const i = t <= state.vidDur ? bsearch(state.frameTimes, t + 0.02) : -1;
  const pf = i >= 0 ? a.per_frame[i] : null;
  const v = pf ? pf.ev : 0;
  const cx = W / 2, cy = H - 18, R = 100;
  const arc = (from, to, col, w) => { ctx.beginPath(); ctx.arc(cx, cy, R, Math.PI + from * Math.PI, Math.PI + to * Math.PI); ctx.strokeStyle = col; ctx.lineWidth = w; ctx.stroke(); };
  arc(0, 1, cssVar("--card2"), 16); arc(0, cp.suspect_conf, "rgba(147,160,187,.35)", 16);
  arc(cp.suspect_conf, cp.confirm_conf, "rgba(245,158,11,.45)", 16); arc(cp.confirm_conf, 1, "rgba(239,68,68,.45)", 16);
  const col = pf && pf.ev_state === "CONFIRMED" ? "#ef4444" : v >= cp.suspect_conf ? "#f59e0b" : "#4f8cff";
  if (v > 0) arc(0, v, col, 8);
  const ang = Math.PI + v * Math.PI; ctx.strokeStyle = cssVar("--text"); ctx.lineWidth = 3;
  ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(cx + Math.cos(ang) * (R - 18), cy + Math.sin(ang) * (R - 18)); ctx.stroke();
  ctx.fillStyle = cssVar("--text"); ctx.beginPath(); ctx.arc(cx, cy, 5, 0, 7); ctx.fill();
  ctx.font = "800 26px " + cssVar("--mono"); ctx.textAlign = "center"; ctx.fillText(v.toFixed(2), cx, cy - 30);
  ctx.font = "600 11px " + cssVar("--font"); ctx.fillStyle = cssVar("--muted");
  ctx.fillText("0", cx - R, cy + 14); ctx.fillText("1", cx + R, cy + 14); ctx.fillText("confidence (this frame)", cx, cy - 62); ctx.textAlign = "left";
  // state: the strongest knowledge so far (confirmed tracks stay confirmed until lost)
  let st = "NONE", cls = "";
  if (pf && pf.ev_state) { st = pf.ev_state === "CANDIDATE" ? "LOW CONFIDENCE" : pf.ev_state; cls = pf.ev_cls; }
  const pill = $("#evPill"); pill.textContent = st;
  pill.className = "pill " + (st === "CONFIRMED" ? "conf" : st === "SUSPECTED" ? "sus" : "none");
  $("#evCls").textContent = cls ? cls : (t > state.vidDur ? "(video ended)" : "");
  $("#evStreak").textContent = pf && pf.ev > 0 ? `consecutive frames ≥ ${cp.confirm_conf}: ${Math.min(pf.streak, cp.confirm_frames)}/${cp.confirm_frames}` + (pf.streak > cp.confirm_frames ? " ✓" : "") : `needs ${cp.confirm_frames} consecutive frames ≥ ${cp.confirm_conf} to preempt`;
}
function updateLoad(t) {
  const box = $("#loadBars"), q = sim().queues, sig = signalAt(t);
  if (!box.children.length) APP.forEach(a => { const d = document.createElement("div"); d.className = "lb"; d.innerHTML = `<span><i class="sig"></i>${NAMES[a]}</span><span class="track"><i></i><u></u></span><b></b>`; box.appendChild(d); });
  const maxv = Math.max(8, ...APP.map(a => Math.max(...q[a].map(x => x[1]))));
  APP.forEach((a, k) => {
    const arr = q[a], i = Math.max(0, bsearch(arr, t, x => x[0])), [, n, qn] = arr[i] || [0, 0, 0];
    const d = box.children[k]; d.querySelector(".sig").style.background = COL[sig.s[k]];
    d.querySelector("i:not(.sig)") && (d.querySelector(".track i").style.width = (100 * n / maxv) + "%");
    d.querySelector(".track u").style.width = (100 * qn / maxv) + "%";
    d.querySelector("b").textContent = `${n} · ${qn}q`;
  });
}
function updatePhase(t) {
  const m = signalAt(t).mode, el = $("#phaseNow");
  const map = { NORMAL: ["NORMAL CYCLE", ""], PREEMPT_CLEAR: ["⚠ PREEMPTION · clearing conflicting approaches", "clr"], PREEMPT_GREEN: ["🚑 PREEMPTION · emergency vehicle has green", "pre"], RECOVERY: ["↺ RECOVERY · back to normal cycle", "rec"] };
  const [txt, cl] = state.mode === "fixed" ? ["FIXED-TIME CONTROL · no preemption (comparison)", ""] : map[m] || [m, ""];
  if (el.textContent !== txt) { el.textContent = txt; el.className = "phase-now " + cl; }
}

// ---------------------------------------------------------------- wiring
function initDashboard() {
  $("#playBtn").onclick = () => (state.playing ? stop() : play());
  $("#restartBtn").onclick = () => { seek(0); };
  $("#speedSel").onchange = e => { state.speed = Number(e.target.value); $("#video").playbackRate = state.speed; };
  $$("[data-mode]").forEach(b => b.onclick = () => {
    $$("[data-mode]").forEach(x => x.classList.toggle("on", x === b)); state.mode = b.dataset.mode;
    $("#loadBars").innerHTML = ""; buildLog(); drawTimeline(); renderAll();
  });
  $$("[data-ov]").forEach(b => b.onclick = () => { $$("[data-ov]").forEach(x => x.classList.toggle("on", x === b)); state.overlay = b.dataset.ov; });
  $("#video").addEventListener("ended", () => { state.lastTs = null; });
  document.addEventListener("keydown", e => {
    if (!state.res || $("#dashboard").hidden || ["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement.tagName)) return;
    if (e.code === "Space") { e.preventDefault(); state.playing ? stop() : play(); }
    if (e.code === "ArrowRight") seek(state.t + 1); if (e.code === "ArrowLeft") seek(state.t - 1);
  });
  initTimelineClick();
  window.addEventListener("resize", () => state.res && renderAll());
}
window.addEventListener("DOMContentLoaded", () => {
  initTheme(); initStart(); initDashboard(); requestAnimationFrame(tick);
  const q = new URLSearchParams(location.search);
  const initT = q.get("t") ? Number(q.get("t")) : 0;
  if (q.get("job")) api(`/api/jobs/${q.get("job")}`).then(j => { if (j.status === "done") loadResult(j.id, initT); else { show("processing"); poll(j.id); } }).catch(() => { });
  if (q.get("theme")) document.documentElement.dataset.theme = q.get("theme");
});
