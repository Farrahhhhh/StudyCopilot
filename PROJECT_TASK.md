# StudyCopilot 项目总任务

你现在是 StudyCopilot 项目的主开发 Agent。

请在当前工作目录中直接创建并持续开发这个项目。

不要只输出教程、架构草图、示例代码或伪代码。在能够安全执行的前提下，请直接：

- 创建项目文件
- 编写代码
- 安装必要依赖
- 初始化 Git
- 初始化数据库
- 运行程序
- 运行测试
- 检查错误
- 修复问题
- 验证当前阶段的功能

我是电子科学与技术相关专业的本科生，不是专业软件开发者。

因此：

- 项目内部可以专业、规范；
- 需要我操作的地方必须写清楚；
- README 必须对非软件专业用户友好；
- 尽量减少需要我手动修改代码；
- 普通工程决策由你自行完成；
- 不要为了展示工程复杂度而过度设计。

---

# 一、项目名称

StudyCopilot

---

# 二、项目定位

StudyCopilot 是一个：

**Local-First、Model-Independent、Context-Aware、拥有长期学习记忆的 Windows 理工科学习助手。**

当前最优先的学习场景是：

- 模拟电子技术
- 模拟电路
- Microelectronic Circuits
- 半导体器件
- 英文 STEM 教材
- 技术论文
- PDF 文献
- 课程讲义

未来也可能用于：

- 信号与系统
- 数字电路
- 电磁场
- 控制
- ArduPilot
- 工程技术文档
- 科研论文
- 其他专业书籍

StudyCopilot 不是新的 PDF 阅读器，也不是普通聊天机器人。

它位于：

```text
教材 / PDF / 浏览器 / 文档
            │
            ↓
      StudyCopilot
            │
      Context + Memory
            │
            ↓
       AI Integration
            │
      ┌─────┴─────┐
      ↓           ↓
   ChatGPT      Claude
```

它主要负责：

1. 感知用户正在看什么；
2. 获取当前选中的内容；
3. 获取当前前台软件和窗口信息；
4. 区分当前学习 Project；
5. 区分当前 Source；
6. 管理当前学习 Session；
7. 管理长期学习 Memory；
8. 管理跨书籍、跨课程、跨项目 Concept；
9. 检索当前任务最相关的旧知识；
10. 创建 Minimum Sufficient Context；
11. 将 Context Package 提供给 AI；
12. 保存有价值的学习信息。

AI 负责：

- 翻译
- 解释
- 推理
- 电路分析
- 公式理解
- 少量问答
- 跨知识关联解释

---

# 三、最高层设计原则

整个项目必须始终遵循：

> StudyCopilot 拥有 Context、Knowledge 和 Memory。

> GPT、Claude 或其他 AI 只是可以替换的大脑。

不要把用户最重要的数据绑定在单一厂商中。

长期目标：

```text
                    StudyCopilot
                         │
        ┌────────────────┼─────────────────┐
        │                │                 │
     Capture          Context            Memory
        │                │                 │
        └────────────────┼─────────────────┘
                         │
                    Knowledge
                         │
                   Context Package
                         │
                  Integration Layer
                         │
             ┌───────────┼───────────┐
             ↓           ↓           ↓
          ChatGPT      Claude       Other AI
```

未来即使用户：

- 取消 ChatGPT Plus
- 改用 Claude Pro
- 再改用 Gemini
- 使用本地模型

StudyCopilot 的以下内容都不应丢失：

- Projects
- Sources
- Learning Sessions
- Concepts
- Concept Links
- Questions
- Translation History
- Learning Preferences
- Memory
- Prompt
- UI
- Capture
- Context Manager

---

# 四、成本约束

用户是学生。

当前已经拥有 ChatGPT Plus。

用户希望：

ChatGPT Plus 既用于：

- Codex 开发 StudyCopilot
- 教材翻译
- 辅助理解
- 技术问答
- 看电路图

同时不希望必须长期额外支付：

- OpenAI API
- Anthropic API
- Claude Code
- 多个 AI PDF 软件
- 大量 Token 费用

因此：

## OpenAI API 不是核心依赖。

## Anthropic API 不是核心依赖。

API Provider 只能作为未来 Optional Feature。

