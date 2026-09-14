# StudyCopilot V0.2 — Screenshot-First 阅读体验重构

你现在继续开发现有的 StudyCopilot 项目。

## 非常重要：V0.1 已经完成

当前工作目录中已经存在可运行的 StudyCopilot V0.1。

不要重新创建项目。

不要重新实现 V0.1。

不要删除现有项目后从零开始。

不要因为下面描述了新的产品方向，就重写所有已经正常工作的模块。

第一步必须是：

**阅读并审查现有代码、AGENTS.md、README、数据库 Schema、测试和当前 UI，理解 V0.1 已经完成了什么。**

然后在现有代码基础上进行增量重构。

必须尽可能保留和复用 V0.1 已有的：

- Project
- Source
- Topic
- Session
- SQLite
- Memory
- Concept
- Concept Alias
- Concept Link
- Retrieval
- Context
- ContextPackage
- Prompt 系统
- Integration 抽象
- Provider 抽象
- 日志
- 测试
- 配置
- 已经可靠工作的 Windows 基础设施

除非现有实现存在明确问题，否则不要为了“代码更漂亮”而重写。

数据库已有用户数据时必须优先保护数据。

Schema 需要变化时使用 migration，不要删除数据库重建。

---

# 1. 为什么现在需要 V0.2

V0.1 已经完成并经过实际使用。

实际体验暴露出了一个根本问题：

V0.1 的核心工作流是：

```text
外部阅读器选中文字
→ 快捷键 / 复制
→ StudyCopilot
→ Selected Text
→ 生成 Context Package
→ 点击“复制给 AI”
→ 切换 ChatGPT
→ 粘贴
→ 发送
→ 获得回答
```

这个流程技术上可以工作，但是实际阅读体验很差。

更重要的是：

## 用户主要阅读的是扫描版 PDF。

扫描版 PDF 经常：

- 没有文字层；
- 无法选择文字；
- OCR 质量不稳定；
- 包含公式；
- 包含电路图；
- 包含上下标；
- 包含图注；
- 文字和图形共同构成语义。

因此：

**“选中文字”不应该继续作为 StudyCopilot 的主要输入方式。**

从 V0.2 开始：

# StudyCopilot 必须从 Text-First 转向 Screenshot-First。

---

# 2. 新的产品定位

StudyCopilot 是：

**Screenshot-First、Context-Aware、Local-First、Model-Independent 的 AI 学习阅读伴侣。**

它不是：

- Prompt Generator
- PDF Reader
- OCR 软件
- 普通聊天客户端

它负责：

```text
用户正在阅读的内容
        ↓
Screenshot / Text / Context
        ↓
Project / Source / Session
        ↓
Relevant Memory / Knowledge
        ↓
Minimum Sufficient Context
        ↓
AI
```

AI 可以是：

- ChatGPT
- Claude
- 未来其他模型

StudyCopilot 的长期数据不能绑定具体模型。

---

# 3. 最高优先级使用场景

用户正在 Windows 中阅读扫描版：

Microelectronic Circuits

或者其他：

- 模拟电子技术教材
- 半导体器件教材
- 数字电路教材
- 信号与系统教材
- 论文
- 扫描书籍
- 技术文档

页面可能同时包含：

```text
英文正文
+
MOSFET/BJT 电路图
+
公式
+
上下标
+
变量
+
图注
+
波形
```

用户看到一块内容需要翻译。

理想操作：

```text
Alt+Q
↓
进入区域截图模式
↓
鼠标框选教材区域
↓
松开鼠标
↓
StudyCopilot 得到原始截图
↓
关联当前 Project / Source / Session
↓
建立视觉 Translation Context
↓
准备交给具有 Vision 能力的 AI
```

这必须成为 V0.2 的核心工作流。

---

# 4. V0.2 的核心原则

从现在开始，Capture 优先级调整为：

```text
1. Region Screenshot       ← 主输入
2. Current Screenshot      ← 主上下文
3. Text Selection          ← 辅助输入
4. OCR                     ← 未来辅助索引
```

不要删除 V0.1 的文字 Capture。

它仍然有价值。

但是：

## Text Selection 从 Primary Input 降级为 Secondary Input。

---

# 5. 不要把 OCR 当成 Screenshot Translation 的必经步骤

这是非常重要的架构要求。

扫描版 STEM 教材中可能出现：

