const form = document.querySelector("#preview-form");
const submitButton = document.querySelector("#submit-button");
const loading = document.querySelector("#loading");
const results = document.querySelector("#results");
const resultList = document.querySelector("#result-list");
const emptyResult = document.querySelector("#empty-result");
const scanSummary = document.querySelector("#scan-summary");
const formError = document.querySelector("#form-error");

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

function repoCard(repository) {
  const tags = (repository.matched_interests || [])
    .map((item) => `<span>${escapeHtml(item)}</span>`)
    .join("");
  const risk = repository.risk_note
    ? `<p class="risk">注意：${escapeHtml(repository.risk_note)}</p>`
    : "";
  return `
    <article class="repo-card">
      <div class="rank-rail">
        <span class="rank-number">${escapeHtml(repository.rank)}</span>
        <span class="score">MATCH ${escapeHtml(repository.relevance_score)}/100</span>
      </div>
      <div class="repo-content">
        <div class="repo-topline">
          <div>
            <span class="recommendation">${escapeHtml(repository.recommendation)}</span>
            <h3 class="repo-name">
              <a href="${escapeHtml(repository.url)}" target="_blank" rel="noreferrer">
                ${escapeHtml(repository.full_name)} ↗
              </a>
            </h3>
          </div>
        </div>
        <p class="why">${escapeHtml(repository.why_for_you)}</p>
        <p class="summary">${escapeHtml(repository.summary || repository.description)}</p>
        <div class="repo-meta">
          <span>★ ${number(repository.stars)}</span>
          <span>今日 +${number(repository.stars_today)}</span>
          <span>${escapeHtml(repository.language || "Unknown")}</span>
          <span>${escapeHtml(repository.license || "许可证未知")}</span>
          <span>Trending #${escapeHtml(repository.trending_rank)}</span>
        </div>
        ${tags ? `<div class="tag-list">${tags}</div>` : ""}
        ${risk}
      </div>
    </article>`;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  formError.hidden = true;
  results.hidden = true;
  emptyResult.hidden = true;
  resultList.innerHTML = "";

  const interests = parseInterests(document.querySelector("#interests").value);
  if (!interests.length) {
    formError.textContent = "请至少填写一个关注词。";
    formError.hidden = false;
    return;
  }

  const payload = {
    interests,
    language: document.querySelector("#language").value,
    ai_base_url: document.querySelector("#ai-base-url").value,
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
      throw new Error(detail || "暂时无法生成预览。");
    }

    scanSummary.textContent = `已扫描 ${number(data.scanned_count)} 个候选 · ${
      data.used_ai ? "AI 摘要" : "本地摘要"
    }`;
    if (data.repositories.length) {
      resultList.innerHTML = data.repositories.map(repoCard).join("");
    } else {
      emptyResult.hidden = false;
    }
    results.hidden = false;
    document.querySelector("#ai-api-key").value = "";
    results.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    formError.textContent = error.message || "暂时无法生成预览。";
    formError.hidden = false;
    form.scrollIntoView({ behavior: "smooth", block: "start" });
  } finally {
    loading.hidden = true;
    submitButton.disabled = false;
  }
});
