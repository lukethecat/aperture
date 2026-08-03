# Kimi K3 分析任务包（喂给 Kimi Desktop / Kimi Code 的提示词）

## 角色设定
你是一位资深开源项目顾问 + AI 产品架构师。请对下面这个开源项目做一轮**独立的、批判性的整体改进分析**，不要客套，直接指出问题。

## 项目背景
项目名（候选）：self-evolving-news-engine（改名候选：Paperboy / Kiosk / Scoop / Molt）
定位：一套"会自我进化的新闻引擎"——模拟人读报的新闻发现系统，核心差异化：
1. 反思循环（用户反馈 → 画像版本化 → 可回滚）
2. scan 读报模式（扫版面 → 版面diff → 关键词初筛 → 结构化二验 → 去重入池，LLM 只出现在第三道闸）
3. tape 全生命周期审计（append-only JSONL，7 类记录，可回放任意决策）
4. ECHO 回声模块（带证据主动请示，一字可答，防打扰）
5. 采编审发四段式流水线（collect → edit → review → publish）
6. 一套引擎 × N 垂直（新增垂直只加配置不改引擎）

技术形态：skill-first（SKILL.md 是核心，LLM agent 可直接执行模式），Python 参考实现（纯标准库，LLM 供应商配置化，无 key 可 --dry 纯规则跑），MIT，全英文。

仓库：https://github.com/lukethecat/self-evolving-news-engine
文档：README.md / SKILL.md / DESIGN.md / docs/module-showcase.md / docs/sample-issue.md / docs/naming-options.md

## 项目方已规划的改进方向（请验证 + 补充）
A. 更详尽的项目各模块优势（module showcase）
B. 一期带 tape 决策链的样刊示例（sample issue）
C. 后现代主义（康定斯基风格）视觉装修（logo/banner/social card）
D. 一个感性、易传播的项目名字
E. 成熟度基建（CI/CONTRIBUTING/issue 模板）
F. 60 秒上手（Docker/uv）、taste-profile 词云可视化、进化日志公开页、对比页（vs 静态摘要器/RSS 阅读器/问答 agent）

## 请 K3 回答的问题
1. **定位与命名**：从传播学角度，5 个名字（self-evolving-news-engine / Paperboy / Kiosk / Scoop / Molt）哪个最能打动开发者社区？为什么？有没有更好的新名字建议？
2. **差异化验证**：这套系统的三条差异化（反思循环/scan 模式/tape 审计）在 2026 年的开源生态里是否仍然稀缺？市面（GitHub/Reddit/HN）上最接近的竞品是什么？我们 vs 它们的关键差距表？
3. **批判性短板**：作为独立顾问，你认为这个项目现在最大的 5 个问题是什么？（可包括：定位模糊、上手门槛、文档过度/不足、缺少真实用户证据、命名、视觉、README 叙事、代码质量、生态位等）
4. **样刊设计**：带 tape 决策链的样刊怎么做才最有冲击力？（给出页面结构建议）
5. **视觉**：康定斯基风格对开发者社区是加分还是减分？给出一套具体视觉规范建议（配色/几何元素/字体的具体 hex/形状建议）
6. **增长**：除了 HN/Reddit/X/掘金，2026 年还有什么渠道/玩法能让这类"agent skill"型开源项目获得 star 和采用？（如 agent 生态市场、工具目录、AI-native 社区等）
7. **AI Native 评估**：项目自称 AI Native（agent 自编排 harness 模型），实际做到位了吗？如何更进一步？
8. **产品化建议**：如果要收 100 个真实用户并沉淀 3 个社区贡献的垂直配置，你建议的第一优先级动作是什么？

## 输出格式
一份结构化改进报告（中文即可，供内部讨论）：
1. 结论摘要（3-5 条最重要的发现）
2. 每个问题的回答
3. 按"立即做（1周内）/ 短期（1月）/ 中期（1季）"分类的行动清单
4. 命名最终推荐（1 个 + 理由 + 备选）

---
*备注：本分析用于内部决策；项目对外内容全英文。*