没有 API Key 时，StudyCopilot 必须仍然完整支持：

- Capture
- Context
- Project
- Source
- Memory
- Knowledge
- Retrieval
- Context Package
- Clipboard Integration
- UI

用户未来可能取消 GPT Plus 改用 Claude Pro。

所以必须保持 Vendor Neutral。

---

# 五、绝对禁止 Vendor Lock-In

核心业务代码中禁止：

- 直接绑定 OpenAI SDK
- 直接绑定 Anthropic SDK
- 直接绑定 ChatGPT 专有 message schema
- 直接绑定 Claude 专有 message schema
- 把 Memory 只存在 ChatGPT
- 把 Memory 只存在 Claude
- 把 Prompt 写死在 Provider
- 把学习数据存在厂商专有格式中

未来 Provider：

```text
providers/
    base.py
    openai.py
    anthropic.py
    local.py
```

未来 Integration：

```text
integrations/
    base.py
    chatgpt/
    claude/
    fallback/
```

Provider 和 Integration 必须分开。

Provider：

AI API 层。

Integration：

AI 客户端 / Plugin / MCP / Tool / Clipboard 等交互层。

---

# 六、核心使用体验

用户可能在：

- Microsoft Edge
- Foxit
- Adobe Reader
- PDFgear
- 浏览器
- Word
- 其他 PDF 阅读器

阅读教材。

例如：

Microelectronic Circuits

用户看到：

```text
The source resistance introduces negative feedback.
```

用户：

鼠标选中

然后：

```text
Alt + Q
```

StudyCopilot：

```text
选中文字
↓
获取前台应用
↓
获取窗口标题
↓
判断当前 Project
↓
判断当前 Source
↓
获得当前 Session
↓
查询相关 Concepts
↓
查询相关 Memories
↓
创建 Context Package
↓
提供给当前 AI
```

---

# 七、主要快捷模式

## 1. Alt + Q — Translate

用途：

翻译当前选择内容。

翻译要求：

1. 中文准确自然；
2. 优先采用中国大陆高校电子类教材常用术语；
3. 保留重要英文术语；
4. 不总结；
5. 不扩写；
6. 不改公式；
7. 不改变量；
8. 不改单位；
9. 根据上下文消除专业歧义。

例如：

```text
transconductance
→ 跨导

small-signal model
→ 小信号模型

source degeneration
→ 源极退化

common-source amplifier
→ 共源放大器

channel-length modulation
→ 沟道长度调制

output resistance
→ 输出电阻

bias point / Q-point
→ 静态工作点
```

---

## 2. Alt + A — Ask / Explain

长期功能。

用于：

```text
“为什么？”
“这里什么意思？”
“这个公式怎么来的？”
“为什么加入 Rs 后增益下降？”
```

AI 应该获得：

- 当前选中文字
- 当前 Project
- 当前 Source
- 当前 Topic
- Recent Context
- Related Concepts
- Relevant Memories
- User Learning Preferences

回答偏好：

1. 中文；
2. 保留重要英文术语；
3. 优先物理直觉；
4. 再解释电路关系；
5. 再给数学关系；
6. 必要时推导公式；
7. 不默认做整章总结；
8. 根据用户已经掌握的知识控制解释深度。

---

## 3. Alt + E — Explain Screen

长期功能。

用于：

- 电路图
- 方框图
- 公式
- 波形
- 图片
- 教材复杂排版

流程：

```text
Alt+E
↓
截图
↓
Context
↓
Relevant Memory
↓
Vision-capable AI
```

V0.1 不实现 Vision AI。

只预留接口。

---

# 八、多学习项目 Project 系统

StudyCopilot 必须支持多个独立但可联动的学习项目。

Project 示例：

```text
模拟电子技术
半导体器件
信号与系统
数字电路
ArduPilot
论文阅读
毕业设计
某科研课题
```

Project 是一级学习空间。

不同 Project 的局部上下文默认隔离。

例如：

模拟电路 Project 的：

```text
MOSFET
small-signal model
source degeneration
```

不应因为关键词碰撞而自动污染 ArduPilot Project。

---

# 九、Source 系统

一个 Project 可以包含多个 Source。

Source 可以是：

