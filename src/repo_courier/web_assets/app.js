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
const progressTitle = document.querySelector("#progress-title");
const progressSummary = document.querySelector("#progress-summary");
const channelProgress = document.querySelector("#channel-progress");
const sourceCatalog = new Map();

const SOURCE_PRESENTATION = {
  github: { icon: "GH", description: "热门项目、Topics、README 与 Star 增长" },
  news: { icon: "N", description: "MIT Tech Review、The Verge、WIRED 等" },
  blogs: { icon: "B", description: "OpenAI、Google DeepMind、Hugging Face 等" },
  academic: { icon: "aχ", description: "arXiv AI、NLP、CV 与机器学习论文" },
  products: { icon: "P", description: "Codex、Claude Code、Gemini CLI 等发布日志" },
  security: { icon: "S", description: "Krebs、The Hacker News、Google Security 等" },
  wechat: { icon: "微", description: "机器之心、量子位、新智元等公众号文章" },
};

const FALLBACK_SOURCES = [
  { id: "github", title: "GitHub Trending", source_count: 1, default: true },
  { id: "news", title: "科技新闻", source_count: 4, default: false },
  { id: "blogs", title: "大厂博客", source_count: 4, default: false },
  { id: "academic", title: "学术论文", source_count: 1, default: false },
  { id: "products", title: "产品更新", source_count: 4, default: false },
  { id: "security", title: "安全资讯", source_count: 4, default: false },
  { id: "wechat", title: "微信公众号", source_count: 6, default: false, requires_key: true },
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
    description: `${source.source_count || 0} 个 RSS / Atom 信息源`,
  };
  const sourceLabel = `${source.title}，${presentation.description}`;
  const keyHint = source.requires_key
    ? `<small class="source-key-hint" title="需要 API Key">KEY</small>`
    : "";
  return `
    <label class="source-option" title="${escapeHtml(presentation.description)}">
      <input type="checkbox" name="sources" value="${escapeHtml(source.id)}" aria-label="${escapeHtml(sourceLabel)}" ${source.default ? "checked" : ""} />
      <span class="source-checkbox" aria-hidden="true">✓</span>
      <span class="source-title">${escapeHtml(source.title)}</span>${keyHint}
    </label>`;
}

