# 📮 RepoCourier

> 从 GitHub、科技新闻、大厂博客、学术论文、产品更新和安全资讯中，挑出今天真正与你相关的技术信号。

<p align="center">
  <img src="assets/Repo-readme.png" alt="RepoCourier 个性化技术情报" width="82%">
</p>

RepoCourier 不是又一个大而全的 RSS 阅读器。它先从多个公开信息源收集候选内容，再根据你的关注词去噪、重新排序，每个频道只保留最值得打开的几条。

- **6 个情报频道**：GitHub Trending + 5 个 RSS 专题。
- **18 个上游信息源**：默认配置 17 个 RSS / Atom Feed 和 GitHub Trending。
- **个性化精选**：先用关键词筛选，再可选使用 AI 分析相关性与创新性。
- **没有 AI Key 也能运行**：自动回退到本地规则摘要和排序。
- **报告与推送**：输出 Markdown、HTML、JSON，可推送到飞书、企业微信、个人微信和 QQ。

## 情报来源

| 频道 | 默认信息源 | 挑选方式 |
| --- | --- | --- |
| 🔥 GitHub Trending | GitHub Trending 页面、仓库元数据、Topics 与 README | 关注词 + Star 增长 + Trending 排名 |
| 📰 科技新闻 | MIT Technology Review、The Verge、WIRED、Ars Technica | 新闻价值、相关性与时效性 |
| 🏢 大厂博客 | OpenAI、Google DeepMind、Google AI、Hugging Face | 技术贡献、工程实践与影响范围 |
| 🎓 学术论文 | arXiv AI、NLP、CV 与 Machine Learning | 研究相关性与方法创新性 |
| 🚀 产品更新 | Gemini CLI、OpenAI Codex、Claude Code、OpenClaw Releases | 功能变化、兼容性与实用影响 |
| 🛡️ 安全资讯 | Krebs on Security、The Hacker News、Google Security、安全客 | 风险等级、受影响范围与可操作性 |

信息源不写死在程序中。可以在 [`config/config.yaml`](config/config.yaml) 增删 RSS / Atom Feed，也可以添加新的专题频道。

## 快速开始