- Book
- PDF
- Paper
- Lecture Notes
- Web Page
- Manual
- Documentation
- User Notes

例如：

```text
Project:
模拟电子技术

Sources:
- Microelectronic Circuits
- Sedra/Smith
- 模电课程讲义.pdf
- 教师 PPT
```

或者：

```text
Project:
ArduPilot

Sources:
- ArduPilot Plane Documentation
- 参数文档
- 飞行日志说明
```

不要把一本 PDF 等同于整个 Project。

---

# 十、Topic 系统

Project 下允许有 Topic。

例如：

```text
MOSFET
BJT
Operational Amplifiers
Negative Feedback
Frequency Response
```

Source 也可以包含：

- Chapter
- Section
- Topic

Topic 信息允许为空。

系统必须允许：

信息不完整但仍然正常工作。

---

# 十一、Concept 是跨项目知识联动的核心

Concept 不应绑定某一本书。

例如：

```text
negative feedback
transconductance
transfer function
pole
zero
channel-length modulation
output resistance
```

这些知识可以跨 Source、跨 Project 复用。

Concept 建议具有：

```text
id
canonical_name
english_name
chinese_name
description
created_at
updated_at
```

---

# 十二、Concept Aliases

同一个 Concept 可能有多种表达。

例如：

```text
Concept:
MOSFET output resistance

Aliases:
- ro
- r_o
- output resistance
```

例如：

```text
Q-point
bias point
静态工作点
```

应该允许映射到同一个 Canonical Concept。

需要设计：

```text
concept_aliases
```

而不是简单关键词匹配。

---

# 十三、Concept Links

不同 Concepts 之间允许建立关系。

至少支持：

```text
related_to
prerequisite_of
used_in
same_as
derived_from
contrasts_with
```

例如：

```text
channel-length modulation
    related_to
MOSFET output resistance
```

```text
small-signal model
    prerequisite_of
voltage gain analysis
```

```text
negative feedback
    used_in
source degeneration
```

```text
pole
    used_in
frequency response
```

第一阶段不要建立复杂 Knowledge Graph Engine。

SQLite relation table 即可。

---

# 十四、跨 Project 联动规则

Project 应隔离上下文，但 Concept 可以跨项目联动。

检索优先顺序：

```text
1. 当前 Project Memory
2. 当前 Source / Topic
3. Global Knowledge
4. 其他 Project 的高度相关 Concept / Memory
```

不要简单因为同一个英文单词出现，就跨项目引用。

跨项目联动必须满足：

**相关性明显。**

例如：

半导体器件中：

```text
channel-length modulation
```

可以联动到模拟电路中的：

```text
output resistance ro
```

但是：

ArduPilot 项目中的：

```text
output channel
```

显然不能因为 output 一词而混入。

---

# 十五、Memory Scope

Memory 至少支持三种 Scope：

## project

仅当前 Project 有效。

例如：

```text
用户在模拟电路项目中目前不熟悉 source degeneration。
```

## global

跨项目知识。

例如：

```text
用户已经理解 transfer function 基本定义。
```

## user

学习偏好。

例如：

```text
解释时先讲物理直觉，再公式。
```

---

# 十六、User Learning Preferences

长期记录：

```text
preferred_language
preferred_explanation_style
preferred_translation_style
preferred_depth
terminology_preferences
```

初始默认偏好：

```text
中文解释
保留英文专业术语
先直觉
再电路
再数学
公式尽量不要跳步
不要自动总结
```

这些属于 User Scope。

---

# 十七、Memory 原则

不要简单保存所有 Chat。

Memory 应保存真正有长期价值的信息。

例如：

```text
用户已经理解：
gm 的物理意义。

用户目前容易混淆：
gm 与 voltage gain。

用户已经学习：
MOSFET small-signal model。

用户对：
negative feedback
理解仍不稳定。
```

长期目标：

AI 回答前，只获得最相关 Memory。

---

# 十八、Memory Retrieval

初期：

SQLite + FTS5

不要立即加入：

- Chroma
- FAISS
- Pinecone
- embeddings API
- vector database

先建立统一接口：

```text
MemoryRetriever
```

例如：

```python
search(
    query,
    project_id=None,
    concept_ids=None,
    limit=5
)
```