```text
gm
r_o
R_S
R_D
V_GS
V_DS
β
λ
ω
```

以及复杂公式和电路连接。

OCR 可能错误识别：

- 下标
- 希腊字母
- 分数
- 公式结构
- 电路符号
- 上下文关系

因此长期视觉翻译链路应该是：

```text
Screenshot
      │
      ├──────────────→ Vision-capable AI
      │                    ↓
      │              翻译 / 理解 / 推理
      │
      └──────────────→ OCR（未来）
                           ↓
                    搜索 / 索引 / Concept
```

也就是说：

**Vision AI 应直接看到原始截图。**

OCR 以后可以加入，但主要用于：

- 全文搜索
- 本地索引
- Concept Detection
- Source Search

V0.2 不需要实现 OCR。

---

# 6. V0.2 快捷键重新设计

## Alt+Q — Screenshot Translate

这是 V0.2 最重要的快捷键。

按下：

```text
Alt+Q
```

进入 Region Capture。

行为：

1. 当前屏幕进入区域选择模式；
2. 鼠标变为适合截图的十字光标；
3. 用户按下鼠标左键；
4. 拖动选择矩形区域；
5. 显示半透明选区；
6. 松开鼠标；
7. 完成截图；
8. Esc 取消；
9. 极小区域应忽略；
10. 多显示器环境尽量正确工作；
11. 高 DPI / Windows Scaling 尽量正确；
12. 截图完成后不要让截图遮罩出现在最终截图中。

Task：

```text
translate
```

---

# 7. Alt+A — Screenshot Explain

V0.2 如果实现成本合理，应同时实现。

按：

```text
Alt+A
```

同样进入区域截图。

但是：

```text
task_type = explain
```

用于：

- 这段什么意思？
- 这个公式为什么这样？
- 这个电路在做什么？
- 为什么这里可以忽略某个量？
- 图中的反馈路径是什么？

如果实现 Alt+A 会显著影响 Alt+Q 的可靠性：

优先把 Alt+Q 做好。

---

# 8. Current Screenshot

建立明确的数据模型。

例如：

```text
ScreenshotContext

id
image_path
capture_type
screen_region
width
height
captured_at

project_id
source_id
topic_id
session_id

task_type
```

可以根据现有架构调整。

不要把图片二进制直接长期塞进 SQLite。

图片建议保存到：

```text
data/
    screenshots/
```

或者合理的本地应用数据目录。

数据库只保存 metadata / path。

---

# 9. Screenshot 生命周期

不是每一张截图都值得永久保存。

需要区分：

```text
temporary screenshot
```

和：

```text
learning screenshot
```

默认截图可以是临时的。

只有当：

- 用户明确保存；
- 与 Memory 关联；
- 与 Question 关联；
- 与 Concept 关联；
- 被标记为重要；

才升级为长期学习资料。

避免用户学习几个月后：

```text
data/screenshots/
```

积累几十 GB 无意义截图。

为未来 Cleanup Policy 预留结构。

V0.2 可以采用简单策略：

- 当前截图保留；
- 最近若干截图保留；
- 不做复杂自动清理；
- 代码结构允许未来增加清理策略。

---

# 10. StudyContext 升级

现有 StudyContext 必须继续兼容。

增加视觉输入。

例如：

```text
StudyContext

project
source
topic
session

current_app
window_title

selected_text        # optional

current_screenshot   # optional
recent_screenshots   # optional

recent_context
timestamp
```

核心原则：

# Partial Context Is Valid Context.

允许：

```text
selected_text = None
current_screenshot != None
```

也允许：

```text
selected_text != None
current_screenshot = None
```

以后甚至允许二者同时存在。

---

# 11. ContextPackage 升级为 Multimodal

V0.1 已有 ContextPackage 时，不要删除重写。

增量扩展。

建议：

```text
ContextPackage

task_type

project
source
topic
session

selected_text

current_screenshot
recent_screenshots

related_concepts
relevant_memories

user_preferences

attachments
metadata
```

ContextPackage 必须保持：

**Vendor Neutral**

不要使用：

OpenAI-specific image format

作为内部标准。

也不要使用：

Anthropic-specific content block

作为内部标准。

Integration 层负责转换。

---

# 12. Translation Prompt 改成视觉教材翻译

更新现有 translation prompt。

任务定义：

