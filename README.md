📮 RepoCourier

> 每天从 GitHub Trending、学术数据库和科技大厂官方 RSS 中，挑出真正与你有关的内容。

GitHub Trending 很热闹，但你真正关心的通常只有几个。RepoCourier 根据你的关注词重新排序榜单，给出 `深挖 / 关注 / 略过` 判断，并解释为什么这个项目适合你。没有足够相关的项目时宁缺毋滥，不会为了凑数而推送。

Academic 是默认关闭的可选扩展：它与 GitHub 独立处理，只在最终日报和推送摘要中合并。首个支持的学术子源是 ArXiv，默认检索北京时间昨天 00:00:00～23:59:59 提交的论文。

Tech Blog 与 Tech News 同样是两条独立流水线：前者从 10 个官方技术源中最多选 5 篇，后者从 4 个官方新闻源中最多选 3 篇。两类当前共用 `profile` 关键词，先进行透明的规则初筛，再使用 Academic 的模型配置进行语义精筛；模型不可用时自动回退到规则分。

```text
1. [深挖 86/100] owner/agent-tool · 今日 +1,208 ⭐
   为什么：命中你的关注词 agent、mcp；项目提供可自托管方案。

2. [关注 57/100] owner/dev-cli · 今日 +680 ⭐
   为什么：命中你的关注词 developer tools、automation。

3. [关注 43/100] owner/local-app · 今日 +390 ⭐
   为什么：命中你的关注词 self-hosted。
```

少看榜单，多看真正与你有关的项目。

## 它只专注一件事

RepoCourier 会抓取 GitHub Trending 候选项目，然后使用下面这些透明信号进行个性化排序：

- 项目名称和 GitHub Topics 是否命中你的关注词
- 项目描述和 README 是否相关
- 今日 Star 增长和 Trending 原始排名
- 是否命中你不想看的内容
- 是否能识别出开源许可证

匹配度是“与你相关的程度”，不是项目质量的绝对评分。没有 AI 密钥也可以完成这一步。

## 三步开始

要求 Python 3.10 及以上。

```bash
git clone https://github.com/jjyaoao/repo-courier.git
cd repo-courier
python -m venv .venv
source .venv/bin/activate
pip install .
```

### 1. 写下关注词并配置模型参数

编辑 [`config/config.yaml`](config/config.yaml)：

```yaml
profile:
  interests: [agent, llm, mcp, developer tools, automation, self-hosted]
  exclude_keywords: [awesome list, interview, tutorial collection]
  daily_picks: 3

academic:
  enabled: true
  base_url: https://www.example.cn/v1/chat/completions
  model: glm-5
  verify_ssl: true
```

推荐使用 GitHub 仓库描述和 Topics 中常见的英文关键词。也可以临时通过环境变量覆盖：

```bash
export REPO_COURIER_INTERESTS="rust,cli,database,self-hosted"
```

如果启用 Academic，添加用于论文分析的 API Key：

```bash
export ACADEMIC_API_KEY="sk-xxxxxxxxxxxxxxxx"
```

### 2. 先看一次结果

```bash
repo-courier --dry-run
# 指定 Academic 检索的北京时间自然日
repo-courier --date 2026-07-12 --dry-run
```

结果会写入：

```text
reports/YYYY-MM-DD/daily.md
reports/YYYY-MM-DD/daily.html
reports/YYYY-MM-DD/daily.json
```

### 3. 选择一个推送方式

敏感信息全部通过环境变量配置：

| 渠道              | 环境变量                                                  |
| ----------------- | --------------------------------------------------------- |
| 飞书机器人        | `FEISHU_WEBHOOK`                                        |
| 企业微信群机器人  | `WECOM_WEBHOOK`                                         |
| 个人微信 Server酱 | `SERVERCHAN_SENDKEY`                                    |
| 个人 QQ OneBot    | `ONEBOT_URL`、`ONEBOT_USER_ID`，可选 `ONEBOT_TOKEN` |

例如：

```bash
export FEISHU_WEBHOOK="https://open.feishu.cn/open-apis/bot/v2/hook/..."
repo-courier
```

