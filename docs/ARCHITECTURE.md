# StudyCopilot 架构（当前 0.3.1）

当前主流程：主动框选 → ScreenshotStore → ContextManager → ReadingWorkflow → 精简阅读请求 → CodexProvider → 侧栏流式回答 → ReadingStore。每次模型阅读使用独立临时会话，连接可以复用；完整交接说明仅用于备用手动路径。

下面按版本保留采集、本地知识与阅读连接的演进。V0.2 剪贴板数据流是历史及备用实现；当前能力以末尾 V0.3／V0.3.1 增量、README 和 STATUS.md 为准。

## 视觉数据流

主动按钮／热键 → CaptureRuntime → RegionCapture → ScreenshotStore → StudyContext → ContextManager → ContextPackage → ClipboardIntegration → 用户在 AI 客户端附图与粘贴说明。

- RegionCapture 只管理短期屏幕像素、遮罩与选择事件，不访问数据库。开始时隐藏本应用窗口，给合成器 160 ms 清场；先冻结所有屏幕再显示任何遮罩。裁切从原始帧缓冲提取，用实际物理图像尺寸／逻辑屏幕尺寸换算，不从遮罩窗口截图。没有后台截图循环。
- 遮罩有 120 秒取消期限，完成后 500 ms 防重复。Esc、右键、过小选区取消，代数 token 防止已取消的延迟回调重新显示遮罩。屏幕移除时取消。
- 每次仅裁切一块屏幕内的矩形；支持负坐标元数据，不实现跨屏拼接。屏幕抓取调用仍受 Qt／Windows 系统接口响应约束，不声称能中断底层驱动调用。
- CaptureRuntime 为 Alt+Q、Alt+A、Alt+Shift+Q 注册独立 ID。冲突时截图分别尝试 Ctrl+Alt+Q、Ctrl+Alt+A；旧文字输入不占用截图备用键。按钮入口与热键复用相同状态。
- VisualWorkflow 负责当前图片、最近上下文和交接界面的协调。SidebarController 保留 V0.1 的项目／资料／Session 管理。UI 中没有截图文件 SQL。
- 截图元数据 dataclass 使用相对文件路径；PNG 先写临时文件再替换，数据库插入失败时清理本次产生的文件。图片不塞入 SQLite。

## SQLite v2 与生命周期

新增 screenshots、memory_screenshots、recent_context；不更改 v1 表。Database 在升级之前做 SQLite online backup，migration 事务失败回滚，不删除重建。每个业务连接启用外键。

当前截图默认临时，保留最近 20 张临时图片；每次主动完成截图后尝试清理更旧的临时文件。当前保护 ID、已保留或已关联 Memory 的图片不清理。文件锁定或非法路径跳过，绝不按外部路径删除。

Memory 保存与图片关联／持久化在同一 SQLite 事务中，失败不留下半条记忆。手动资料修正仅允许同一项目中的临时图片重绑定；持久图片的历史归属不变化。

recent_context 每 Session 最多 20 条，存截图 ID、任务、明确输入的文字与问题、时间。检索严格匹配项目／资料／Session；UI 显示最近 5 张图片，ContextPackage 仅包含最多 2 张历史图片元数据和 2 条有用文字片段。当前图片才是交接附件，历史图片需用户另行附上。

## 上下文与交接

选文可空，截图可空，至少一个输入存在；项目、资料、Topic 允许部分缺失，但提供的 ID 必须归属一致。截图不经 OCR：Concept／Memory 检索仅基于明确输入的 Topic、文字或问题，不凭图片猜测关键词。

ContextPackage 沿用普通 JSON，增加 current_screenshot、recent_screenshots、session、question 和厂商无关附件描述。translation／explain 提示继续是独立 Markdown 资源。

ClipboardIntegration.prepare 验证图片并生成交接对象，copy_image 只放图片，原 copy 继续复制完整文本说明。外部客户端没有确认混合粘贴，因此明确两步，不自动上传或回收答案。官方路径评估见 AI_HANDOFF.md。

---

# V0.1 维护说明

## 边界

UI 只调用服务；SQL 在 projects、memory、knowledge、context 层。StudyContext 与 ContextPackage 使用 dataclass，导出为普通 JSON。Integration 负责生成文本；Provider 是未实现的独立 API 协议。

数据流：Win32 热键消息 → SelectionCapture → StudyContext → ContextManager → FTSMemoryRetriever / ConceptStore → ContextPackage → ClipboardIntegration → 用户主动复制。

## 采集状态机