用户正在阅读 STEM 教材或技术文献。

当前输入可能是一张包含：

- 正文
- 公式
- 电路图
- 图注
- 表格

的截图。

翻译要求：

1. 准确翻译截图中需要阅读的正文；
2. 不自动总结；
3. 不随意扩写；
4. 保留重要英文专业术语；
5. 保留公式；
6. 保留变量；
7. 保留下标含义；
8. 保留单位；
9. 根据图、电路和上下文消除术语歧义；
10. 不要因为看到电路图就自动写长篇电路分析；
11. 如果图中的文字属于正文理解的一部分，应结合图理解；
12. 无法确认的字符不要自信编造。

当前模拟电路领域继续优先采用标准术语，例如：

```text
transconductance → 跨导
source degeneration → 源极退化
small-signal model → 小信号模型
bias point / Q-point → 静态工作点
common-source amplifier → 共源放大器
channel-length modulation → 沟道长度调制
output resistance → 输出电阻
negative feedback → 负反馈
```

---

# 13. Explain Prompt 升级

Explain Screenshot 时：

AI 应该知道用户可能框选：

```text
电路图 + 公式 + 正文
```

解释原则：

```text
先识别用户框选内容在讲什么
↓
物理 / 工程直觉
↓
电路关系
↓
必要数学关系
↓
必要时推导
```

用户偏好继续保持：

- 中文为主
- 保留英文术语
- 不要无意义总结
- 不要默认从最基础概念全部讲起
- 根据 Memory 判断已有知识

---

# 14. Recent Visual Context

这是 V0.2 非常重要的新方向。

用户经常会：

```text
第一次：
截图翻译

第二次：
这个公式怎么来的？

第三次：
为什么这里忽略 ro？
```

不能把每次操作都当成完全独立任务。

因此建立：

```text
RecentContext
```

至少记录当前 Session 中最近的：

- screenshot metadata
- task
- selected text
- source
- timestamp

V0.2 不需要做复杂 Conversation Engine。

但架构必须允许后续：

```text
current screenshot
+
previous relevant screenshot
+
recent question
```

形成连续学习上下文。

---

# 15. Project / Source / Memory 不要删除

V0.1 已经完成这些基础设施。

继续保留。

Screenshot 必须能够关联：

```text
Project
Source
Topic
Session
```

例如：

```text
Project:
模拟电子技术

Source:
Microelectronic Circuits

Topic:
MOSFET Amplifiers

Current Screenshot:
capture_20260910_xxx.png
```

---

# 16. 跨项目知识系统继续保留，但降低当前开发优先级

以下长期设计继续有效：

- Concept
- Concept Alias
- Concept Link
- Project Memory
- Global Memory
- User Memory
- Cross-Project Knowledge Linking

不要删除。

但是：

## V0.2 不要投入大量时间继续扩展 Knowledge Graph。

当前优先级：

```text
Screenshot UX             ★★★★★
Screenshot Capture        ★★★★★
Visual Context            ★★★★★
AI Handoff UX             ★★★★★
Recent Context            ★★★★☆
Project / Source          ★★★★☆
Memory                    ★★★★☆
Cross-project Knowledge   ★★★☆☆
OCR                       ★★☆☆☆
Complex Knowledge Graph   ★☆☆☆☆
```

---

# 17. UI 必须重构

当前 V0.1 UI 暴露了太多内部实现。

当前界面类似：

```text
Project
Source
Topic
Session
Selected Text
Related Concepts
Related Memory
Full Prompt
Copy to AI
Save Memory
```

这对开发调试有帮助，但对日常阅读过于复杂。

V0.2：

# Prompt 不应该成为主要 UI。

# Concept 数据库不应该成为主要 UI。

# Memory 数据库不应该成为主要 UI。

这些是后台能力。

---

# 18. V0.2 Normal Mode UI

主界面应该明显更轻。

推荐：

```text
┌──────────────────────────────────┐
│ StudyCopilot                     │
│ 模拟电子技术 · Microelectronic… │
├──────────────────────────────────┤
│                                  │
│       Current Screenshot         │
│          [缩略图]                │
│                                  │
├──────────────────────────────────┤
│                                  │
│ 当前任务：翻译                   │
│                                  │
│ [准备给 AI]                      │
│                                  │
├──────────────────────────────────┤
│  截图翻译     截图解释           │
│                                  │
│  继续提问…                       │
│                                  │
├──────────────────────────────────┤
│ Project / Source        ⚙        │
└──────────────────────────────────┘
```