未来可以换：

```text
HybridRetriever
VectorRetriever
GraphRetriever
```

但上层不变。

---

# 十九、Context Layer

建立统一内部 Context。

建议：

```text
context/
    models.py
    manager.py
    package.py
```

StudyContext 建议：

```text
current_app
process_name
window_title

project_id
source_id
topic_id
session_id

selected_text
recent_context

timestamp
```

这些字段允许部分为空。

必须遵循：

> Partial Context is valid context.

不能因为：

```text
page = unknown
```

就导致整个任务失败。

---

# 二十、Context Package

这是 AI 集成的核心边界。

定义厂商无关结构：

```text
ContextPackage

task_type

project
source
topic

selected_text
recent_context

related_concepts
relevant_memories

user_preferences

attachments
metadata
```

不要让：

OpenAI messages

或者：

Claude messages

成为内部数据格式。

Integration Layer 负责转换。

---

# 二十一、Minimum Sufficient Context

这是核心原则。

不要发送：

```text
整本书
+
全部 Memory
+
全部聊天
+
所有 Project
```

应该：

```text
当前选择
+
少量当前上下文
+
最相关 Concepts
+
3~5 条相关 Memory
+
必要用户偏好
```

目标：

- 降低 Token
- 减少噪音
- 降低成本
- 提高回答质量
- 降低跨 Project 污染

---

# 二十二、Capture Layer

建议：

```text
capture/
    clipboard.py
    hotkeys.py
    active_window.py
    screenshot.py
```

Alt+Q：

1. 保存当前剪贴板；
2. 模拟 Ctrl+C；
3. 等待数据变化；
4. 获取文字；
5. 尽可能恢复原剪贴板；
6. 获取当前窗口；
7. 获取当前进程；
8. 防止重复触发；
9. 不阻塞 UI。

必须考虑：

某些 PDF 软件 Ctrl+C 响应较慢。

增加合理等待 / retry。

不要无限等待。

---

# 二十三、Project Detection

V0.1 不需要 AI 自动判断 Project。

第一阶段可允许用户：

手动选择当前 Project。

例如 Sidebar：

```text
Project:
[ 模拟电子技术 ▼ ]
```

并允许：

```text
+ 新建项目
```

未来可以根据：

- window title
- source
- file path
- history

自动建议。

但不要第一阶段过度自动化。

---

# 二十四、Source Detection

V0.1 可以先：

通过 window title 获取可能 Source。

例如：

```text
Microelectronic Circuits.pdf - Foxit PDF Reader
```

提取：

```text
Microelectronic Circuits.pdf
```

如果无法可靠识别：

允许用户手动设置 Source。

不要做复杂 PDF parser。

---

# 二十五、Session

Study Session 表示一次连续学习。

例如：

```text
Project:
模拟电子技术

Source:
Microelectronic Circuits

Topic:
MOSFET Amplifiers

Started:
19:30
```

V0.1 可以简单实现：

- 当前 Session
- 开始时间
- Project
- Source

Topic 可以手动设置或为空。

---

# 二十六、数据库

默认：

```text
data/study.db
```

使用 SQLite。

必须考虑 Schema Version / Migration。

建议至少：

## projects

```text
id
name
description
created_at
updated_at
```

## sources

```text
id
project_id
source_type
title
author
edition
file_name
external_identifier
created_at
updated_at
last_opened_at
```

## topics

```text
id
project_id
source_id
name
parent_topic_id
created_at
```

## study_sessions

```text
id
project_id
source_id
topic_id
started_at
ended_at
```

## concepts

```text
id
canonical_name
english_name
chinese_name
description
created_at
updated_at
```

## concept_aliases

```text
id
concept_id
alias
language
```

## concept_links

```text
id
source_concept_id
target_concept_id
relation_type
confidence
created_at
```

## source_concepts

```text
id
source_id
concept_id
importance
created_at
```

## memories

```text
id
scope
project_id
source_id
concept_id
memory_type
content
importance
created_at
updated_at
```

## questions

```text
id
project_id
source_id
topic_id
session_id
question
context_text
answer_summary
created_at
```

## translation_history

```text
id
project_id
source_id
topic_id
session_id
source_text
translated_text
terms_json
source_app
created_at
```

