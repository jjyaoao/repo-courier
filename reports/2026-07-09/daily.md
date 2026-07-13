# RepoCourier · 个性化开源速递

> 2026-07-09 · 0 个开源项目 · 3 篇论文

根据你的关注词对 GitHub Trending 重新排序。分数表示与你的匹配程度，不是项目质量的绝对排名。

## GitHub 推荐

## 学术论文

### 1. [TRACE: A Two-Channel Robust Attribution Watermark via Complementary Embeddings for LLM-Agent Trajectories](https://arxiv.org/abs/2607.08400v1)

匹配度 **8/10** · 创新性 **9/10** · 综合分 **15.4**

**研究动机**：LLM代理常通过转售商分发，转售商拥有轨迹日志的完全读写权限，可能进行恶意重包装或模型替换。现有水印方法在面对拥有证据控制权的攻击者时失效，且单一水印机制无法同时抵抗删除攻击（破坏位置键）和重写攻击（破坏内容键），导致归属权争议难以解决。

**核心贡献**：提出TRACE框架，首个针对LLM代理轨迹的无失真、抗删除自同步且抗重写不变的水印方案。设计了双通道机制：基于内容键控的选择通道保证无失真和抗删除，基于位置键控的计数通道保证抗重写。提供了理论证明，确保水印检测的有效性和擦除的高昂成本。引入了LLM重写器攻击，并在ToolBench和ALFWorld上验证了方法的有效性。

**作者**：Zheng Gao、Xiaoyu Li、Xiaoyan Feng、Jiaojiao Jiang、Yang Song · **提交日期**：2026-07-09 · **来源**：ArXiv

### 2. [From Legacy Documentation to OSCAL: An MCP-Based Agent Pipeline for Threat-Informed Continuous Compliance in Critical Infrastructure](https://arxiv.org/abs/2607.08288v1)

匹配度 **10/10** · 创新性 **8/10** · 综合分 **14.8**

**研究动机**：关键基础设施无法进行主动扫描，但需满足严格的合规要求。现有文档是非结构化的，且AI工具存在幻觉风险，无法直接生成可信的审计产物。因此需要一种非侵入式、能减少幻觉并自动化生成合规报告的方法。

**核心贡献**：提出基于MCP的八阶段多智能体流水线，将自然语言文档转换为OSCAL合规制品。通过集成15个MCP服务器实现知识落地，将LLM推理与确定性检索解耦，显著降低幻觉风险。实验表明CVE召回率为0.90，D3FEND召回率为1.00，并提出了针对运营技术的漏洞优先级排序启发式方法。

**作者**：Lea Roxanne Muth、Marian Margraf · **提交日期**：2026-07-09 · **来源**：ArXiv

### 3. [Cognitive-structured Multimodal Agent for Multimodal Understanding, Generation, and Editing](https://arxiv.org/abs/2607.08497v1)

匹配度 **9/10** · 创新性 **8/10** · 综合分 **13.0**

**研究动机**：现有统一多模态模型在长对话中面临视觉标记爆炸和跨轮引用不可靠的瓶颈，单纯参数扩展难以解决。现有智能体缺乏跨轮视觉检索与混合任务编排能力，且纯文本记忆无法处理细粒度视觉细节，限制了长时多模态交互的发展。

**核心贡献**：提出认知结构化多模态智能体，将视觉信息外化至情景记忆，实现按需检索。开发了统一场景引擎生成带检索标注的数据，构建了M2CA-Bench基准。利用强化学习优化感知与检索，使8B模型超越32B基线。发布了集成工具与持久记忆的CMA-Harness部署方案。

**作者**：Feng Wang、Canmiao Fu、Zhipeng Huang、Chen Li、Jing Lyu · **提交日期**：2026-07-09 · **来源**：ArXiv

---

由 [RepoCourier](https://github.com/jjyaoao/repo-courier) 自动生成。