Project / Source 仍然可操作，但不要占据半个窗口。

---

# 19. Advanced / Debug View

V0.1 中以下内容仍然有价值：

- Related Concepts
- Relevant Memory
- Context Package
- Full Prompt
- Current App
- Window Title
- Session metadata

不要删除。

把它们移动到：

```text
Details
Advanced
Debug
```

等可折叠区域。

普通学习时默认隐藏。

---

# 20. 截图预览

截图完成后：

Sidebar 必须立即显示缩略图。

用户应该能够：

- 查看当前截图；
- 重新截图；
- 清除截图；
- 必要时打开大图预览。

不要只显示：

```text
capture_123.png
```

必须显示真实视觉缩略图。

---

# 21. AI Handoff 是 V0.2 的关键问题

当前用户拥有 ChatGPT Plus。

用户希望尽可能利用：

ChatGPT Plus

进行：

- 翻译
- 理解
- Vision
- 问答

而不是强制额外购买 OpenAI API Token。

未来用户也可能改用：

Claude Pro。

因此：

# 不允许为了自动化直接加入强制 OpenAI API。

# 不允许为了自动化直接加入强制 Anthropic API。

---

# 22. 不允许非官方登录集成

禁止：

- 抓 ChatGPT Cookie
- 抓 Claude Cookie
- 读取 Session Token
- 模拟登录
- 逆向私有 API
- 浏览器认证注入
- 自动读取密码

所有客户端集成必须建立在官方支持方式上。

---

# 23. V0.2 Fallback 必须支持图片

V0.1 的：

```text
Copy to AI
```

只能复制文本 Prompt。

V0.2 必须升级。

需要实现一个可靠的：

```text
Prepare for AI
```

流程。

至少做到：

1. 当前截图已经准备好；
2. 对应 Prompt 已经生成；
3. Context Package 已经生成；
4. 用户可以方便地把图片 + Prompt 提供给 ChatGPT / Claude。

请调查 Windows 剪贴板是否可以可靠同时提供：

- image
- text

以及 ChatGPT/Claude 客户端实际粘贴行为。

如果无法可靠一次粘贴两者：

不要 hack。

设计最少步骤的 fallback。

例如：

```text
按钮 A：
复制截图

按钮 B：
复制 Prompt
```

或者：

```text
准备给 AI
```

后提供非常清晰的两步操作。

优先追求：

**用户操作最少。**

但不要通过不可靠的技巧假装实现一键。

---

# 24. 评估官方 AI Integration

在不阻塞 Screenshot Capture 开发的前提下：

检查当前项目未来是否适合通过官方支持方式接入：

- ChatGPT
- Claude
- MCP
- Plugin
- Tool
- Connector
- App integration

但是：

## V0.2 不要因为集成研究而无限拖延。

如果当前没有稳定、官方、可利用 Plus/Pro 客户端订阅的自动接口：

继续使用可靠 fallback。

必须保持：

```text
integrations/
```

抽象。

未来只替换 Integration。

---

# 25. Text Capture 继续保留

V0.1 已经有：

```text
Selected Text
```

不要删除。

对于有文字层的：

- 网页
- 普通 PDF
- Word
- Documentation

选中文字仍然非常方便。

长期可以形成：

```text
Alt+Q
```

默认 Screenshot Translate。

另外保留文字捕获入口。

如果现有 Alt+Shift+Q 已经用于 Text Capture：

可以继续保留：

```text
Alt+Shift+Q
→ Text Capture
```

不要破坏已经工作的功能。

---

# 26. Screenshot Region UX 要求

区域截图体验必须认真做。

至少考虑：

- 多显示器
- Windows DPI Scaling
- 125%
- 150%
- 高分屏
- Esc 取消
- 右键取消（可选）
- 选区矩形
- 半透明遮罩
- 十字光标
- 极小区域
- 屏幕边缘
- 快速连续截图
- Hotkey debounce
- 截图时 Sidebar 不应该错误进入截图内容

如果实现多显示器需要额外时间：

先保证主显示器可靠。

README 如实说明限制。

不要声称没有测试的 DPI / 多显示器功能已经支持。

---

# 27. Screenshot Security / Privacy

