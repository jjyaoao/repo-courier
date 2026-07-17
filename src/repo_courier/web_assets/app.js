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
const emptyResultTitle = document.querySelector("#empty-result-title");
const emptyResultDescription = document.querySelector("#empty-result-description");
const scanSummary = document.querySelector("#scan-summary");
const formError = document.querySelector("#form-error");
const keyList = document.querySelector(".key-list");
const wechatKeyPanel = document.querySelector("#wechat-key-panel");
const wechatKeyInput = document.querySelector("#wechat-auth-key");
const wechatKeySummary = document.querySelector("#wechat-key-summary");
const wechatKeyAction = document.querySelector("#wechat-key-action");
const wechatKeyNote = document.querySelector("#wechat-key-note");
const aiProviderSelect = document.querySelector("#ai-provider");
const aiBaseUrlInput = document.querySelector("#ai-base-url");
const aiModelInput = document.querySelector("#ai-model");
const aiCompatibilityNote = document.querySelector("#ai-compatibility-note");
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

const AI_PROVIDERS = {
  openai: { label: "OpenAI", baseUrl: "https://api.openai.com/v1", model: "" },
  claude: { label: "Claude", baseUrl: "https://api.anthropic.com/v1", model: "claude-sonnet-4-6" },
  zhipu: { label: "智谱 GLM", baseUrl: "https://open.bigmodel.cn/api/paas/v4", model: "glm-5.2" },
  kimi: { label: "Kimi", baseUrl: "https://api.moonshot.cn/v1", model: "kimi-k2.6" },
  minimax: { label: "MiniMax", baseUrl: "https://api.minimaxi.com/v1", model: "MiniMax-M2.7" },
  stepfun: { label: "阶跃星辰", baseUrl: "https://api.stepfun.com/v1", model: "step-3.5-flash" },
};

