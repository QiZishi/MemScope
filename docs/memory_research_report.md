# AI Agent 记忆模块前沿研究报告

> 搜索时间：2026年4月28日 | 范围：2026年3月以来的arXiv论文 + GitHub高星开源项目
> 搜索关键词：agent memory, LLM memory, episodic memory, procedural memory, memory augmentation, test-time learning

---

## 一、arXiv 论文（2026年3月以来，聚焦记忆模块）

| # | 论文标题 | arXiv ID | 发布日期 | 记忆架构类型 | 核心创新 | 企业场景相关性 |
|---|---------|----------|---------|-------------|---------|--------------|
| 1 | **ZenBrain: A Neuroscience-Inspired 7-Layer Memory Architecture for Autonomous AI Systems** | 2604.23878 | 2026-04-26 | 多层生物启发式记忆 | 首次将神经科学的记忆巩固(consolidation)、遗忘(forgetting)、再巩固(reconsolidation)原理整合到AI记忆系统，提出7层架构 | ⭐⭐⭐⭐⭐ **极高** - 直接支持个人偏好记忆（通过遗忘曲线管理）和团队知识衰减监控，多层架构可映射为：感知→工作记忆→情景→语义→程序→长期巩固 |
| 2 | **Graph Memory Transformer (GMT)** | 2604.23862 | 2026-04-26 | 图结构记忆替换FFN | 将Transformer的FFN子层替换为显式学习的记忆图(memory graph)，保持自回归架构不变 | ⭐⭐⭐⭐ **高** - 图结构记忆天然适合企业知识图谱，可编码团队协作关系和知识依赖 |
| 3 | **MEMCoder: Multi-dimensional Evolving Memory for Private-Library-Oriented Code Generation** | 2604.24222 | 2026-04-27 | 多维演化记忆 | 针对企业私有库代码生成，提出多维演化记忆系统，克服静态RAG的局限 | ⭐⭐⭐⭐⭐ **极高** - 直接面向企业场景，解决内部私有库代码记忆问题，可扩展为团队编程习惯记忆 |
| 4 | **Cortex-Inspired Continual Learning: Functional Task Networks (FTN)** | 2604.24637 | 2026-04-27 | 参数隔离+任务网络 | 无需任务标签即可自动推断当前输入匹配的历史任务解决方案，防灾难性遗忘 | ⭐⭐⭐⭐ **高** - 适用于Agent在多任务间的持续学习，可防止团队知识遗忘 |
| 5 | **A Parametric Memory Head for Continual Generative Retrieval** | 2604.23388 | 2026-04-25 | 参数化记忆头 | 将文档ID直接解码的生成式检索扩展到动态文档集合，支持持续更新 | ⭐⭐⭐⭐ **高** - 可用于企业知识库的持续更新检索，避免索引重建 |
| 6 | **ClawMark: A Living-World Benchmark for Multi-Turn, Multi-Day, Multimodal Coworker Agents** | 2604.23781 | 2026-04-26 | 持久化多日协作记忆 | 多轮、多天、多模态协作Agent基准，模拟环境随时间独立变化的场景 | ⭐⭐⭐⭐ **高** - 直接模拟企业工作场景中信息持续变化（邮件、日历、知识库更新） |
| 7 | **Skill Retrieval Augmentation for Agentic AI** | 2604.24594 | 2026-04-27 | 技能检索记忆 | 将Agent技能(skill)作为可检索记忆层，支持跨任务复用 | ⭐⭐⭐⭐ **高** - 团队知识和技能的程序性记忆架构参考 |

---

## 二、GitHub 开源项目（按星标数排序，1000+ stars）

### A. 核心记忆框架（⭐10,000+）