截图是敏感能力。

必须：

- 只有用户主动快捷键触发；
- 不后台自动截图；
- 不定时截图；
- 不监控屏幕；
- 不自动上传；
- 默认本地保存；
- 日志不保存图片内容；
- 日志只记录 metadata。

---

# 28. Memory 与 Screenshot

允许用户把当前截图关联到 Memory。

例如：

```text
用户保存：

“这里的 Rs 引入 source degeneration，
本质是局部负反馈。”
```

Memory 可以引用：

```text
screenshot_id
```

但不要把图片内容直接写进 Memory 文本字段。

---

# 29. 数据库 Migration

如果需要新增：

```text
screenshots
recent_context
```

或者其他表：

必须通过 migration。

不要：

```text
DELETE study.db
```

不要要求用户重新创建所有 Project。

现有 V0.1 数据必须保留。

---

# 30. 推荐 screenshots 表

可以根据现有 Schema 调整：

```text
screenshots

id
project_id
source_id
topic_id
session_id

file_path
capture_type
task_type

width
height

is_persistent
created_at
```

不要过度设计。

---

# 31. Screenshot 文件命名

不要直接使用完整教材内容作为文件名。

建议：

```text
YYYYMMDD_HHMMSS_<short-id>.png
```

避免：

- 非法 Windows 字符；
- 超长路径；
- 泄露教材内容。

---

# 32. V0.2 不要实现完整 PDF Reader

不要尝试：

- 自己渲染 PDF；
- 做分页；
- 做书签；
- 替代 Foxit；
- 替代 Edge；
- 替代 Adobe Reader。

StudyCopilot 是：

**Overlay / Companion**

不是 Reader。

---

# 33. V0.2 不要实现 OCR

虽然用户阅读扫描 PDF：

现在也不要急着加入 Tesseract / PaddleOCR 等。

原因：

当前核心任务是：

**让视觉 AI 直接看到截图。**

OCR 留给后续：

- 本地搜索
- 自动 Source/Topic Detection
- Concept Indexing

---

# 34. V0.2 不要实现复杂知识图谱

保留已有 Concept 系统。

但不要继续大量开发：

- 自动 Concept Extraction
- Graph Visualization
- Knowledge Map
- 自动关系生成

当前没有截图体验重要。

---

# 35. V0.2 不要实现强制 API

不要主动加入：

```text
OPENAI_API_KEY required
ANTHROPIC_API_KEY required
```

如果项目已经有 Provider abstraction：

保留。

但 V0.2 必须：

**零 API Key 可以完整启动并使用 Screenshot Capture + Context + Handoff。**

---

# 36. V0.2 需要保留模型可迁移性

内部结构必须继续是：

```text
Screenshot
      ↓
StudyContext
      ↓
Memory Retrieval
      ↓
ContextPackage
      ↓
Integration
      ↓
┌───────────────┐
│               │
GPT           Claude
```

而不是：

```text
Screenshot
↓
OpenAI-specific code
```

---

# 37. Normal User 不应该管理 Prompt

V0.1 有：

```text
完整 Prompt
```

Tab。

V0.2 默认隐藏。

Prompt 是内部能力。

高级用户仍可：

```text
查看 Context / Prompt
```

但正常阅读不需要看到。

---

# 38. Normal User 不应该手动管理每个 Concept

Concept 应作为后台知识层。

V0.2 普通界面只需要在必要时显示：

```text
相关知识
```

甚至可以默认折叠。

---

# 39. Memory UX 简化

V0.1 的：

```text
保存 Memory
```

可以继续保留。

但长期应该变成更自然的：

```text
记住这个
```

或者：

```text
保存知识点
```

V0.2 如果 UI 重构时容易实现，可以改文案。

不要因为 Memory UX 阻塞截图核心功能。

---

# 40. 连续阅读设计

未来 StudyCopilot 不应该每次截图后“失忆”。

同一个 Session 内：

```text
Screenshot A
↓
Translate

Screenshot B
↓
Explain

Question C
↓
Follow-up
```

应该能够形成：

```text
Recent Learning Context
```

V0.2 先建立基础数据结构。

不要立即构建完整聊天系统。

---

# 41. Project / Source UI 简化

V0.1 顶部大量空间用于：

```text
Project
Source
Topic
Session
```

V0.2 建议改成：

```text
模拟电子技术
Microelectronic Circuits
```

