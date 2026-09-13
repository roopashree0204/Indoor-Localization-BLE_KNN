"use strict";

// ─── Config ───────────────────────────────────────────────────────────────────
const POLL_MS       = 1000;
const SPARKLINE_LEN = 40;

// Floor plan marker positions per zone
const ZONE_POS = {
  "Room101":  { left: "13%", top: "28%" },
  "Room102":  { left: "36%", top: "28%" },
  "Room103":  { left: "60%", top: "28%" },
  "Room104":  { left: "85%", top: "28%" },
  "Corridor": { left: "44%", top: "50%" },
  "UNKNOWN":  { left: "44%", top: "50%" },
};

// ─── State ────────────────────────────────────────────────────────────────────
const sparkA    = [];
const sparkB    = [];
let   logItems  = [];
let   prevConn  = null;
let   prevState = null;
let   prevLoc   = null;

// ─── DOM ──────────────────────────────────────────────────────────────────────
const el = id => document.getElementById(id);

const dom = {
  // banner
  banner:       el("disconnectedBanner"),
  bannerText:   el("bannerText"),
  bannerRetry:  el("bannerRetry"),

  // topbar chip
  statusChip:   el("statusChip"),
  chipDot:      el("chipDot"),
  chipValue:    el("chipValue"),

  // sidebar
  sysDot:       el("sysDot"),
  sysStatusText:el("sysStatusText"),

  // metric cards
  cardA:   el("cardA"),  valA:  el("valA"),  unitA: el("unitA"),  subA:  el("subA"),
  cardB:   el("cardB"),  valB:  el("valB"),  unitB: el("unitB"),  subB:  el("subB"),
  cardLoc: el("cardLoc"),valLoc:el("valLoc"),subLoc:el("subLoc"),
  cardConf:el("cardConf"),valConf:el("valConf"),accLabel:el("accLabel"),

  // sparklines
  sparkA:  el("sparkA"),
  sparkB:  el("sparkB"),
  sparkConf: el("sparkConf"),

  // live panel
  liveBadge:    el("liveBadge"),
  liveDot:      el("liveDot"),
  liveBadgeText:el("liveBadgeText"),
  liveHere:     el("liveHere"),
  liveRoom:     el("liveRoom"),
  liveAcc:      el("liveAcc"),
  liveTime:     el("liveTime"),

  // radar
  radarR1:      el("radarR1"),
  radarR2:      el("radarR2"),
  radarR3:      el("radarR3"),
  radarCenter:  el("radarCenter"),

  // activity log
  activityList: el("activityList"),

  // map
  mapOfflineOverlay: el("mapOfflineOverlay"),
  mapOfflineSub:     el("mapOfflineSub"),
  fpLocation:        el("fpLocation"),
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

function now12() {
  const d   = new Date();
  const pad = n => String(n).padStart(2, "0");
  const h   = d.getHours();
  const ampm = h >= 12 ? "PM" : "AM";
  const h12  = h % 12 || 12;
  return `${pad(h12)}:${pad(d.getMinutes())}:${pad(d.getSeconds())} ${ampm}`;
}

function addLog(msg, dotClass = "act-dot--purple") {
  logItems.unshift({ time: now12(), msg, dotClass });
  if (logItems.length > 60) logItems.pop();
  renderLog();
}

function renderLog() {
  dom.activityList.innerHTML = logItems.map(e => `
    <div class="activity-item">
      <div class="act-time">${e.time}</div>
      <div class="act-dot ${e.dotClass}"></div>
      <div class="act-content">
        <div class="act-content__title">${e.msg}</div>
      </div>
    </div>
  `).join("");
}

// ─── Sparkline ────────────────────────────────────────────────────────────────

function drawSparkline(canvas, data, color) {
  const ctx = canvas.getContext("2d");
  const W   = canvas.width;
  const H   = canvas.height;
  const pad = 4;
  ctx.clearRect(0, 0, W, H);
  if (data.length < 2) return;

  const min   = Math.min(...data) - 5;
  const max   = Math.max(...data) + 5;
  const range = max - min || 1;
  const toX   = i => pad + (i / (SPARKLINE_LEN - 1)) * (W - 2 * pad);
  const toY   = v => H - pad - ((v - min) / range) * (H - 2 * pad);

  const grad = ctx.createLinearGradient(0, 0, 0, H);
  grad.addColorStop(0, color + "44");
  grad.addColorStop(1, color + "00");

  ctx.beginPath();
  data.forEach((v, i) => {
    const xi = toX(i + (SPARKLINE_LEN - data.length));
    i === 0 ? ctx.moveTo(xi, toY(v)) : ctx.lineTo(xi, toY(v));
  });
  ctx.lineTo(toX(SPARKLINE_LEN - 1), H);
  ctx.lineTo(toX(SPARKLINE_LEN - data.length), H);
  ctx.closePath();
  ctx.fillStyle = grad;
  ctx.fill();

  ctx.beginPath();
  data.forEach((v, i) => {
    const xi = toX(i + (SPARKLINE_LEN - data.length));
    i === 0 ? ctx.moveTo(xi, toY(v)) : ctx.lineTo(xi, toY(v));
  });
  ctx.strokeStyle = color;
  ctx.lineWidth   = 1.5;
  ctx.shadowColor = color;
  ctx.shadowBlur  = 4;
  ctx.stroke();
  ctx.shadowBlur  = 0;
}

// ─── State Appliers ───────────────────────────────────────────────────────────

function applyDisconnected(d) {
  // Banner
  dom.banner.className = "disconnected-banner";
  dom.bannerText.textContent = d.error_message || "ESP32 not connected — connect the device and it will appear automatically.";
  dom.bannerRetry.textContent = "● Scanning…";

  // Top chip
  dom.statusChip.className = "status-chip offline";
  dom.chipDot.className    = "status-chip__dot offline";
  dom.chipValue.className  = "status-chip__value offline";
  dom.chipValue.textContent = "DISCONNECTED";

  // Sidebar
  dom.sysDot.className        = "sys-dot offline";
  dom.sysStatusText.className = "sys-value offline";
  dom.sysStatusText.textContent = "OFFLINE";

  // Cards — dimmed
  [dom.cardA, dom.cardB, dom.cardLoc, dom.cardConf].forEach(c => c.classList.add("dimmed"));

  dom.valA.textContent  = "—"; dom.unitA.textContent = ""; dom.subA.textContent  = "No Signal";
  dom.valB.textContent  = "—"; dom.unitB.textContent = ""; dom.subB.textContent  = "No Signal";
  dom.valLoc.textContent = "—"; dom.subLoc.textContent = "Awaiting signal";
  dom.valConf.textContent = "—"; dom.accLabel.textContent = "No Signal";

  // Live panel
  dom.liveBadge.className    = "live-badge offline";
  dom.liveDot.className      = "live-dot inactive";
  dom.liveBadgeText.textContent = "OFFLINE";
  dom.liveHere.textContent   = "Device status";
  dom.liveRoom.textContent   = "DISCONNECTED";
  dom.liveAcc.textContent    = "—";

  // Radar — stop animation
  dom.radarCenter.classList.add("offline");
  [dom.radarR1, dom.radarR2, dom.radarR3].forEach(r => r.classList.add("paused"));

  // Map overlay — show
  dom.mapOfflineOverlay.classList.remove("hidden");
  dom.mapOfflineSub.textContent = d.error_message || "Connect your device to see live location tracking";
  dom.fpLocation.style.display = "none";

  // Clear room highlights
  document.querySelectorAll(".fp-room--active").forEach(r => r.classList.remove("fp-room--active"));
}

function applyIdle(d) {
  // Banner
  dom.banner.className = "disconnected-banner idle";
  dom.bannerText.textContent = "ESP32 connected but not sending data — check if your ESP32 sketch is running.";
  dom.bannerRetry.textContent = "● Waiting for data…";

  // Top chip
  dom.statusChip.className = "status-chip idle";
  dom.chipDot.className    = "status-chip__dot idle";
  dom.chipValue.className  = "status-chip__value idle";
  dom.chipValue.textContent = "IDLE";

  // Sidebar
  dom.sysDot.className        = "sys-dot idle";
  dom.sysStatusText.className = "sys-value idle";
  dom.sysStatusText.textContent = "IDLE";

  [dom.cardA, dom.cardB, dom.cardLoc, dom.cardConf].forEach(c => c.classList.add("dimmed"));

  // Live badge
  dom.liveBadge.className    = "live-badge idle";
  dom.liveDot.className      = "live-dot inactive";
  dom.liveBadgeText.textContent = "IDLE";
  dom.liveHere.textContent   = "Device status";
  dom.liveRoom.textContent   = "IDLE";

  // Map overlay
  dom.mapOfflineOverlay.classList.remove("hidden");
  dom.mapOfflineSub.textContent = "ESP32 is connected but not sending data yet";
  dom.fpLocation.style.display = "none";

  // Radar — pause
  dom.radarCenter.classList.add("offline");
  [dom.radarR1, dom.radarR2, dom.radarR3].forEach(r => r.classList.add("paused"));
}

function applyOnline(d) {
  // Hide banner
  dom.banner.classList.add("hidden");

  // Top chip
  dom.statusChip.className = "status-chip online";
  dom.chipDot.className    = "status-chip__dot online";
  dom.chipValue.className  = "status-chip__value online";
  dom.chipValue.textContent = d.system_state === "TRACKING" ? "TRACKING" : "ONLINE";

  // Sidebar
  dom.sysDot.className        = "sys-dot online";
  dom.sysStatusText.className = "sys-value online";
  dom.sysStatusText.textContent = "ONLINE";

  // Cards — restore
  [dom.cardA, dom.cardB, dom.cardLoc, dom.cardConf].forEach(c => c.classList.remove("dimmed"));

  // Beacon A
  dom.valA.textContent  = d.beaconA !== null ? d.beaconA : "—";
  dom.unitA.textContent = d.beaconA !== null ? "dBm" : "";
  dom.subA.textContent  = d.beaconA_status || "—";

  // Beacon B
  dom.valB.textContent  = d.beaconB !== null ? d.beaconB : "—";
  dom.unitB.textContent = d.beaconB !== null ? "dBm" : "";
  dom.subB.textContent  = d.beaconB_status || "—";

  // Location
  dom.valLoc.textContent = d.location !== "UNKNOWN" ? d.location : "—";
  dom.subLoc.textContent = d.location !== "UNKNOWN" ? "Building A · Floor 1" : "Detecting…";

  // Confidence
  dom.valConf.textContent = d.confidence > 0 ? `${d.confidence}%` : "—";
  dom.accLabel.textContent = d.accuracy_label || "—";
  dom.accLabel.className = d.confidence >= 85 ? "mcard__sub mcard__sub--green" : "mcard__sub";

  // Live badge
  dom.liveBadge.className    = "live-badge online";
  dom.liveDot.className      = "live-dot active";
  dom.liveBadgeText.textContent = "LIVE";
  dom.liveHere.textContent   = "You are here";
  dom.liveRoom.textContent   = d.location !== "UNKNOWN" ? d.location : "Detecting…";
  dom.liveAcc.textContent    = d.confidence > 0 ? `${d.confidence}%` : "—";

  // Last updated
  if (d.timestamp) {
    dom.liveTime.textContent = now12();
  }

  // Radar — resume
  dom.radarCenter.classList.remove("offline");
  [dom.radarR1, dom.radarR2, dom.radarR3].forEach(r => r.classList.remove("paused"));

  // Map overlay — hide
  dom.mapOfflineOverlay.classList.add("hidden");

  // Move location marker on floor plan
  if (d.location && d.location !== "UNKNOWN") {
    const pos = ZONE_POS[d.location] || ZONE_POS["Corridor"];
    dom.fpLocation.style.left    = pos.left;
    dom.fpLocation.style.top     = pos.top;
    dom.fpLocation.style.display = "flex";

    // Room highlights
    document.querySelectorAll(".fp-room").forEach(r => r.classList.remove("fp-room--active"));
    const zone = document.getElementById(`zone-${d.location}`);
    if (zone) zone.classList.add("fp-room--active");
  }

  // Sparklines
  if (d.beaconA !== null) {
    sparkA.push(d.beaconA);
    if (sparkA.length > SPARKLINE_LEN) sparkA.shift();
  }
  if (d.beaconB !== null) {
    sparkB.push(d.beaconB);
    if (sparkB.length > SPARKLINE_LEN) sparkB.shift();
  }
  drawSparkline(dom.sparkA, sparkA, "#3b82f6");
  drawSparkline(dom.sparkB, sparkB, "#6366f1");
}

// ─── Main poll ────────────────────────────────────────────────────────────────

async function poll() {
  let d;
  try {
    const res = await fetch("/data", { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    d = await res.json();
  } catch {
    // Flask itself is unreachable — show server error
    dom.banner.className = "disconnected-banner";
    dom.banner.classList.remove("hidden");
    dom.bannerText.textContent = "Cannot reach server — make sure app.py is running.";
    dom.chipValue.textContent  = "SERVER ERROR";
    return;
  }

  const conn  = d.connection;
  const state = d.system_state;

  // ── State machine ──────────────────────────────────
  if (conn === "DISCONNECTED" || state === "DISCONNECTED") {
    applyDisconnected(d);
    if (prevConn !== "DISCONNECTED") addLog("✗ ESP32 disconnected", "act-dot--red");
  } else if (conn === "IDLE" || state === "IDLE") {
    applyIdle(d);
    if (prevConn !== "IDLE") addLog("~ Connection IDLE — awaiting data", "act-dot--amber");
  } else {
    // ONLINE / TRACKING / WAITING
    applyOnline(d);

    // Log events for transitions
    if (prevConn === "DISCONNECTED" || prevConn === "IDLE") {
      addLog("✓ ESP32 connected — ONLINE", "act-dot--green");
    }
    if (prevState !== "TRACKING" && state === "TRACKING") {
      addLog("✓ Tracking started", "act-dot--green");
    }
    if (prevLoc !== null && prevLoc !== d.location && d.location !== "UNKNOWN") {
      addLog(`→ Moved to ${d.location}`, "act-dot--purple");
    }
    if (d.beaconA_status === "LOST") addLog("⚠ Beacon A signal LOST", "act-dot--red");
    if (d.beaconB_status === "LOST") addLog("⚠ Beacon B signal LOST", "act-dot--red");
  }

  prevConn  = conn;
  prevState = state;
  prevLoc   = d.location;
}

// ─── Boot ─────────────────────────────────────────────────────────────────────
addLog("Dashboard initialised", "act-dot--purple");
poll();
setInterval(poll, POLL_MS);