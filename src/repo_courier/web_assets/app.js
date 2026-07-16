const form = document.querySelector("#preview-form");
const submitButton = document.querySelector("#submit-button");
const sourceGrid = document.querySelector("#source-grid");
const selectedSourceCount = document.querySelector("#selected-source-count");
const loading = document.querySelector("#loading");
const results = document.querySelector("#results");
const githubResults = document.querySelector("#github-results");
const resultList = document.querySelector("#result-list");
const channelResults = document.querySelector("#channel-results");
const emptyResult = document.querySelector("#empty-result");
const scanSummary = document.querySelector("#scan-summary");
const formError = document.querySelector("#form-error");

const SOURCE_PRESENTATION = {
  github: { icon: "GH", description: "热门项目、Topics、README 与 Star 增长" },
  news: { icon: "N", description: "MIT Tech Review、The Verge、WIRED 等" },
  blogs: { icon: "B", description: "OpenAI、Google DeepMind、Hugging Face 等" },
  academic: { icon: "aχ", description: "arXiv AI、NLP、CV 与机器学习论文" },
  products: { icon: "P", description: "Codex、Claude Code、Gemini CLI 等发布日志" },
  security: { icon: "S", description: "Krebs、The Hacker News、Google Security 等" },
};

const FALLBACK_SOURCES = [
  { id: "github", title: "GitHub Trending", source_count: 1, default: true },
  { id: "news", title: "科技新闻", source_count: 4, default: false },
  { id: "blogs", title: "大厂博客", source_count: 4, default: false },
  { id: "academic", title: "学术论文", source_count: 1, default: false },
  { id: "products", title: "产品更新", source_count: 4, default: false },
  { id: "security", title: "安全资讯", source_count: 4, default: false },
];

const escapeHtml = (value) =>
  String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

const number = (value) => new Intl.NumberFormat("zh-CN").format(Number(value || 0));

function parseInterests(value) {
  return [...new Set(value.split(/[,\n，]/).map((item) => item.trim()).filter(Boolean))];
}

function selectedSources() {
  return [...document.querySelectorAll('input[name="sources"]:checked')].map(
    (input) => input.value,
  );
}

function updateSourceCount() {
  selectedSourceCount.textContent = String(selectedSources().length);
}

function sourceCard(source) {
  const presentation = SOURCE_PRESENTATION[source.id] || {
    icon: source.id.slice(0, 2).toUpperCase(),
    description: `${source.source_count || 0} 个 RSS / Atom 信息源`,
  };
  return `
    <label class="source-card">
      <input type="checkbox" name="sources" value="${escapeHtml(source.id)}" ${source.default ? "checked" : ""} />
      <span class="source-check" aria-hidden="true">✓</span>
      <span class="source-icon" aria-hidden="true">${escapeHtml(presentation.icon)}</span>
      <span class="source-copy">
        <strong>${escapeHtml(source.title)}</strong>
        <small>${escapeHtml(presentation.description)}</small>
      </span>
      <span class="source-tag">${number(source.source_count)} SOURCE${Number(source.source_count) === 1 ? "" : "S"}</span>
    </label>`;
}

function renderSources(sources) {
  sourceGrid.innerHTML = sources.map(sourceCard).join("");
  sourceGrid.querySelectorAll('input[name="sources"]').forEach((input) => {
    input.addEventListener("change", updateSourceCount);
  });
  updateSourceCount();
}