## user_preferences

```text
id
key
value
updated_at
```

可以合理调整字段。

优先：

简单
清晰
可扩展
不破坏未来迁移

---

# 二十七、Prompt 系统

Prompt 必须独立保存。

例如：

```text
prompts/
    translation.md
    explain.md
    circuit.md
    equation.md
    tutor.md
```

Prompt 不得散落在 UI / Provider 中。

---

# 二十八、Translation Prompt 原则

translation.md 至少包含：

```text
用户正在阅读理工科专业资料。

翻译当前选中文字。

要求：

- 中文准确自然；
- 优先采用专业教材术语；
- 根据当前 Project 调整领域语义；
- 保留重要英文技术术语；
- 不总结；
- 不扩写；
- 不添加无关解释；
- 保留公式；
- 保留变量；
- 保留单位；
- 对歧义术语使用 Context 和相关 Concepts 判断。
```

---

# 二十九、Explain Prompt

至少包含：

```text
请解释当前内容。

用户偏好：

1. 中文为主；
2. 保留英文专业术语；
3. 先解释物理 / 工程直觉；
4. 再解释因果和结构；
5. 然后数学关系；
6. 必要时再推导；
7. 不跳过关键步骤；
8. 不自动总结整个章节；
9. 根据用户已有知识控制深度。
```

---

# 三十、不同 Project 可以拥有自己的 Prompt Preference

例如：

模拟电路：

```text
优先物理直觉
保留器件英文术语
公式尽量不跳步
```

论文阅读：

```text
优先准确理解原文
少做无关教学扩写
保持学术语义
```

ArduPilot：

```text
优先参数定义
区分 Plane/Copter
说明配置影响
安全相关内容不要臆测
```

未来支持：

```text
project_preferences
```

V0.1 可以只预留。

---

# 三十一、UI

使用：

Python 3.11+

PySide6

Windows 10 / 11。

目标：

轻量右侧 Sidebar。

宽度约：

```text
380–460 px
```

V0.1 建议：

```text
StudyCopilot

Project
[ 模拟电子技术 ▼ ]

Source
Microelectronic Circuits

Topic
MOSFET Amplifiers

----------------

当前应用
Foxit

窗口
Microelectronic Circuits.pdf

----------------

Selected Text

----------------

Related Knowledge

----------------

Relevant Memory

----------------

Context Package Preview

----------------

[复制给 AI]

[保存 Memory]

[关闭]
```

保持简单。

不要做成完整聊天客户端。

---

# 三十二、AI Integration

目前最重要要求：

**不要通过不官方、不安全方式直接控制 ChatGPT / Claude。**

禁止：

- 窃取 Cookie
- 读取认证 Token
- 模拟账号密码
- 逆向私有 API
- 浏览器 Cookie 注入
- 非官方 session hack

只使用官方支持方式。

---

# 三十三、Fallback Integration

V0.1 必须提供可靠：

```text
Copy to AI
```

即：

```text
Context Package
↓
格式化为适合聊天 AI 的 Prompt
↓
复制到剪贴板
```

然后用户粘贴至：

- ChatGPT Plus
- Claude Pro
- 其他 AI

这保证：

即使 Integration 改变，核心系统仍可使用。

---

# 三十四、未来 ChatGPT / Claude Integration

如果未来官方支持：

- Plugin
- MCP
- Tool
- App
- Connector

则增加：

```text
integrations/chatgpt
integrations/claude
```

它们读取统一 Context Package。

不要改核心 Memory。

---

# 三十五、API Provider

未来可选：

```text
providers/
    base.py
    openai.py
    anthropic.py
```

API 只能作为：

Optional.

没有 API Key：

应用必须正常启动。

---

# 三十六、隐私

默认 Local First。

要求：

- Memory 本地；
- 数据库本地；
- Project 数据本地；
- 不自动上传完整 PDF；
- 不自动上传完整数据库；
- 不自动上传所有历史记录；
- 日志不要记录完整教材段落；
- 日志不要记录密钥；
- 截图只能在用户主动触发时使用。

---

# 三十七、多设备长期需求

未来用户可能：

- Windows PC
- Laptop
- Tablet
- Phone

使用同一学习系统。