一到两行。

点击后再展开管理。

Topic 可隐藏到 Details。

Session 默认后台自动维护。

---

# 42. 视觉层级

当前 UI 的主要视觉焦点应该从：

```text
Project / Source 表单
```

转移到：

```text
Current Screenshot
+
Current Task
+
AI Result / Handoff
```

用户打开 StudyCopilot 应该立即知道：

**现在截什么、现在问什么。**

---

# 43. 当前阶段的真实限制必须接受

如果由于 ChatGPT Plus / Claude Pro 没有稳定的官方第三方自动调用接口：

V0.2 可以暂时无法：

```text
Alt+Q
→ 自动让 ChatGPT 回答
→ 自动把答案显示回 StudyCopilot
```

不要伪造这一能力。

但是 V0.2 必须显著减少当前 V0.1 的操作步骤。

目标是：

从：

```text
复制文字
→ 粘贴 StudyCopilot
→ 生成 Prompt
→ 复制
→ 切 GPT
→ 粘贴
```

至少改进为：

```text
Alt+Q
→ 框选
→ Prepare for AI
→ ChatGPT
```

并为未来官方 Integration 保留接口。

---

# 44. 如果存在可靠的 Windows 原生能力，可以利用

可以合理使用：

- PySide6
- Qt Screenshot APIs
- pywin32
- ctypes
- Windows Clipboard
- Windows foreground window APIs

优先：

稳定
简单
维护成本低

不要为了截图引入巨大依赖。

---

# 45. 测试要求

保留 V0.1 测试。

不得为了 V0.2 删除旧测试来“让测试通过”。

新增至少测试：

- Screenshot metadata model
- Screenshot DB migration
- screenshot path generation
- ContextPackage with screenshot
- ContextPackage without text
- ContextPackage with text + screenshot
- temporary / persistent screenshot state
- missing Project
- missing Source
- cancelled screenshot
- invalid tiny region
- screenshot task type
- fallback visual handoff formatting
- recent context storage

GUI / Windows 截图无法完全自动化的部分：

写清楚 manual test。

---

# 46. Manual Test 场景

开发完成后必须让我实际测试：

## Test A — 扫描 PDF 翻译

```text
1. 启动 StudyCopilot
2. 打开扫描版 PDF
3. 按 Alt+Q
4. 框选：
   英文正文 + 公式
5. 松开鼠标
6. StudyCopilot 显示截图缩略图
7. Project / Source 正确或允许选择
8. Prepare for AI
9. 将截图和上下文提供给 ChatGPT
10. ChatGPT 可以直接进行视觉翻译
```

## Test B — 电路图

框选：

```text
电路图 + 正文 + 公式
```

确认截图：

- 清晰；
- 没有遮罩；
- 没有严重缩放错误。

## Test C — Cancel

```text
Alt+Q
→ Esc
```

应用正常恢复。

## Test D — Text Capture Regression

原有文字 Capture 仍然可用。

---

# 47. V0.2 成功标准

V0.2 成功不是：

“增加了截图模块。”

真正成功标准是：

> 用户阅读扫描版 PDF 时，不再需要先手动提取文字。

用户应该能够：

```text
Alt+Q
↓
框选
↓
得到 Screenshot Context
↓
最少步骤交给 AI
```

并且：

- Project 保留；
- Source 保留；
- Memory 保留；
- Context 保留；
- GPT/Claude 可迁移架构保留。

---

# 48. 不要为了 V0.2 重做 V0.1

再次强调：

当前项目已经完成 V0.1。

不要：

- 重新初始化整个项目；
- 重建已有数据库；
- 重写所有 Project 代码；
- 重写所有 Memory 代码；
- 重写所有 Context 代码；
- 重新做已经通过测试的 V0.1 功能。

正确流程：

```text
Audit V0.1
↓
Identify reusable modules
↓
Create migration
↓
Add Screenshot Capture
↓
Extend Context
↓
Extend Integration
↓
Refactor UI
↓
Regression Test
```

---

# 49. AGENTS.md 更新

不要覆盖掉有价值的原内容。

在现有 AGENTS.md 中加入或强化：

```text
Screenshot First
Vision Before OCR for visual understanding
Reading UX Before Knowledge Graph Complexity
AI Prompt Is an Implementation Detail
Minimize User Workflow Steps
Preserve Existing User Data
Incremental Migration
```

