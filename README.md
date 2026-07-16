# 📡 RepoCourier

> 一个主打检索快、检索全的技术舆情雷达。

🔥 GitHub Trending · 📰 科技新闻 · 🏢 大厂博客 · 🎓 学术论文 · 🚀 产品更新 · 🛡️ 安全资讯

<p align="center">
  <img src="assets/Repo-readme.png" alt="RepoCourier 技术舆情雷达" width="70%">
</p>

## ⚡ 快速开始

### 1️⃣ 安装

开始前请准备 Python 3.10+ 和 [uv](https://docs.astral.sh/uv/)。

```bash
git clone https://github.com/jjyaoao/repo-courier.git
cd repo-courier
uv sync
```

### 2️⃣ 配置环境变量

```bash
# GitHub API
export GITHUB_TOKEN="your-github-token"

# GitHub Trending 与 RSS 专题共用的大模型
export REPO_LLM_API_KEY="your-key"
export REPO_LLM_BASE_URL="https://api.openai.com/v1/chat/completions"
export REPO_LLM_MODEL="your-model"

# 可选：临时覆盖关注词
export REPO_COURIER_INTERESTS="agent,llm,mcp,security"
```

### 3️⃣ 一键探索

运行全部信息源：

```bash
uv run repo-courier \
  --channels all \
  --dry-run
```
> [!NOTE]
> 不传 `--date`，默认检索时间为昨天。

## ⚙️ 配置

主要配置位于 [`config/config.yaml`](config/config.yaml)，可以设置默认启用的通道、关注词、
排除词、RSS 来源和候选数量。

- `github.enabled`：是否默认运行 GitHub Trending。
- `rss.channels.<channel>.enabled`：是否默认运行对应 RSS 专题。
- `profile.interests`：关键词排序使用的关注词。
- `profile.exclude_keywords`：命中后直接排除的关键词。
- `rss.channels.<channel>.sources`：对应专题的 RSS 或 Atom 来源。

## ▶️ 运行

完整命令示例：

```bash
uv run repo-courier \
  --config config/config.yaml \
  --channels github,news,blogs,academic,products,security \
  --date 2026-07-15 \
  --dry-run \
  --verbose
```

命令及参数说明：

- `uv run repo-courier`：在项目的 uv 环境中启动 RepoCourier。
- `--config config/config.yaml`：指定 YAML 配置文件路径。
- `--channels github,news,blogs,academic,products,security`：仅运行列出的通道；使用 `all` 运行全部六个通道。
- `--date 2026-07-15`：筛选指定北京时间自然日内的 RSS 内容。
- `--dry-run`：只生成报告，不发送消息推送。
- `--verbose`：输出详细运行日志，便于排查抓取和分析问题。

> [!NOTE]
> 未传 `--channels` 时，RepoCourier 使用 [`config/config.yaml`](config/config.yaml) 中的默认配置决定运行源。

## 📊 运行结果

报告会写入以下目录：

```text
reports/YYYY-MM-DD/daily.md
reports/YYYY-MM-DD/daily.html
reports/YYYY-MM-DD/daily.json
```

## 📣 推送

- 支持飞书、企业微信、Server酱和 OneBot。
- Webhook 与密钥通过环境变量配置，详见 [`.env.example`](.env.example)。
> [!TIP]
> 开启推送时禁用 `--dry-run` 参数。

## 🌐 Web Beta

Web Beta 仅提供 GitHub Trending 预览，不运行 RSS 专题：

```bash
pip install -e '.[web]'
repo-courier-web
```
