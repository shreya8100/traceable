// ── DOM REFERENCES ─────────────────────────────────────────────────────────

const queryInput   = document.getElementById("query");
const searchBtn    = document.getElementById("searchBtn");
const pipelineEl   = document.getElementById("pipeline-status");
const pipelineText = document.getElementById("pipeline-text");
const heroError    = document.getElementById("hero-error");
const resultsSec   = document.getElementById("results-section");
const resultsTopic = document.getElementById("results-topic");
const resultsMeta  = document.getElementById("results-meta");
const thead        = document.getElementById("results-thead");
const tbody        = document.getElementById("results-tbody");
const popover      = document.getElementById("popover");

// ── UTILS ──────────────────────────────────────────────────────────────────

function esc(s) {
  return String(s ?? "").replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c] ?? c)
  );
}

// ── PIPELINE STEP TRACKER ──────────────────────────────────────────────────

const STEP_IDS = ["step-search", "step-scrape", "step-extract", "step-merge"];

function setStep(activeIndex) {
  STEP_IDS.forEach((id, i) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.remove("active", "done");
    if (i < activeIndex)  el.classList.add("done");
    if (i === activeIndex) el.classList.add("active");
  });
}

// ── EXAMPLE PILLS ──────────────────────────────────────────────────────────

document.querySelectorAll(".example-pill").forEach((pill) => {
  pill.addEventListener("click", () => {
    queryInput.value = pill.textContent ?? "";
    queryInput.focus();
  });
});

// ── POPOVER ────────────────────────────────────────────────────────────────

function showPopover(e, sources) {
  let html = `<div class="popover-label">Source evidence</div>`;
  sources.forEach((s) => {
    html += `
      <div class="popover-source">
        <div class="popover-quote">${esc(s.evidence || s.value)}</div>
        <a class="popover-link" href="${esc(s.source_url)}" target="_blank" rel="noopener">
          ${esc(s.source_url)}
        </a>
      </div>`;
  });
  popover.innerHTML = html;
  positionPopover(e);
  popover.classList.add("visible");
}

function positionPopover(e) {
  const PW = 320;
  const PH = 200;
  let x = e.clientX + 12;
  let y = e.clientY + 12;
  if (x + PW > window.innerWidth  - 16) x = e.clientX - PW - 8;
  if (y + PH > window.innerHeight - 16) y = e.clientY - PH - 8;
  popover.style.left = `${x}px`;
  popover.style.top  = `${y}px`;
}

function hidePopover() {
  popover.classList.remove("visible");
}

document.addEventListener("mousemove", (e) => {
  if (popover.classList.contains("visible")) positionPopover(e);
});

// ── TABLE RENDERER ─────────────────────────────────────────────────────────

function renderTable(data) {
  if (!data.rows || data.rows.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="99" style="text-align:center;color:var(--muted);padding:40px;font-family:var(--font-mono);font-size:13px;">
          No entities found. Try a more specific query.
        </td>
      </tr>`;
    return;
  }

  const keys = [];
  data.rows.forEach((row) => {
    Object.keys(row.attributes).forEach((k) => {
      if (!keys.includes(k)) keys.push(k);
    });
  });

  thead.innerHTML = `
    <tr>
      <th>Entity</th>
      ${keys.map((k) => `<th>${esc(k.replace(/_/g, " "))}</th>`).join("")}
      <th>Sources</th>
    </tr>`;

  tbody.innerHTML = data.rows.map((row) => {
    const cells = keys.map((k) => {
      const vals = row.attributes[k];
      if (!vals || !vals.length) {
        return `<td style="color:var(--muted)">—</td>`;
      }
      const primary = vals[0];
      const srcData = esc(JSON.stringify(vals));
      const badge   = vals.length > 1
        ? `<span class="cell-count">${vals.length}</span>`
        : "";
      return `<td>
        <span class="cell-val" data-sources='${srcData}'>
          ${esc(primary.value)}${badge}
        </span>
      </td>`;
    }).join("");

    const srcCount = row.sources.length;
    return `
      <tr class="fade-up">
        <td class="entity-name">${esc(row.name)}</td>
        ${cells}
        <td class="sources-cell">
          <span class="source-dot"></span>${srcCount} page${srcCount === 1 ? "" : "s"}
        </td>
      </tr>`;
  }).join("");

  tbody.querySelectorAll(".cell-val").forEach((el) => {
    el.addEventListener("mouseenter", (e) => {
      const sources = JSON.parse(el.getAttribute("data-sources") ?? "[]");
      showPopover(e, sources);
    });
    el.addEventListener("mouseleave", hidePopover);
  });
}

// ── SEARCH ─────────────────────────────────────────────────────────────────

async function runSearch() {
  const topic = queryInput.value.trim();
  if (!topic) return;

  heroError.innerHTML = "";
  resultsSec.style.display = "none";
  pipelineEl.style.display = "block";
  searchBtn.disabled = true;
  searchBtn.innerHTML = `<span class="spinner"></span>Running`;
  setStep(0);
  pipelineText.textContent = "Searching the web…";

  const pipelineMessages = [
    [0,     "Searching the web…",            0],
    [2000,  "Scraping pages…",               1],
    [5000,  "Extracting entities with LLM…", 2],
    [18000, "Merging and deduplicating…",    3],
  ];
  const timers = pipelineMessages.map(([delay, msg, stepIdx]) =>
    setTimeout(() => {
      setStep(stepIdx);
      pipelineText.textContent = msg;
    }, delay)
  );

  try {
    const resp = await fetch("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ topic }),
    });

    timers.forEach(clearTimeout);

    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail ?? "Unknown error");

    setStep(STEP_IDS.length);
    pipelineText.textContent = `Done — ${data.stats.merged_entities} entities found.`;

    resultsTopic.textContent = `"${topic}"`;
    const s = data.stats;
    resultsMeta.innerHTML = `
      <span><b>${s.searched}</b> pages searched</span>
      <span><b>${s.scraped}</b> scraped</span>
      <span><b>${s.extracted_entities_raw}</b> raw mentions</span>
      <span><b>${s.merged_entities}</b> entities</span>`;

    renderTable(data);
    resultsSec.style.display = "block";
    resultsSec.scrollIntoView({ behavior: "smooth", block: "start" });

  } catch (err) {
    timers.forEach(clearTimeout);
    pipelineEl.style.display = "none";
    heroError.innerHTML = `<div class="error-msg">Error: ${esc(err.message)}</div>`;
  } finally {
    searchBtn.disabled = false;
    searchBtn.innerHTML = `
      <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
        <path d="M5 12h14M12 5l7 7-7 7"/>
      </svg>
      Search`;
  }
}

// ── EVENT LISTENERS ────────────────────────────────────────────────────────

searchBtn.addEventListener("click", runSearch);
queryInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") runSearch();
});