原有：

```text
Local First
Model Independent
Client Independent
Memory Belongs to User
Project-Aware
Concept-Aware
Minimum Sufficient Context
No Automatic Summarization
Avoid Vendor Lock-In
Low Cost
Privacy by Default
```

继续保留。

---

# 50. 后续路线调整

记录但不要全部实现。

## V0.2

当前版本：

Screenshot-First Capture + Visual Context + UI 重构。

## V0.3

连续问答体验：

```text
Current Screenshot
+
Recent Screenshot
+
Question
+
Memory
```

## V0.4

更好的官方 AI Client Integration。

目标：

进一步减少：

```text
Prepare
→ Switch
→ Paste
```

操作。

## V0.5

OCR / Local Index。

主要用于：

- 搜索扫描教材；
- 页面索引；
- Concept Detection。

不是替代 Vision。

## V0.6

Cross-Project Knowledge Linking。

例如：

```text
半导体器件：
channel-length modulation

↓

模拟电路：
MOSFET output resistance ro
```

## V0.7

更好的 Memory Intelligence。

## V0.8

多设备同步。

---

# 51. 当前开发执行顺序

现在直接开始。

不要先给我长篇架构报告。

执行：

1. 阅读当前项目全部关键代码；
2. 阅读 AGENTS.md；
3. 阅读 README；
4. 检查现有数据库 Schema；
5. 运行现有测试；
6. 确认 V0.1 baseline；
7. 不修改功能的情况下记录 baseline；
8. 设计最小增量 migration；
9. 实现 Region Screenshot Capture；
10. 实现截图 metadata；
11. 扩展 StudyContext；
12. 扩展 ContextPackage；
13. 更新 translation/explain prompt；
14. 实现 Screenshot Preview；
15. 重构 Sidebar；
16. 把 Prompt/Concept/Memory 技术细节移动到 Advanced/Details；
17. 实现 Alt+Q Screenshot Translate；
18. 如果稳定，实现 Alt+A Screenshot Explain；
19. 保留现有 Text Capture；
20. 改进 Prepare for AI；
21. 实现 Recent Visual Context 基础；
22. 添加测试；
23. 运行全部旧测试；
24. 运行全部新测试；
25. 修复 regression；
26. 启动 GUI；
27. 检查日志；
28. 完成 Windows manual test 能自动完成的部分；
29. 给用户明确的人工实测步骤。

---

# 52. 工程决策原则

如果两个方案之间需要选择：

优先：

```text
1. 实际阅读体验
2. 截图可靠性
3. 保留用户数据
4. 模型可迁移
5. 本地优先
6. 少操作步骤
7. 低成本
8. 可维护
9. 自动化
10. 技术复杂度
```

不要为了技术优雅牺牲实际体验。

---

# 53. 最终汇报

完成这一轮后，只需要告诉我：

## V0.1 Baseline

你确认原项目已经有哪些能力。

## V0.2 已完成

实际新增 / 修改了什么。

## Regression Test

V0.1 哪些功能确认仍然正常。

## New Tests

新增测试结果。

## 如何运行

给具体命令。

## 如何测试扫描版 PDF

明确告诉我：

```text
打开 PDF
→ Alt+Q
→ 怎么框选
→ 松开后看到什么
→ 怎么交给 ChatGPT
```

## 当前 AI Handoff

明确说明现在：

- 是否能一次复制图片 + Prompt；
- 是否需要两步；
- 是否需要切换 ChatGPT；
- 哪些部分受官方客户端能力限制。

不要隐藏这些限制。

## 下一步

最多提出 3 个最有价值的下一步。

---

# 54. 最后的产品判断标准

开发过程中不断问：

> “这个改动有没有让用户阅读扫描版教材更快？”

如果没有：

它可能不是 V0.2 的优先事项。

当前最重要目标不是让 StudyCopilot 拥有最多功能。

而是让下面这件事变得足够自然：

```text
看到教材中不懂的地方
↓
Alt+Q
↓
框起来
↓
AI 看懂它
↓
翻译 / 解释
↓
继续阅读
```

StudyCopilot 应该逐渐消失在这个过程中，而不是让用户为了使用 AI 先操作 StudyCopilot 本身。

现在请基于已经完成的 V0.1，直接开始 StudyCopilot V0.2 的增量重构。