async function loadSources() {
  try {
    const response = await fetch("/api/options", { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error("频道配置读取失败");
    const data = await response.json();
    renderSources(data.sources?.length ? data.sources : FALLBACK_SOURCES);
  } catch (_error) {
    renderSources(FALLBACK_SOURCES);
  }
}

function shortDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("zh-CN", { month: "short", day: "numeric" }).format(date);
}

function repoCard(repository) {
  const tags = (repository.matched_interests || [])
    .map((item) => `<span>${escapeHtml(item)}</span>`)
    .join("");
  const risk = repository.risk_note
    ? `<p class="risk">注意：${escapeHtml(repository.risk_note)}</p>`
    : "";
  return `
    <article class="signal-card repo-card">
      <div class="rank-column"><span class="rank-label">PICK</span><strong>${String(repository.rank || 0).padStart(2, "0")}</strong><span class="match-score">${escapeHtml(repository.relevance_score)}<small>/100</small></span></div>
      <div class="signal-content">
        <div class="signal-topline"><span class="recommendation">${escapeHtml(repository.recommendation)}</span><span class="source-rank">TRENDING #${escapeHtml(repository.trending_rank)}</span></div>
        <h4><a href="${escapeHtml(repository.url)}" target="_blank" rel="noreferrer">${escapeHtml(repository.full_name)} <span>↗</span></a></h4>
        <p class="why">${escapeHtml(repository.why_for_you)}</p>
        <p class="summary">${escapeHtml(repository.summary || repository.description)}</p>
        <div class="metric-row"><span><b>★ ${number(repository.stars)}</b> total</span><span><b>+${number(repository.stars_today)}</b> today</span><span><b>${escapeHtml(repository.language || "Unknown")}</b> language</span><span><b>${escapeHtml(repository.license || "Unknown")}</b> license</span></div>
        ${tags ? `<div class="tag-list">${tags}</div>` : ""}${risk}
      </div>
    </article>`;
}

function rssCard(item) {
  const tags = (item.matched_keywords || [])
    .map((keyword) => `<span>${escapeHtml(keyword)}</span>`)
    .join("");
  const status = item.analysis_status === "ai" ? "AI ANALYZED" : "RULE RANKED";
  return `
    <article class="signal-card rss-card">
      <div class="rank-column paper-rank"><span class="rank-label">SIGNAL</span><strong>${String(item.rank || 0).padStart(2, "0")}</strong><span class="match-score">${escapeHtml(item.relevance_score)}<small>/10</small></span></div>
      <div class="signal-content">
        <div class="signal-topline"><span class="recommendation paper-status">${status}</span><span class="source-rank">${escapeHtml(item.source_name)} · ${escapeHtml(shortDate(item.published_at))}</span></div>
        <h4><a href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">${escapeHtml(item.title)} <span>↗</span></a></h4>
        <p class="why">${escapeHtml(item.recommendation_reason)}</p>
        <p class="summary">${escapeHtml(item.summary)}</p>
        <div class="metric-row"><span><b>${escapeHtml(item.relevance_score)}/10</b> relevance</span><span><b>${escapeHtml(item.innovation_score)}/10</b> innovation</span></div>
        ${tags ? `<div class="tag-list">${tags}</div>` : ""}
      </div>
    </article>`;
}

function channelSection(channel) {
  if (!channel.items?.length) return "";
  const presentation = SOURCE_PRESENTATION[channel.id] || { icon: "RSS" };
  return `
    <div class="result-channel">
      <div class="channel-title"><span class="channel-icon">${escapeHtml(presentation.icon)}</span><h3>${escapeHtml(channel.title)}</h3><span class="channel-scan">扫描 ${number(channel.scanned_count)} 条${channel.errors_count ? ` · ${number(channel.errors_count)} 个源异常` : ""}</span><i></i></div>
      <div class="result-list">${channel.items.map(rssCard).join("")}</div>
    </div>`;
}

document.querySelectorAll(".reveal-key").forEach((button) => {
  button.addEventListener("click", () => {
    const input = document.getElementById(button.dataset.target);
    const showing = input.type === "text";
    input.type = showing ? "password" : "text";
    button.textContent = showing ? "显示" : "隐藏";
  });
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  formError.hidden = true;
  results.hidden = true;
  githubResults.hidden = true;
  emptyResult.hidden = true;
  resultList.innerHTML = "";
  channelResults.innerHTML = "";

  const sources = selectedSources();
  const interests = parseInterests(document.querySelector("#interests").value);
  if (!sources.length) {
    formError.textContent = "请至少选择一个情报频道。";
    formError.hidden = false;
    return;
  }
  if (!interests.length) {
    formError.textContent = "请至少填写一个关注词。";
    formError.hidden = false;
    return;
  }

  const payload = {
    interests,
    sources,
    language: document.querySelector("#language").value,
    github_token: document.querySelector("#github-token").value.trim() || null,
    ai_base_url: document.querySelector("#ai-base-url").value.trim(),
    ai_model: document.querySelector("#ai-model").value.trim(),
    ai_api_key: document.querySelector("#ai-api-key").value.trim() || null,
  };

  submitButton.disabled = true;
  loading.hidden = false;
  loading.scrollIntoView({ behavior: "smooth", block: "center" });

  try {
    const response = await fetch("/api/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) {
      const detail = Array.isArray(data.detail)
        ? data.detail.map((item) => item.msg).join("；")
        : data.detail;
      throw new Error(detail || "暂时无法生成情报。");
    }

    const totalScanned = Number(data.scanned_count || 0) + Number(data.rss_scanned_count || 0);
    scanSummary.textContent = `已扫描 ${number(totalScanned)} 条候选 · ${data.used_ai ? "AI 增强分析" : "本地规则分析"}`;
    if (data.repositories?.length) {
      resultList.innerHTML = data.repositories.map(repoCard).join("");
      githubResults.hidden = false;
    }
    channelResults.innerHTML = (data.channels || []).map(channelSection).join("");
    const hasRssItems = (data.channels || []).some((channel) => channel.items?.length);
    if (!data.repositories?.length && !hasRssItems) emptyResult.hidden = false;

    results.hidden = false;
    document.querySelector("#github-token").value = "";
    document.querySelector("#ai-api-key").value = "";
    results.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    formError.textContent = error.message || "暂时无法生成情报。";
    formError.hidden = false;
    form.scrollIntoView({ behavior: "smooth", block: "start" });
  } finally {
    loading.hidden = true;
    submitButton.disabled = false;
  }
});

loadSources();