没有配置推送通道时，RepoCourier 仍会正常生成报告。

## Web Beta

RepoCourier 包含一个可选的轻量网页：用户写下关注词后，立即生成一次今日个性化三选。排序不依赖 AI；如果用户选择填写模型密钥，密钥只存在于本次请求内存中，不会写入报告、日志、数据库或浏览器存储。

本地启动：

```bash
pip install -e '.[web]'
repo-courier-web
# 打开 http://127.0.0.1:8000
```

公开实例默认只允许 `https://api.openai.com/v1` 作为模型地址，避免页面被利用去请求任意内网服务。自托管时可以通过英文逗号扩展白名单：

```bash
export REPO_COURIER_ALLOWED_AI_BASE_URLS="https://api.example.com/v1"
```

使用仓库根目录的 `render.yaml` 可以在 Render 上创建 Web Service。部署时建议配置 `GITHUB_TOKEN`，提高 GitHub API 限额；不要在 Render 环境变量中配置公共的 `AI_API_KEY`，Web Beta 会明确忽略服务端的 AI 密钥。

## 可选 AI 摘要

个性化排序不依赖 AI。配置兼容 OpenAI Chat Completions 的服务后，项目介绍会更自然；调用失败时会自动回退到本地摘要。

```bash
export AI_API_KEY="your-key"
export AI_MODEL="your-model-name"
export ACADEMIC_API_KEY="your-academic-key"
```

GitHub 摘要使用 `summary.base_url` 和 `AI_API_KEY`；Academic、Tech Blog 和 Tech News 分析使用 `academic.base_url` 和独立的 `ACADEMIC_API_KEY` 环境变量。

## 每天自动运行

仓库内置 [GitHub Actions 工作流](.github/workflows/daily.yml)，默认每天北京时间 09:00 执行。Fork 或克隆仓库后，在 `Settings → Secrets and variables → Actions` 添加需要的推送与 AI Secrets 即可。

工作流会：

1. 扫描 GitHub Trending、Tech Blog 和 Tech News 官方 RSS；启用 Academic 后，同时检索指定北京时间自然日的 ArXiv 论文。
2. 四个类别分别筛选和分析，只在最后合并。
3. 只为入选项目读取 README，为初筛论文补充 Introduction，再生成报告并发送到已配置渠道。
4. 把报告和历史快照提交回仓库。

## Docker

```bash
cp .env.example .env
docker compose build
docker compose run --rm courier --dry-run
```

## 为什么不直接搬运 Trending

现有开源项目已经很好地完成了榜单抓取、历史归档或单个平台通知。RepoCourier 不准备重复做一个“大而全”的信息平台，它只解决一个小问题：

> Trending 今天有很多项目，但最多哪 3 个值得我打开？

因此，抓取、AI、报告格式和推送渠道都只是支撑能力；“个性化三选”才是产品本身。

## 技术说明

GitHub Trending 没有官方 API。RepoCourier 从 Trending 页面获取榜单，再通过 GitHub REST API 补充 Topics、许可证、Star、Fork 和 README。历史快照用于展示新上榜和排名变化。

```text
src/repo_courier/
├── trending.py       # Trending 抓取
├── github.py         # GitHub 信息补充
├── personalize.py    # 个性化三选（核心）
├── summary.py        # AI / 本地摘要
├── academic/         # Academic 流水线与 ArXiv 子源
├── feeds.py          # Tech Blog / Tech News RSS 抓取与筛选
├── matching.py       # GitHub 与 RSS 共用的关键词匹配
├── report.py         # Markdown / HTML / JSON
├── pushers/          # 飞书、微信、QQ
└── runner.py         # 流程编排
```

## 开发

```bash
pip install '.[dev]'
pytest
ruff check .
```

## 安全与平台说明

- 不要把 Token、Webhook 或 SendKey 提交到 Git。
- 个人微信没有通用官方机器人接口，Server酱属于第三方服务。
- QQ 推送依赖 OneBot 实现，请遵守相关平台规则。
- 开启 AI 后，仓库公开 README、论文内容及入围 RSS 摘要会发送给所配置的模型服务。

## License

[MIT](LICENSE)