const FALLBACK_SOURCES = [
  { id: "wechat", title: "微信公众号", source_count: 6, default: false, requires_key: true },
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

function comparableAiBaseUrl(value) {
  return value.trim().replace(/\/+$/, "").replace(/\/chat\/completions$/, "");
}

function updateAiProviderNote() {
  const provider = AI_PROVIDERS[aiProviderSelect.value];
  aiCompatibilityNote.textContent = provider
    ? `已适配 ${provider.label} 的 Chat Completions 接口；仍可修改模型名称。`
    : "自定义地址需在启动时加入 REPO_COURIER_ALLOWED_AI_BASE_URLS；页面会自动补全 /chat/completions。";
}

aiProviderSelect.addEventListener("change", () => {
  const provider = AI_PROVIDERS[aiProviderSelect.value];
  if (provider) {
    aiBaseUrlInput.value = provider.baseUrl;
    aiModelInput.value = provider.model;
  } else {
    aiBaseUrlInput.focus();
  }
  updateAiProviderNote();
});

aiBaseUrlInput.addEventListener("input", () => {
  const current = comparableAiBaseUrl(aiBaseUrlInput.value);
  const matched = Object.entries(AI_PROVIDERS).find(
    ([, provider]) => comparableAiBaseUrl(provider.baseUrl) === current,
  );
  aiProviderSelect.value = matched?.[0] || "custom";
  updateAiProviderNote();
});

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
  const wechatSource = sources.find((source) => source.id === "wechat");
  const hasServerWechatKey = Boolean(wechatSource && !wechatSource.requires_key);
  wechatKeyPanel.hidden = !wechatSource;
  wechatKeyPanel.open = false;
  keyList.classList.toggle("without-wechat", !wechatSource);
  wechatKeySummary.textContent = hasServerWechatKey
    ? "已有默认 Key，可选填覆盖"
    : "读取预设公众号文章";
  wechatKeyAction.firstChild.textContent = hasServerWechatKey ? "可选 " : "添加 ";
  wechatKeyNote.innerHTML = hasServerWechatKey
    ? "服务端已配置默认 Key；留空即可使用，也可填入你自己的 Key 仅覆盖本次请求。"
    : '选择微信公众号频道时使用。可前往 <a href="https://down.mptext.top/dashboard/api" target="_blank" rel="noreferrer">mptext API 控制台 ↗</a> 获取。';
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

function rssCard(item, channelId) {
  const tags = (item.matched_keywords || [])
    .map((keyword) => `<span>${escapeHtml(keyword)}</span>`)
    .join("");
  const status = item.analysis_status === "ai" ? "AI 精选" : "规则精选";
  const inlineSummary = item.analysis_status === "ai" ? "" : `<p class="summary">${escapeHtml(item.summary)}</p>`;
  const date = shortDate(item.published_at);
  const isWechat = channelId === "wechat";
  const sourceMeta = isWechat
    ? `<span class="wechat-source"><i>公众号</i><strong>${escapeHtml(item.source_name)}</strong>${date ? `<small>${escapeHtml(date)}</small>` : ""}</span>`
    : `<span class="source-rank">${escapeHtml(item.source_name)}${date ? ` · ${escapeHtml(date)}` : ""}</span>`;
  return `
    <article class="signal-card rss-card${isWechat ? " wechat-card" : ""}">
      <div class="signal-content">
        <div class="signal-topline"><span class="pick-index paper-index">${String(item.rank || 0).padStart(2, "0")}</span><span class="recommendation paper-status">${status}</span>${sourceMeta}</div>
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
    <div class="result-channel${channel.id === "wechat" ? " wechat-channel" : ""}">
      <div class="channel-title"><span class="channel-icon">${escapeHtml(presentation.icon)}</span><h3>${escapeHtml(channel.title)}</h3><span class="channel-scan">扫描 ${number(channel.scanned_count)} 条${channel.errors_count ? ` · ${number(channel.errors_count)} 个源异常` : ""}</span><i></i></div>
      <div class="result-list">${channel.items.map((item) => rssCard(item, channel.id)).join("")}</div>
    </div>`;
}

function prioritizeSources(sources) {
  const priority = { wechat: 0, github: 1 };
  return sources
    .map((source, index) => ({ source, index }))
    .sort((left, right) =>
      (priority[left.source.id] ?? 2) - (priority[right.source.id] ?? 2) || left.index - right.index,
    )
    .map(({ source }) => source);
}

function resetProgress(sources) {
  const orderedSources = prioritizeSources(sources);
  progressTitle.textContent = `正在处理 0 / ${orderedSources.length} 个频道`;
  progressSummary.textContent = `0 / ${orderedSources.length}`;
  channelProgress.innerHTML = orderedSources
    .map((source) => {
      const title = source.title || sourceCatalog.get(source.id)?.title || source.id;
      return `<span id="progress-${escapeHtml(source.id)}" class="progress-chip"><i></i><b>${escapeHtml(title)}</b><small class="progress-status">等待中</small></span>`;
    })
    .join("");
  channelResults.innerHTML = orderedSources
    .map((source) => `<div id="channel-slot-${escapeHtml(source.id)}"></div>`)
    .join("");
  const githubSlot = document.getElementById("channel-slot-github");
  if (githubSlot) githubSlot.append(githubResults);
}

function updateProgress(source, state, label) {
  const chip = document.getElementById(`progress-${source}`);
  if (!chip) return;
  chip.className = `progress-chip is-${state}`;
  chip.title = state === "error" ? label : "";
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
  emptyResultTitle.textContent = "今天没有足够相关的信号";
  emptyResultDescription.textContent = "可以放宽关注词，或选择更多频道后重试。";
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
    ai_base_url: aiBaseUrlInput.value.trim(),
    ai_model: aiModelInput.value.trim(),
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
    const failureMessages = [];

    await readNdjson(response, (streamEvent) => {
      if (streamEvent.type === "start") {
        total = Number(streamEvent.total || total);
        resetProgress(streamEvent.sources || []);
        return;
      }
      if (streamEvent.type === "channel_started") {
        const status = streamEvent.source === "wechat" && streamEvent.credential_source === "request"
          ? "页面 Key · 抓取中"
          : "抓取中";
        updateProgress(streamEvent.source, "running", status);
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
        const credentialNote = streamEvent.source === "wechat" && streamEvent.credential_source === "request"
          ? "已使用页面填写的 Key；"
          : "";
        const failureMessage = streamEvent.message || "该频道暂时不可用";
        failureMessages.push(`${credentialNote}${failureMessage}`);
        const failureLabel = failureMessage.includes("网络拦截")
          ? "网络已拦截"
          : failureMessage.includes("拒绝访问")
            ? "403 · 访问被拒"
            : "抓取失败";
        updateProgress(streamEvent.source, "error", failureLabel);
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
      if (failed) {
        emptyResultTitle.textContent = failed === total ? "所选频道暂时无法抓取" : "部分频道抓取失败";
        emptyResultDescription.textContent = [...new Set(failureMessages)].join("；");
      }
      emptyResult.hidden = false;
      results.hidden = false;
    }
    document.querySelector("#github-token").value = "";
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