1. 收到 Alt+Q，在 UI 主线程读取前台窗口与可恢复剪贴板格式；不显示或激活侧栏。
2. QTimer 每 40 ms 检查，最多等待 1.2 秒让 Alt/Q/修饰键松开。
3. 核对前台窗口与剪贴板序号仍未变化，发送一次 Ctrl+C。
4. 最多 2.2 秒轮询 GetClipboardSequenceNumber；不因文字与旧剪贴板相同而丢掉合法选择。
5. 读取选文，若剪贴板序号仍对应所读内容，恢复原 MIME 格式。
6. 完成后再展示侧栏，500 ms 内忽略重复触发。等待期间锁住项目与资料选择，防止归属变化。

不重复发送 Ctrl+C：对延迟复制的阅读器，多次请求可能在结束后覆写剪贴板。超出期限的极晚响应仍不能撤销。QClipboard 的 OS/OLE 调用本身由系统处理；定时轮询不会通过 sleep 阻塞 Qt 事件循环。

## 数据

SQLite 外键开启，WAL 模式，UTC ISO 时间、UUID。迁移使用事务和 PRAGMA user_version。较新 schema 不自动降级。FTS5 索引由触发器随 Memory 插入、更新、删除同步；更新内容时还需同步由 index_text 生成的 search_text。

英文基本分词，中文双字片段；FTS 查询只由安全 token 构造，用户原始 MATCH 语法不会直接执行。检索先在当前项目和 global 范围筛选，然后排序。user 范围作为学习偏好单独提供，最多 3 条。V0.1 不开启跨项目 project 记忆查询。

Concept 描述是全局术语，不是用户学习状态。Concept Aliases 完整词/短语匹配；Concept Links 与 source_concepts 提供程序层接口，V0.1 不做自动图扩展。用户学习状态在 Memory 中显式保存。

## 资源与依赖

安装 PySide6-Essentials，而非包含全部 Addons 的元包。界面仍使用 PySide6.QtWidgets。无额外热键库、ORM、模型 SDK 或网络客户端。测试采用 pytest 和 Qt 自身对象，不依赖另一个 GUI 测试框架。

参考的官方接口资料：

- [Qt 原生事件过滤器](https://doc.qt.io/qtforpython-6/PySide6/QtCore/QAbstractNativeEventFilter.html)
- [Microsoft RegisterHotKey](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-registerhotkey)
- [Microsoft Clipboard](https://learn.microsoft.com/en-us/windows/win32/dataxchg/using-the-clipboard)
- [Qt for Python 包组成](https://doc.qt.io/qtforpython-6/gettingstarted/package_details.html)

## 已知取舍

SQL store 使用轻量 dict 记录；核心上下文有明确 dataclass。V0.1 的数据量较小，Concept 别名在本地逐条扫描，FTS 候选再按项目优先排序。达到明显性能瓶颈后再改索引或查询，不提前引入向量服务。

日志不输出用户正文，也不输出异常消息中的参数；只记录异常类型。Memory 内容目前没有 UI 编辑/删除。V0.1/V0.2 翻译历史预留表保留，V0.3 实际回答使用独立 reading_results。


## V0.3 自动阅读增量

ReadingProvider 定义连接、登录、提交、取消和事件接口；CodexProvider 使用 QProcess 持续读取官方 App Server 的 stdio JSON-RPC，不在 UI 线程等待网络。模型来自实际视觉能力列表，显式失效选择不自动替换。process-local 配置禁用工具和继承 MCP，不修改全局设置或读取认证文件。environments=[]、ephemeral/readOnly/instructionSources 返回检查限制阅读会话。

ReadingWorkflow 捕获发送时 ContextPackage 快照，用请求 ID 与项目／资料／Session／图片键隔离增量和完成事件。新截图中断旧 turn 并退订，保留已建立连接；尚无可中断 ID 时安全重启。相同截图完成信号去重。生成阶段保留等待、流式、完成、取消和错误状态，完成后才能复制／保存回答。追问最多带最近两轮回答各 4000 字和有限既有上下文。服务连接可预热，但预热不发送图片。

模型返回采用 GitHub Markdown + 禁用 HTML 的本地 QTextBrowser；禁用链接与资源加载。常用数学转成可读文本，不支持的表达保留源码，不实现完整 LaTeX 排版。65ms 合并显示更新，限制协议缓冲 4MiB、回答 100000 字、普通 RPC 40 秒、生成 90 秒。关闭只回收本应用自己的连接。

SQLite v3 仅新增 reading_results 及索引，最多保留 60 条完成结果；按 project/source/session 精确恢复，截图清理通过外键级联。该表不是长期 Memory；长期保存仍走已有用户明确编辑确认流程。原 translation_history 是旧预留表，V0.3 不迁移或清空它。

V0.3.1 使用 integrations/reading.py 与独立 Markdown 任务资源生成最小阅读请求；内部归属、窗口标题、路径和空元数据不发送。request_progress 按请求 ID 更新等待阶段，500ms 刷新计时，首段出现／结束／取消／清除时停止等待计时。性能证据见 V0.3.1_LATENCY.md。