但 V0.1 不实现同步。

数据库设计避免：

```text
C:\Users\xxx\book.pdf
```

成为 Source 唯一 ID。

应该使用：

```text
source_id
```

未来可考虑：

- Syncthing
- WebDAV
- 云盘
- Export / Import

但当前不要实现。

---

# 三十八、推荐项目结构

```text
StudyCopilot/
│
├── AGENTS.md
├── README.md
├── pyproject.toml
├── requirements.txt
├── .gitignore
├── .env.example
│
├── src/
│   └── studycopilot/
│
│       ├── main.py
│       ├── config.py
│
│       ├── ui/
│       │   ├── sidebar.py
│       │   └── components/
│
│       ├── capture/
│       │   ├── clipboard.py
│       │   ├── hotkeys.py
│       │   ├── active_window.py
│       │   └── screenshot.py
│
│       ├── projects/
│       │   ├── manager.py
│       │   └── models.py
│
│       ├── context/
│       │   ├── models.py
│       │   ├── manager.py
│       │   └── package.py
│
│       ├── knowledge/
│       │   ├── concepts.py
│       │   ├── aliases.py
│       │   └── links.py
│
│       ├── memory/
│       │   ├── database.py
│       │   ├── schema.py
│       │   ├── migrations.py
│       │   └── retrieval.py
│
│       ├── prompts/
│       │   ├── translation.md
│       │   ├── explain.md
│       │   ├── circuit.md
│       │   ├── equation.md
│       │   └── tutor.md
│
│       ├── integrations/
│       │   ├── base.py
│       │   └── fallback.py
│
│       └── providers/
│           └── base.py
│
├── data/
├── logs/
└── tests/
```

可以合理调整，但必须保持：

- UI
- Capture
- Project
- Context
- Knowledge
- Memory
- Integration
- Provider

边界清楚。

---

# 三十九、AGENTS.md

必须创建。

内容至少包括：

## Mission

帮助用户阅读复杂 STEM 内容时获得：

- 翻译
- 理解
- 问答
- 长期学习记忆
- 跨资料知识联动

## Current Priority Domains

- Analog Electronics
- Analog Circuits
- Microelectronic Circuits
- Semiconductor Devices

## Principles

1. Local First
2. Model Independent
3. Client Independent
4. Memory Belongs to User
5. Project-Aware
6. Concept-Aware
7. Minimum Sufficient Context
8. Translation First
9. No Automatic Summarization
10. Avoid Vendor Lock-In
11. Low Cost
12. Privacy by Default
13. Incremental Development
14. Do Not Overengineer
15. Partial Context Must Still Work

Codex 后续所有修改都遵守 AGENTS.md。

---

# 四十、现在真正需要实现：V0.1

不要一次实现全部长期功能。

V0.1 的目标：

**证明学习上下文系统真正可用。**

必须实现：

## A. PySide6 Sidebar

应用可以正常启动、关闭。

---

## B. Project Management

至少支持：

- 创建 Project
- 查看 Project
- 选择当前 Project

默认可以自动创建：

```text
General
```

或者：

```text
未分类
```

---

## C. Source

允许：

- 根据窗口标题生成建议 Source
- 或手动填写 / 创建 Source

---

## D. Global Hotkey

实现：

```text
Alt+Q
```

---

## E. Selection Capture

用户选中文字：

```text
Alt+Q
```

StudyCopilot 获取文字。

要求：

- 尽可能恢复原剪贴板
- 防抖
- 空内容处理
- Ctrl+C 延迟处理
- 不冻结 UI

---

## F. Active Window

获取至少：

```text
process name
window title
```

---

## G. StudyContext

建立统一 Context 对象。

至少：

```text
project_id
source_id
selected_text
current_app
window_title
timestamp
```

---

## H. SQLite

建立数据库和 migration/version 机制。

至少创建：

- projects
- sources
- study_sessions
- concepts
- concept_aliases
- concept_links
- memories
- translation_history
- user_preferences

---

## I. Knowledge Layer

建立基本 Concept model。

V0.1 不需要复杂自动抽取。

至少允许程序层创建 / 查询 Concept。

---

## J. Memory

支持：

- project
- global
- user

三种 scope。

