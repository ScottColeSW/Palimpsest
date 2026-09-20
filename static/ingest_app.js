const svg = document.getElementById("graph");
const logEl = document.getElementById("log");
const tickBtn = document.getElementById("tick-btn");
const tick5Btn = document.getElementById("tick5-btn");
const resetBtn = document.getElementById("reset-btn");
const progressBar = document.getElementById("progress-bar");
const progressLabel = document.getElementById("progress-label");
const episodeCountEl = document.getElementById("episode-count");
const dormantCountEl = document.getElementById("dormant-count");

const REFERENT_COLORS = {};
const PALETTE = ["#e2a53f", "#5c8ce2", "#3f7d5c", "#c25ce2", "#e25c8c", "#5ce2c2", "#e28c5c"];

function colorForReferent(referent) {
  if (!(referent in REFERENT_COLORS)) {
    REFERENT_COLORS[referent] = PALETTE[Object.keys(REFERENT_COLORS).length % PALETTE.length];
  }
  return REFERENT_COLORS[referent];
}

// Episode nodes cluster by referent -- the interesting axis here,
// since domain is constant ("story") for the whole run. Dormant
// nodes don't get individual clustering at all: they pile up as a
// dim, visibly-growing mass bottom-left, because their point is
// collective ("this much material wasn't judged significant yet"),
// not individual identity -- a real, inspectable pile instead of a
// void nothing went into.
function layout(nodes) {
  const w = svg.clientWidth || 800;
  const h = svg.clientHeight || 600;
  const episodes = nodes.filter((n) => n.origin === "episode");
  const dormant = nodes.filter((n) => n.origin === "dormant");

  const referents = [...new Set(episodes.map((n) => n.referent))];
  const clusterCenters = {};
  referents.forEach((r, i) => {
    const angle = (i / Math.max(referents.length, 1)) * Math.PI * 2;
    clusterCenters[r] = {
      x: w * 0.55 + Math.cos(angle) * Math.min(w, h) * 0.28,
      y: h * 0.45 + Math.sin(angle) * Math.min(w, h) * 0.28,
    };
  });

  const byReferent = {};
  episodes.forEach((n) => (byReferent[n.referent] = byReferent[n.referent] || []).push(n));

  // Spiral outward per referent instead of a tight ring -- a ring packs
  // nodes close enough that the edges between them are a few pixels
  // long and vanish under the overlapping circles. Spiraling out means
  // each new mention sits visibly farther from the last, so the edge
  // connecting them reads as an actual line, not a rumor of one.
  const positions = {};
  Object.entries(byReferent).forEach(([referent, group]) => {
    const center = clusterCenters[referent];
    group.forEach((n, i) => {
      const angle = i * 0.85;
      const r = 22 + i * 17;
      positions[n.id] = { x: center.x + Math.cos(angle) * r, y: center.y + Math.sin(angle) * r };
    });
  });

  // Dormant pile: a loose, gently-growing cluster in the bottom-left
  // corner, capped visually by wrapping rows rather than spreading
  // across the whole canvas as the count grows.
  const pileOrigin = { x: 90, y: h - 90 };
  dormant.forEach((n, i) => {
    const col = i % 10;
    const row = Math.floor(i / 10);
    positions[n.id] = { x: pileOrigin.x + col * 14, y: pileOrigin.y - row * 14 };
  });

  return { positions, episodeCount: episodes.length, dormantCount: dormant.length };
}

function edgeColor(edge) {
  if (edge.type === "reinforces") return "#3f7d5c";
  if (edge.type === "coexists") return "#5c8ce2";
  if (edge.type === "collides") return edge.status === "open" ? "#e2504a" : "#7d8496";
  if (edge.type === "scope_parent") return "#c25ce2";
  return "#7d8496";
}