function renderSources(sources) {
  sourceCatalog.clear();
  sources.forEach((source) => sourceCatalog.set(source.id, source));
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

function insightList(title, items) {
  const content = (items || [])
    .filter(Boolean)
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join("");
  if (!content) return "";
  return `<div class="ai-insight"><strong>${title}</strong><ul>${content}</ul></div>`;
}

function repoAiDetails(repository) {
  if (repository.analysis_status !== "ai") return "";
  const summary = repository.summary
    ? `<p class="ai-summary">${escapeHtml(repository.summary)}</p>`
    : "";
  const highlights = insightList("值得关注", repository.highlights);
  const useCases = insightList("适合用在", repository.use_cases);
  const risk = repository.risk_note
    ? `<p class="ai-risk"><strong>采用前留意</strong>${escapeHtml(repository.risk_note)}</p>`
    : "";
  return `
    <details class="ai-details">
      <summary><span><i>AI</i> 深度分析</span><b aria-hidden="true"></b></summary>
      <div class="ai-details-body">
        ${summary}
        ${highlights || useCases ? `<div class="ai-insight-grid">${highlights}${useCases}</div>` : ""}
        ${risk}
      </div>
    </details>`;
}

function repoCard(repository) {
  const tags = (repository.matched_interests || [])
    .map((item) => `<span>${escapeHtml(item)}</span>`)
    .join("");
  const language = String(repository.language || "").trim();
  const license = String(repository.license || "").trim();
  const metrics = [
    Number(repository.stars) > 0 ? `<span><b>★ ${number(repository.stars)}</b> Stars</span>` : "",
    Number(repository.stars_today) > 0 ? `<span><b>+${number(repository.stars_today)}</b> 今日新增</span>` : "",
    language && language.toLowerCase() !== "unknown" ? `<span><b>${escapeHtml(language)}</b></span>` : "",
    license && !["unknown", "noassertion", "other"].includes(license.toLowerCase())
      ? `<span><b>${escapeHtml(license)}</b> 许可证</span>`
      : "",
  ].filter(Boolean).join("");
  return `
    <article class="signal-card repo-card">
      <div class="signal-content">
        <div class="signal-topline"><span class="pick-index">${String(repository.rank || 0).padStart(2, "0")}</span><span class="recommendation">${escapeHtml(repository.recommendation)}</span><span class="source-rank">Trending #${escapeHtml(repository.trending_rank)}</span></div>
        <h4><a href="${escapeHtml(repository.url)}" target="_blank" rel="noreferrer">${escapeHtml(repository.full_name)} <span>↗</span></a></h4>
        <p class="why">${escapeHtml(repository.why_for_you)}</p>
        <p class="summary">${escapeHtml(repository.description || repository.summary)}</p>
        ${metrics ? `<div class="metric-row">${metrics}</div>` : ""}
        ${tags ? `<div class="tag-list">${tags}</div>` : ""}
        ${repoAiDetails(repository)}
      </div>
    </article>`;
}

function rssAiDetails(item) {
  if (item.analysis_status !== "ai") return "";
  const authors = (item.authors || []).filter(Boolean).map(escapeHtml).join("、");
  return `
    <details class="ai-details">
      <summary><span><i>AI</i> 内容摘要</span><b aria-hidden="true"></b></summary>
      <div class="ai-details-body">
        <p class="ai-summary">${escapeHtml(item.summary)}</p>
        ${authors ? `<p class="ai-authors"><strong>作者</strong>${authors}</p>` : ""}
      </div>
    </details>`;
}

function rssCard(item) {
  const tags = (item.matched_keywords || [])
    .map((keyword) => `<span>${escapeHtml(keyword)}</span>`)
    .join("");
  const status = item.analysis_status === "ai" ? "AI 精选" : "规则精选";
  const inlineSummary = item.analysis_status === "ai" ? "" : `<p class="summary">${escapeHtml(item.summary)}</p>`;
  return `
    <article class="signal-card rss-card">
      <div class="signal-content">
        <div class="signal-topline"><span class="pick-index paper-index">${String(item.rank || 0).padStart(2, "0")}</span><span class="recommendation paper-status">${status}</span><span class="source-rank">${escapeHtml(item.source_name)} · ${escapeHtml(shortDate(item.published_at))}</span></div>
        <h4><a href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">${escapeHtml(item.title)} <span>↗</span></a></h4>
        <p class="why">${escapeHtml(item.recommendation_reason)}</p>
        ${inlineSummary}
        ${tags ? `<div class="tag-list">${tags}</div>` : ""}
        ${rssAiDetails(item)}
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

function resetProgress(sources) {
  progressTitle.textContent = `正在处理 0 / ${sources.length} 个频道`;
  progressSummary.textContent = `0 / ${sources.length}`;
  channelProgress.innerHTML = sources
    .map((source) => {
      const title = source.title || sourceCatalog.get(source.id)?.title || source.id;
      return `<span id="progress-${escapeHtml(source.id)}" class="progress-chip"><i></i><b>${escapeHtml(title)}</b><small class="progress-status">等待中</small></span>`;
    })
    .join("");
  channelResults.innerHTML = sources
    .filter((source) => source.id !== "github")
    .map((source) => `<div id="channel-slot-${escapeHtml(source.id)}"></div>`)
    .join("");
}

function updateProgress(source, state, label) {
  const chip = document.getElementById(`progress-${source}`);
  if (!chip) return;
  chip.className = `progress-chip is-${state}`;
  const status = chip.querySelector(".progress-status");
  if (status) status.textContent = label;
}

function renderChannelResult(source, data) {
  let itemCount = 0;
  if (source === "github" && data.repositories?.length) {
    resultList.innerHTML = data.repositories.map(repoCard).join("");
    githubResults.hidden = false;
    itemCount += data.repositories.length;
  }
  (data.channels || []).forEach((channel) => {
    const slot = document.getElementById(`channel-slot-${channel.id}`);
    if (slot) slot.innerHTML = channelSection(channel);
    itemCount += channel.items?.length || 0;
  });
  return itemCount;
}

async function readNdjson(response, onEvent) {
  if (!response.body) throw new Error("当前浏览器不支持流式结果读取。");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      if (line.trim()) onEvent(JSON.parse(line));
    }
    if (done) break;
  }
  if (buffer.trim()) onEvent(JSON.parse(buffer));
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
  const wechatKeyInput = document.querySelector("#wechat-auth-key");
  const wechatNeedsKey = sources.includes("wechat") && sourceCatalog.get("wechat")?.requires_key;
  if (wechatNeedsKey && !wechatKeyInput.value.trim()) {
    document.querySelector("#wechat-key-panel").open = true;
    formError.textContent = "微信公众号频道需要 API Key，请在可选增强中填写。";
    formError.hidden = false;
    wechatKeyInput.focus();
    return;
  }

  const payload = {
    interests,
    sources,
    language: document.querySelector("#language").value,
    github_token: document.querySelector("#github-token").value.trim() || null,
    wechat_auth_key: wechatKeyInput.value.trim() || null,
    ai_base_url: document.querySelector("#ai-base-url").value.trim(),
    ai_model: document.querySelector("#ai-model").value.trim(),
    ai_api_key: document.querySelector("#ai-api-key").value.trim() || null,
  };

  submitButton.disabled = true;
  loading.hidden = false;
  resetProgress(
    sources.map((source) => ({ id: source, title: sourceCatalog.get(source)?.title || source })),
  );
  loading.scrollIntoView({ behavior: "smooth", block: "center" });

  try {
    const response = await fetch("/api/preview/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const data = await response.json();
      const detail = Array.isArray(data.detail)
        ? data.detail.map((item) => item.msg).join("；")
        : data.detail;
      throw new Error(detail || "暂时无法生成情报。");
    }

    let processed = 0;
    let failed = 0;
    let total = sources.length;
    let totalScanned = 0;
    let usedAi = false;
    let hasItems = false;
    let revealedResults = false;
    let streamCompleted = false;

    await readNdjson(response, (streamEvent) => {
      if (streamEvent.type === "start") {
        total = Number(streamEvent.total || total);
        resetProgress(streamEvent.sources || []);
        return;
      }
      if (streamEvent.type === "channel_started") {
        updateProgress(streamEvent.source, "running", "抓取中");
        return;
      }
      if (streamEvent.type === "channel_complete") {
        processed += 1;
        const data = streamEvent.result || {};
        const itemCount = renderChannelResult(streamEvent.source, data);
        hasItems = hasItems || itemCount > 0;
        totalScanned += Number(data.scanned_count || 0) + Number(data.rss_scanned_count || 0);
        usedAi = usedAi || Boolean(data.used_ai);
        updateProgress(streamEvent.source, "done", `${itemCount} 条`);
        progressTitle.textContent = `正在处理 ${processed} / ${total} 个频道`;
        progressSummary.textContent = `${processed} / ${total}`;
        scanSummary.textContent = `已完成 ${processed} / ${total} · 扫描 ${number(totalScanned)} 条候选`;
        if (itemCount > 0) {
          results.hidden = false;
          if (!revealedResults) {
            revealedResults = true;
            results.scrollIntoView({ behavior: "smooth", block: "start" });
          }
        }
        return;
      }
      if (streamEvent.type === "channel_error") {
        processed += 1;
        failed += 1;
        updateProgress(streamEvent.source, "error", "暂不可用");
        progressTitle.textContent = `正在处理 ${processed} / ${total} 个频道`;
        progressSummary.textContent = `${processed} / ${total}`;
        return;
      }
      if (streamEvent.type === "complete") {
        streamCompleted = true;
        failed = Number(streamEvent.failed || failed);
        progressTitle.textContent = failed ? `已完成，${failed} 个频道暂不可用` : "今日情报已生成";
        scanSummary.textContent = `已扫描 ${number(totalScanned)} 条候选 · ${usedAi ? "AI 增强分析" : "本地规则分析"}${failed ? ` · ${failed} 个频道异常` : ""}`;
      }
    });

    if (!streamCompleted) throw new Error("流式连接提前结束，请重试。");
    if (!hasItems) {
      emptyResult.hidden = false;
      results.hidden = false;
    }
    document.querySelector("#github-token").value = "";
    wechatKeyInput.value = "";
    document.querySelector("#ai-api-key").value = "";
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