Sidebar 至少提供：

```text
保存 Memory
```

简单输入即可。

---

## K. Retrieval

SQLite FTS5。

搜索：

当前选中文字。

优先：

```text
current project
↓
global
```

暂时可以弱化跨 Project 自动检索。

但接口必须允许未来扩展。

---

## L. Context Package

创建统一 ContextPackage。

包含：

```text
task_type
project
source
selected_text
current_app
window_title
relevant_memories
related_concepts
user_preferences
```

---

## M. Translation Context

Alt+Q 默认为：

```text
task_type = translate
```

Context Package 应加入翻译 Prompt。

---

## N. Context Preview

Sidebar 显示：

- Project
- Source
- Selected Text
- Relevant Memory
- Related Concepts
- Context Package Preview

---

## O. Copy to AI

按钮：

```text
复制给 AI
```

将完整 Prompt 复制到剪贴板。

能够直接粘贴到 ChatGPT Plus。

---

## P. Logging

```text
logs/app.log
```

不要记录：

- API Key
- 登录 Token
- 完整教材正文

可以记录：

- capture success
- capture length
- project id
- source id
- exception

---

## Q. Tests

至少：

- application module import
- DB initialization
- migrations
- project creation
- source creation
- memory insertion
- FTS retrieval
- concept creation
- alias handling
- Context model
- Context Package
- empty clipboard
- missing window title
- fallback copy formatting

---

# 四十一、V0.1 明确不要实现

暂时不要实现：

- OpenAI API
- Anthropic API
- Claude API
- MCP Server
- ChatGPT Plugin
- Claude Plugin
- OCR
- Vision AI
- PDF parser
- 自动读取整本 PDF
- Browser Extension
- embeddings
- FAISS
- Chroma
- Pinecone
- 自动 Concept Graph 构建
- 云同步
- 用户账号
- 自动摘要
- AI 自动生成学习计划

不要 scope creep。

---

# 四十二、V0.1 成功标准

用户能够：

```text
1. 启动 StudyCopilot

2. 创建：
   模拟电子技术

3. 选择这个 Project

4. 打开：
   Microelectronic Circuits.pdf

5. 在 Foxit / Edge 中选中英文

6. 按：
   Alt+Q

7. StudyCopilot 获取：
   选中文字
   当前应用
   窗口标题

8. Context Manager 确定：
   当前 Project
   当前 Source

9. Retrieval 获取：
   相关 Memory
   相关 Concept

10. 创建 Translation Context Package

11. Sidebar 显示内容

12. 点击：
    复制给 AI

13. 粘贴到 ChatGPT Plus

14. ChatGPT 可以直接知道：
    当前是什么项目
    当前是什么资料
    当前选择了什么
    用户翻译偏好
    相关历史知识
```

达到以上即可认为 V0.1 成功。

---

# 四十三、V0.2

只记录，不立即实现。

Alt+A Ask / Explain。

包括：

```text
当前选择
+
用户问题
+
Recent Context
+
Relevant Memory
+
Related Concepts
```

---

# 四十四、V0.3

Memory UX：

- 已理解
- 未理解
- 易混淆
- 重要
- 删除
- 编辑

---

# 四十五、V0.4

Project / Source Intelligence：

自动建议：

- 当前 Project
- 当前 Source
- 当前 Topic

---

# 四十六、V0.5

Cross-Project Knowledge Linking。

例如：

```text
半导体器件
channel-length modulation
          ↓
模拟电路
MOSFET output resistance
```

根据 Concept Link 提供跨项目旧知识。

但遵循相关性阈值。

---

# 四十七、V0.6

官方 AI Client Integration。

如果存在可靠官方方式：

- ChatGPT
- Claude

允许直接调用 Context。

Fallback Clipboard 永远保留。

---

# 四十八、V0.7

Alt+E：

截图 + Vision。

---

# 四十九、V0.8

更高级 Memory Retrieval。

只有普通 FTS5 明显不足时，再考虑：

- Embeddings
- Hybrid Search
- Vector DB

---

# 五十、V0.9

多设备同步。

---

# 五十一、V1.0 目标

最终 StudyCopilot 应成为：

**一个属于用户自己的跨教材、跨课程、跨 AI 的长期理工科学习上下文与知识记忆系统。**

