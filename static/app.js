const svg = document.getElementById("graph");
const logEl = document.getElementById("log");
const tickBtn = document.getElementById("tick-btn");
const resetBtn = document.getElementById("reset-btn");

const DOMAIN_COLORS = {};
const PALETTE = ["#e2a53f", "#5c8ce2", "#3f7d5c", "#c25ce2", "#e25c8c", "#5ce2c2"];

function colorForDomain(domain) {
  if (!(domain in DOMAIN_COLORS)) {
    DOMAIN_COLORS[domain] = PALETTE[Object.keys(DOMAIN_COLORS).length % PALETTE.length];
  }
  return DOMAIN_COLORS[domain];
}

function edgeColor(edge) {
  if (edge.type === "collides") {
    if (edge.status === "open") return "#e2504a";
    if (edge.status === "vindicated") return "#3f7d5c";
    if (edge.status === "mooted") return "#7d8496";
    if (edge.status === "wrong") return "#e2504a";
    if (edge.status === "reconciled_together") return "#c25ce2";
    return "#e2504a";
  }
  if (edge.type === "reinforces") return "#3f7d5c";
  if (edge.type === "scope_parent") return "#5c8ce2";
  return "#7d8496";
}

// Fixed layout: group nodes by domain into loose clusters instead of
// running real physics -- this graph stays small (a handful of nodes),
// and a stable, readable position beats a bouncing force simulation
// for a demo meant to be watched, not admired as a physics toy.
function layout(nodes) {
  const domains = [...new Set(nodes.map((n) => n.domain))];
  const w = svg.clientWidth || 800;
  const h = svg.clientHeight || 600;
  const clusterCenters = {};
  domains.forEach((d, i) => {
    const angle = (i / domains.length) * Math.PI * 2;
    clusterCenters[d] = {
      x: w / 2 + Math.cos(angle) * Math.min(w, h) * 0.28,
      y: h / 2 + Math.sin(angle) * Math.min(w, h) * 0.28,
    };
  });

  const byDomain = {};
  nodes.forEach((n) => {
    (byDomain[n.domain] = byDomain[n.domain] || []).push(n);
  });

  const positions = {};
  Object.entries(byDomain).forEach(([domain, group]) => {
    const center = clusterCenters[domain];
    group.forEach((n, i) => {
      const angle = (i / Math.max(group.length, 1)) * Math.PI * 2;
      const r = group.length > 1 ? 70 : 0;
      positions[n.id] = {
        x: center.x + Math.cos(angle) * r,
        y: center.y + Math.sin(angle) * r,
      };
    });
  });
  return positions;
}

function render(state) {
  const positions = layout(state.nodes);
  const parts = [];

  for (const edge of state.edges) {
    const a = positions[edge.source];
    const b = positions[edge.target];
    if (!a || !b) continue;
    const isOpenCollision = edge.type === "collides" && edge.status === "open";
    const dash = edge.type === "scope_parent" ? ' stroke-dasharray="4,4"' : "";
    parts.push(
      `<line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" stroke="${edgeColor(edge)}" stroke-width="2"${dash} class="${isOpenCollision ? "pulse" : ""}" />`
    );
    const mx = (a.x + b.x) / 2;
    const my = (a.y + b.y) / 2;
    parts.push(`<text class="edge-label" x="${mx}" y="${my}">${edge.type}${edge.status ? " · " + edge.status : ""}</text>`);
  }

  for (const node of state.nodes) {
    const p = positions[node.id];
    if (!p) continue;
    const isSeed = node.origin === "seed";
    const earned = Math.min(1, node.evidence_count / 2);
    const opacity = isSeed ? 0.35 + 0.5 * earned : 0.95;
    const radius = 14 + node.weight * 18;
    const strokeDash = isSeed && earned < 1 ? ' stroke-dasharray="3,3"' : "";
    parts.push(
      `<circle cx="${p.x}" cy="${p.y}" r="${radius}" fill="${colorForDomain(node.domain)}" fill-opacity="${opacity}" stroke="${colorForDomain(node.domain)}" stroke-width="1.5"${strokeDash} />`
    );
    parts.push(`<text class="node-label" x="${p.x}" y="${p.y - radius - 6}" text-anchor="middle">${node.text}</text>`);
    parts.push(`<text class="node-label" x="${p.x}" y="${p.y + 4}" text-anchor="middle" fill="#0b0d12" font-weight="600">${node.referent}</text>`);
  }

  svg.innerHTML = parts.join("\n");
}

function logTick(tick, description, isCollide, isResolve) {
  const entry = document.createElement("div");
  entry.className = "log-entry" + (isCollide ? " collide" : "") + (isResolve ? " resolve" : "");
  entry.innerHTML = `<div class="log-tick">tick ${tick}</div>${description}`;
  logEl.appendChild(entry);
}

async function fetchState() {
  const res = await fetch("/state");
  render(await res.json());
}

async function doTick() {
  tickBtn.disabled = true;
  const res = await fetch("/tick", { method: "POST" });
  const data = await res.json();
  // Styled off the server's structured `kind`, not string-sniffed from
  // the prose description -- a substring check on "resolve" previously
  // mis-tagged the still_open tick because "unresolved" contains it.
  const isCollide = data.kind === "collide_open";
  const isResolve = data.kind === "resolve";
  logTick(data.tick, data.description, isCollide, isResolve);
  render(data.state);
  tickBtn.disabled = data.done;
}

async function doReset() {
  await fetch("/reset", { method: "POST" });
  logEl.innerHTML = "";
  tickBtn.disabled = false;
  fetchState();
}

tickBtn.addEventListener("click", doTick);
resetBtn.addEventListener("click", doReset);
window.addEventListener("resize", fetchState);

fetchState();