| # | 项目名称 | Stars | 创建时间 | 记忆架构类型 | 核心创新 | 企业场景相关性 |
|---|---------|-------|---------|-------------|---------|--------------|
| 1 | **[mem0ai/mem0](https://github.com/mem0ai/mem0)** | ⭐54,262 | 2023-06-20 | 通用记忆层 | AI Agent通用记忆层，支持语义/情景/用户记忆分离，去重、衰减、优先级排序 | ⭐⭐⭐⭐⭐ 业界标杆，个人偏好记忆首选方案 |
| 2 | **[MemPalace/mempalace](https://github.com/MemPalace/mempalace)** | ⭐50,071 | 2026-04-05 | 基准测试最优记忆系统 | 号称"基准测试最优的开源AI记忆系统"，基于ChromaDB，MCP协议支持 | ⭐⭐⭐⭐⭐ 新发布即爆火，需关注其实际架构细节 |
| 3 | **[volcengine/OpenViking](https://github.com/volcengine/OpenViking)** | ⭐23,169 | 2026-01-05 | 上下文数据库（文件系统范式） | 火山引擎出品，统一管理Agent的记忆、资源、技能，文件系统范式实现分层上下文 | ⭐⭐⭐⭐⭐ 字节跳动级工程实践，企业级上下文管理参考 |
| 4 | **[letta-ai/letta](https://github.com/letta-ai/letta)** | ⭐22,343 | 2023-10-11 | 有状态Agent+高级记忆 | 原MemGPT，构建有状态Agent的平台，支持记忆学习和自我改进 | ⭐⭐⭐⭐⭐ 学术论文支撑，记忆管理最成熟 |
| 5 | **[memvid/memvid](https://github.com/memvid/memvid)** | ⭐15,225 | 2025-05-27 | 视频编码记忆层 | 用视频编码替代传统RAG管道，无服务器、单文件记忆层 | ⭐⭐⭐⭐ 创新性强，但企业适用性待验证 |
| 6 | **[MemoriLabs/Memori](https://github.com/MemoriLabs/Memori)** | ⭐13,946 | 2025-07-24 | Agent原生记忆基础设施 | LLM无关的记忆层，将Agent执行和对话转化为持久记忆 | ⭐⭐⭐⭐⭐ LLM无关设计，适合多模型企业环境 |

### B. 中型记忆框架（⭐1,000-10,000）

| # | 项目名称 | Stars | 创建时间 | 记忆架构类型 | 核心创新 | 企业场景相关性 |
|---|---------|-------|---------|-------------|---------|--------------|
| 7 | **[MemTensor/MemOS](https://github.com/MemTensor/MemOS)** | ⭐8,741 | 2025-07-06 | AI记忆操作系统 | 技能记忆(skill memory)持久化，跨任务技能复用和演进 | ⭐⭐⭐⭐⭐ 程序性记忆的标杆实现，技能复用直接对标企业知识复用 |
| 8 | **[memovai/mimiclaw](https://github.com/memovai/mimiclaw)** | ⭐5,296 | 2026-02-04 | 轻量级边缘记忆 | 在$5芯片上运行的记忆系统，无需操作系统 | ⭐⭐⭐ 边缘场景，企业级适用性有限 |
| 9 | **[EverMind-AI/EverOS](https://github.com/EverMind-AI/EverOS)** | ⭐4,240 | 2025-10-28 | 长期记忆评估+集成 | 自进化Agent的长期记忆构建、评估和集成框架 | ⭐⭐⭐⭐⭐ 提供记忆评估基准，适合企业记忆系统质量保证 |
| 10 | **[MemMachine/MemMachine](https://github.com/MemMachine/MemMachine)** | ⭐3,539 | 2025-08-15 | 通用可扩展记忆层 | 可扩展、可扩展、可互操作的记忆存储 | ⭐⭐⭐⭐ 互操作性设计适合多Agent企业架构 |
| 11 | **[holaboss-ai/holaOS](https://github.com/holaboss-ai/holaOS)** | ⭐3,454 | 2026-03-22 | 开放Agent计算机 | 任意数字工作的开放Agent操作系统 | ⭐⭐⭐⭐ 包含记忆管理的完整Agent OS |
| 12 | **[memodb-io/Acontext](https://github.com/memodb-io/Acontext)** | ⭐3,349 | 2025-07-16 | Agent技能即记忆层 | 将Agent技能(skill)封装为记忆层 | ⭐⭐⭐⭐ 程序性记忆参考，技能=可执行的知识 |
| 13 | **[Gentleman-Programming/engram](https://github.com/Gentleman-Programming/engram)** | ⭐2,918 | 2026-02-16 | 持久化编码Agent记忆 | Go语言实现，SQLite+FTS5，MCP服务器，Agent无关 | ⭐⭐⭐⭐ 高性能、Agent无关，适合企业级部署 |
| 14 | **[breferrari/obsidian-mind](https://github.com/breferrari/obsidian-mind)** | ⭐2,079 | 2026-02-28 | Obsidian知识库记忆 | 用Obsidian知识库为AI编码Agent提供持久记忆 | ⭐⭐⭐ 知识管理创新，但依赖Obsidian |
| 15 | **[rohitg00/agentmemory](https://github.com/rohitg00/agentmemory)** | ⭐2,055 | 2026-02-25 | 基准测试驱动的持久记忆 | 基于真实世界基准测试的AI编码Agent持久记忆 | ⭐⭐⭐⭐ 有基准验证，质量有保证 |
| 16 | **[FlowElement-ai/m_flow](https://github.com/FlowElement-ai/m_flow)** | ⭐1,998 | 2026-03-31 | 生物启发认知记忆引擎 | Graph RAG新范式，语义+情景记忆融合 | ⭐⭐⭐⭐⭐ **极高** - 生物启发式记忆，语义+情景双模态，含Ebbinghaus衰减 |
| 17 | **[zilliztech/memsearch](https://github.com/zilliztech/memsearch)** | ⭐1,488 | 2026-02-09 | 统一持久化记忆层 | 为所有AI Agent提供持久统一记忆层 | ⭐⭐⭐⭐ Zilliz出品，向量数据库技术支撑 |
| 18 | **[ghostwright/phantom](https://github.com/ghostwright/phantom)** | ⭐1,374 | 2026-03-26 | 自进化持久化记忆 | 自有计算机的AI同事，自我进化，持久记忆 | ⭐⭐⭐ 自进化Agent参考 |
| 19 | **[joeynyc/hermes-hudui](https://github.com/joeynyc/hermes-hudui)** | ⭐1,249 | 2026-04-09 | 意识监控UI | 持久记忆AI Agent的Web UI意识监控 | ⭐⭐⭐ 可视化参考 |
| 20 | **[Bitterbot-AI/bitterbot-desktop](https://github.com/Bitterbot-AI/bitterbot-desktop)** | ⭐1,237 | 2026-03-28 | 本地优先情感记忆 | 本地优先AI Agent，持久记忆+情感智能 | ⭐⭐⭐ 情感维度创新 |
| 21 | **[mem9-ai/mem9](https://github.com/mem9-ai/mem9)** | ⭐1,038 | 2026-03-08 | 无限记忆 | 为OpenClaw提供无限记忆 | ⭐⭐⭐ 规模创新 |

### C. 特色记忆项目（与企业场景高度相关）

| # | 项目名称 | Stars | 创建时间 | 记忆架构类型 | 核心创新 | 企业场景相关性 |
|---|---------|-------|---------|-------------|---------|--------------|
| 22 | **[sachitrafa/YourMemory](https://github.com/sachitrafa/YourMemory)** | ⭐187 | 2026-03-02 | Ebbinghaus遗忘曲线衰减记忆 | 实现艾宾浩斯遗忘曲线衰减，LoCoMo基准比Mem0高16个百分点 | ⭐⭐⭐⭐⭐ **直接相关** - 遗忘曲线是Direction D（团队知识遗忘告警）的核心技术 |
| 23 | **[alibaizhanov/mengram](https://github.com/alibaizhanov/mengram)** | ⭐160 | 2026-02-10 | 类人三元记忆（语义+情景+程序） | 类人记忆：语义、情景、程序三模态，经验驱动的程序学习 | ⭐⭐⭐⭐⭐ **直接相关** - 三元记忆模型完美映射企业需求 |
| 24 | **[MemTensor/MemRL](https://github.com/MemTensor/MemRL)** | ⭐98 | 2026-01-12 | 情景记忆强化学习 | 自进化Agent通过运行时强化学习利用情景记忆 | ⭐⭐⭐⭐ Agent从历史经验中学习优化 |
| 25 | **[TeleAI-UAGI/telemem](https://github.com/TeleAI-UAGI/telemem)** | ⭐453 | 2025-12-05 | 高性能记忆替代方案 | Mem0的高性能替代，语义去重+长期对话记忆 | ⭐⭐⭐⭐ 语义去重能力适合企业重复知识管理 |

---

## 三、与企业记忆引擎（Direction C + D）的映射分析

### Direction C：个人工作习惯记忆

| 技术要素 | 推荐参考项目 | 关键技术点 |
|---------|------------|-----------|
| **个人偏好记忆** | mem0 (⭐54K), Memori (⭐14K) | 用户记忆分离、偏好向量化存储 |
| **工作习惯学习** | MemOS (⭐8.7K), mengram (⭐160) | 程序性记忆、经验驱动的技能学习 |
| **使用模式追踪** | Letta/MemGPT (⭐22K), OpenViking (⭐23K) | 有状态Agent、上下文数据库 |
| **个性化调整** | YourMemory (⭐187) | Ebbinghaus遗忘曲线、重要性评分 |

### Direction D：团队知识缺口/遗忘告警

| 技术要素 | 推荐参考项目 | 关键技术点 |
|---------|------------|-----------|
| **知识衰减监控** | YourMemory (⭐187), ZenBrain论文 | 遗忘曲线建模、时间衰减机制 |
| **团队知识图谱** | GMT论文, m_flow (⭐2K) | 图结构记忆、知识关系建模 |
| **知识缺口检测** | EverOS (⭐4.2K), MEMCoder论文 | 记忆评估基准、动态文档集合 |
| **技能复用演化** | MemOS (⭐8.7K), Acontext (⭐3.3K) | 跨任务技能记忆、可执行知识 |

---

## 四、技术趋势总结

1. **生物启发式记忆成为主流**：ZenBrain、m_flow、mengram 等项目将神经科学原理引入AI记忆
2. **遗忘曲线是刚需**：YourMemory、ZenBrain、widemem-ai 等多个项目实现了Ebbinghaus衰减
3. **三元记忆模型（语义+情景+程序）**：mengram、m_flow、MemOS 等采用多模态记忆分离
4. **技能即记忆**：Acontext、MemOS 将Agent技能编码为可检索、可复用的记忆
5. **LLM无关设计**：Memori、MemMachine 等强调与具体LLM解耦，适合企业多模型环境
6. **MCP协议成为记忆接口标准**：MemPalace、m_flow、mem9 等均支持MCP