用户的 AI 可以更换。

用户的知识系统不能丢。

---

# 五十二、开发执行要求

现在不要先给我输出长篇设计说明。

直接执行。

顺序：

1. 检查工作目录；
2. 检查已有文件；
3. 如果为空，初始化项目；
4. 如果已有代码，先审查；
5. 创建 / 更新 AGENTS.md；
6. 初始化 Git；
7. 建立 Python 项目；
8. 建立 SQLite schema；
9. 实现 Project；
10. 实现 Source；
11. 实现 Capture；
12. 实现 Active Window；
13. 实现 Context；
14. 实现 Knowledge 基础层；
15. 实现 Memory；
16. 实现 FTS Retrieval；
17. 实现 Context Package；
18. 实现 Translation Prompt；
19. 实现 Fallback Integration；
20. 实现 PySide6 Sidebar；
21. 实现 Alt+Q；
22. 写测试；
23. 运行测试；
24. 启动应用；
25. 检查日志；
26. 修复错误；
27. 再运行；
28. 验证 V0.1 成功标准。

普通 bug 请自行修复。

不要每遇到一个错误就询问用户。

---

# 五十三、技术决策权限

你可以自行选择：

- pynput
- keyboard
- pywin32
- ctypes
- sqlite3
- SQLAlchemy
- dataclass
- Pydantic
- pytest

优先：

```text
简单
稳定
依赖少
Windows 兼容
维护成本低
```

如果 SQLAlchemy 对当前阶段明显过重，可以直接 sqlite3。

如果 Pydantic 没必要，也可以 dataclass。

不要为了“企业级架构”增加无意义复杂度。

---

# 五十四、需要询问用户的情况

只有这些情况再询问：

- 需要账号登录
- 需要真实付费
- 需要敏感授权
- 需要破坏或删除已有数据
- 产品方向存在重大冲突
- 必须由用户进行 GUI 实测才能继续

普通技术问题自己解决。

---

# 五十五、安全要求

禁止：

- 获取浏览器密码
- 偷 Cookie
- 偷 Session
- 偷 Token
- 逆向 ChatGPT 私有 API
- 逆向 Claude 私有 API
- 自动上传整本教材
- 自动上传数据库
- 把 Key 写进 Git
- 在日志保存密钥
- 静默截图

---

# 五十六、README

README 必须告诉普通用户：

## 安装

具体命令。

## 启动

具体命令。

## 使用

例如：

```text
1. 启动 StudyCopilot
2. 创建或选择 Project
3. 打开 PDF
4. 选中文字
5. Alt+Q
6. 点击“复制给 AI”
7. 粘贴进 ChatGPT
```

## 当前限制

如实说明。

## 数据保存位置

说明：

```text
data/study.db
```

## 隐私

明确说明：

默认本地存储。

---

# 五十七、代码质量

必须：

- 合理类型标注
- 清晰异常处理
- 避免 giant file
- 避免 giant class
- 避免循环依赖
- 不把 SQL 全写在 UI
- 不把 Prompt 写在 UI
- 不把 Capture 写进 MainWindow
- 不让 Provider 污染核心数据结构

---

# 五十八、兼容未来迁移

所有长期数据必须可以在：

```text
ChatGPT
↓
Claude
↓
其他模型
```

切换时继续使用。

这是硬性要求。

---

# 五十九、最终开发汇报

完成当前轮次以后，只汇报：

## 已完成

真实实现的内容。

## 测试结果

哪些测试通过。

## 如何运行

给用户命令。

## 如何实测

具体步骤。

## 当前限制

明确限制。

## 下一步建议

最多 3 项。

不要声称没有测试的东西已经正常。

---

# 六十、最终产品原则

如果某个工程决策存在冲突，按以下优先级判断：

```text
1. 用户数据属于用户
2. 不绑定单一 AI 厂商
3. 本地优先
4. 当前实际可用
5. 学习体验
6. 成本低
7. 隐私
8. 可扩展
9. 自动化
10. 技术炫技
```

任何时候：

**宁可先做一个可靠的简单版本，也不要做一个复杂但不可用的版本。**

---

现在直接开始开发 StudyCopilot V0.1。