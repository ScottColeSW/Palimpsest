const pairsEl = document.getElementById("pairs");
const tickBtn = document.getElementById("tick-btn");
const resetBtn = document.getElementById("reset-btn");

function renderPair(result) {
  const card = document.createElement("div");
  card.className = "pair";
  const relationClass = "relation-" + result.relation;
  card.innerHTML = `
    <div class="source">${result.source} — domain="${result.domain}"</div>
    <div class="quotes">
      <div class="quote">${result.first_text}</div>
      <div class="connector">
        <span class="relation-badge ${relationClass}">${result.relation}</span>
        <span>token overlap: ${result.overlap}</span>
      </div>
      <div class="quote">${result.second_text}</div>
    </div>
  `;
  pairsEl.appendChild(card);
}

async function doTick() {
  const res = await fetch("/real-collision/tick", { method: "POST" });
  const data = await res.json();
  if (data.result) renderPair(data.result);
  tickBtn.disabled = data.done;
}

async function doReset() {
  await fetch("/real-collision/reset", { method: "POST" });
  pairsEl.innerHTML = "";
  tickBtn.disabled = false;
}

tickBtn.addEventListener("click", doTick);
resetBtn.addEventListener("click", doReset);