需要 Python 3.10+ 和 [uv](https://docs.astral.sh/uv/)。

```bash
git clone https://github.com/jjyaoao/repo-courier.git
cd repo-courier
uv sync
uv run repo-courier --channels all --dry-run
```

`--dry-run` 会生成报告，但不发送消息。不传 `--date` 时，GitHub 获取实时 Trending，RSS 频道检索北京时间昨天的内容。

报告会写入：

```text
reports/YYYY-MM-DD/daily.md
reports/YYYY-MM-DD/daily.html
reports/YYYY-MM-DD/daily.json
```

## 配置你的关注方向

编辑 [`config/config.yaml`](config/config.yaml)：

```yaml
profile:
  interests: [agent, llm, mcp, developer tools, security]
  exclude_keywords: [awesome list, interview, tutorial collection]
  daily_picks: 3
```

推荐使用仓库 Topics、论文关键词和技术新闻中常见的英文词组。也可以临时覆盖：

```bash
export REPO_COURIER_INTERESTS="rust,database,self-hosted,security"
```

## 可选：使用 AI 增强分析

GitHub 摘要和所有 RSS 频道共用一套 OpenAI Chat Completions 兼容配置：

```bash
export REPO_LLM_API_KEY="your-key"
export REPO_LLM_BASE_URL="https://api.openai.com/v1/chat/completions"
export REPO_LLM_MODEL="your-model"
```

API Key 只通过环境变量或 Web 页面的单次请求传入，不要写进 YAML 或提交到 Git。未配置 Key 时，项目会继续使用透明的关键词规则运行。

GitHub Token 也是可选的，用于提高 API 限额和补全仓库信息：

```bash
export GITHUB_TOKEN="your-fine-grained-token"
```

只分析公开仓库时，Fine-grained Token 使用 `Metadata: Read-only` 和 `Contents: Read-only` 即可。

## Web Beta

Web Beta 提供一个简约的单次情报页面：

- 动态读取 GitHub 和 `config.yaml` 中的 RSS 频道。
- 多选情报频道，每个频道最多精选 3 条。
- 可选填写自己的 GitHub Token 与 AI API Key。
- 密钥仅在本次请求内存中使用，不写入报告、日志、数据库或浏览器存储。
- 公共 Web 实例只生成预览，不代替用户发送飞书、微信或 QQ 消息。

本地启动：

```bash
uv sync --extra web
uv run repo-courier-web
# 打开 http://127.0.0.1:8000
```

部署到 Render 时可以使用仓库根目录的 [`render.yaml`](render.yaml)。公开实例必须通过 `REPO_COURIER_ALLOWED_AI_BASE_URLS` 限制允许请求的模型服务，避免任意网址访问。

## 选择频道

```bash
# 只看 GitHub、科技新闻和安全资讯
uv run repo-courier --channels github,news,security --dry-run

# 运行全部频道
uv run repo-courier --channels all --dry-run

# 指定 RSS 检索日期
uv run repo-courier --channels news,blogs --date 2026-07-15 --dry-run
```

不传 `--channels` 时，按 `config.yaml` 中每个频道的 `enabled` 开关运行。可用值为：

```text
github, news, blogs, academic, products, security, all
```

## 每天自动生成和推送

仓库内置 [GitHub Actions 工作流](.github/workflows/daily.yml)。Fork 项目后，在 `Settings → Secrets and variables → Actions` 中添加所需的 Secrets，即可每天生成报告。

| 能力 | Secret |
| --- | --- |
| GitHub 仓库元数据 | `GITHUB_TOKEN` |
| AI 分析 | `REPO_LLM_API_KEY`、`REPO_LLM_BASE_URL`、`REPO_LLM_MODEL` |
| 飞书群机器人 | `FEISHU_WEBHOOK` |
| 企业微信群机器人 | `WECOM_WEBHOOK` |
| 个人微信 Server酱 | `SERVERCHAN_SENDKEY` |
| 个人 QQ OneBot | `ONEBOT_URL`、`ONEBOT_USER_ID`，可选 `ONEBOT_TOKEN` |

公共 Web 页面不接收这些推送凭证。需要长期自动推送时，应将凭证保存在用户自己的 GitHub Actions Secrets 或自托管环境中。

## 工作流程

```text
GitHub Trending / RSS / Atom
              ↓
    日期窗口与关键词去噪
              ↓
      频道内候选排序
              ↓
   可选 AI 相关性分析
              ↓
 Markdown / HTML / JSON 报告
              ↓
 飞书 / 企微 / 微信 / QQ
```

RSS 信息源的某一站失败不会中断其他频道；AI 请求失败也会自动回退到本地规则结果。

## 开发

```bash
uv sync --extra dev --extra web
uv run pytest
uv run ruff check .
```

项目结构：

```text
src/repo_courier/
├── trending.py       # GitHub Trending 抓取
├── github.py         # GitHub 元数据与 README
├── feeds.py          # 统一 RSS / Atom 抓取、分析与排序
├── prompts/          # 各频道 AI 分析提示词
├── personalize.py    # GitHub 个性化排序
├── report.py         # Markdown / HTML / JSON 报告
├── pushers/          # 飞书、企微、Server酱、OneBot
├── web.py            # Web Beta API
└── runner.py         # 全流程编排
```

贡献前请阅读 [`CONTRIBUTING.md`](CONTRIBUTING.md)。

## 安全与平台说明

- 不要将 Token、API Key、Webhook 或 SendKey 提交到 Git。
- 开启 AI 后，公开仓库 README 片段与 RSS 候选内容会发送给所配置的模型服务。
- 个人微信没有通用官方机器人接口，Server酱属于第三方服务。
- QQ 推送依赖 OneBot 实现，请遵守对应平台规则。

## License

[MIT](LICENSE)