function render(state) {
  const { positions, episodeCount, dormantCount } = layout(state.nodes);
  const parts = [];

  // Edges drawn first so nodes sit visually on top of them.
  for (const edge of state.edges || []) {
    const a = positions[edge.source];
    const b = positions[edge.target];
    if (!a || !b) continue;
    const isOpenCollision = edge.type === "collides" && edge.status === "open";
    const opacity = edge.type === "coexists" ? 0.6 : 0.85;
    parts.push(
      `<line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" stroke="${edgeColor(edge)}" stroke-width="2.5" stroke-opacity="${opacity}" class="${isOpenCollision ? "pulse" : ""}" />`
    );
  }

  for (const node of state.nodes) {
    const p = positions[node.id];
    if (!p) continue;
    if (node.origin === "dormant") {
      parts.push(`<circle cx="${p.x}" cy="${p.y}" r="4" fill="#3a4152" fill-opacity="0.6" />`);
      continue;
    }
    const radius = 12 + node.weight * 10;
    parts.push(
      `<circle cx="${p.x}" cy="${p.y}" r="${radius}" fill="${colorForReferent(node.referent)}" fill-opacity="0.9" />`
    );
    parts.push(`<text class="node-label" x="${p.x}" y="${p.y - radius - 4}" text-anchor="middle">${node.referent}</text>`);
  }

  if (dormantCount > 0) {
    parts.push(`<text class="node-label" x="90" y="${(svg.clientHeight || 600) - 100}" text-anchor="middle" fill="#7d8496">dormant pile</text>`);
  }

  svg.innerHTML = parts.join("\n");
  episodeCountEl.textContent = episodeCount;
  dormantCountEl.textContent = dormantCount;
}

function renderProminence(prominence) {
  const list = document.getElementById("prominence-list");
  list.innerHTML = (prominence || [])
    .map(([referent, score]) => `<div class="prom-row"><span>${referent}</span><span class="score">${score}</span></div>`)
    .join("");
}

function logNode(node, relation) {
  const entry = document.createElement("div");
  const relationClass = relation ? ` relation-${relation}` : "";
  entry.className = "log-entry" + (node.origin === "episode" ? " episode" : "") + relationClass;
  const relationLabel = relation ? ` [${relation}]` : "";
  entry.innerHTML = `<strong>${node.origin}${relationLabel}</strong> ${node.referent !== "unknown" ? `(${node.referent}) ` : ""}— ${node.text.replace(/</g, "&lt;").slice(0, 90)}`;
  logEl.appendChild(entry);
}

function updateProgress(state) {
  const pct = Math.round(state.percent_digested * 100);
  progressBar.style.width = pct + "%";
  progressLabel.textContent = `${pct}% digested — ${state.book}, ${state.chunk_size}-char chunks`;
}

async function fetchState() {
  const res = await fetch("/ingest/state");
  const state = await res.json();
  render(state);
  updateProgress(state);
  renderProminence(state.prominence);
}

async function doTick() {
  const res = await fetch("/ingest/tick", { method: "POST" });
  const data = await res.json();
  if (data.node) logNode(data.node, data.relation);
  render(data.state);
  updateProgress(data.state);
  renderProminence(data.state.prominence);
  tickBtn.disabled = data.done;
  tick5Btn.disabled = data.done;
}

async function doTick5() {
  for (let i = 0; i < 5; i++) {
    const res = await fetch("/ingest/tick", { method: "POST" });
    const data = await res.json();
    if (data.node) logNode(data.node, data.relation);
    if (data.done) {
      render(data.state);
      updateProgress(data.state);
      renderProminence(data.state.prominence);
      tickBtn.disabled = true;
      tick5Btn.disabled = true;
      return;
    }
  }
  fetchState();
}

async function doReset() {
  await fetch("/ingest/reset", { method: "POST" });
  logEl.innerHTML = "";
  Object.keys(REFERENT_COLORS).forEach((k) => delete REFERENT_COLORS[k]);
  tickBtn.disabled = false;
  tick5Btn.disabled = false;
  fetchState();
}

tickBtn.addEventListener("click", doTick);
tick5Btn.addEventListener("click", doTick5);
resetBtn.addEventListener("click", doReset);
window.addEventListener("resize", fetchState);

fetchState();
