# V0.1 验证记录

日期：2026-09-09；Windows x64；Python 3.12.14；PySide6 Essentials 6.11.2；pytest 9.1.1。

## 已完成的验证

| 检查 | 结果 | 证据 / 边界 |
| --- | --- | --- |
| 原始任务保存 | 通过 | PROJECT_TASK.md 与原附件的 SHA-256 完全相同 |
| Python 编译 | 通过 | src、tests、scripts 的 compileall 无错误 |
| 自动化测试 | **53 passed** | test-results/pytest.xml；独立临时数据库与离屏 Qt |
| SQLite 初始化 | 通过 | data/study.db；user_version=1；默认项目和术语初始化 |
| migration | 通过 | 重复初始化保留数据；失败事务回滚；拒绝修改更高版本 schema |
| 数据与知识层 | 通过 | 项目/Source 归属、Session 切换、Concept、Aliases、Links |
| Memory / Retrieval | 通过 | project / global / user，FTS5 中英文、排序、其他项目隔离、索引更新/删除 |
| Context Package | 通过 | Partial Context、原文 JSON 往返、预算上限、模板和完整 Prompt |
| 采集状态机 | 通过 | 模拟慢速响应、同文复制、空文字、超时、防抖、修饰键等待和窗口变化 |
| 剪贴板快照 | 通过 | Qt MIME 文本、HTML、图片、URL、自定义二进制格式、大小限制、竞争变化 |
| Ctrl+C 构造 | 通过 | SendInput 结构大小、按下/释放顺序；使用 fake API，没有向其他软件发按键 |
| 热键消息桥接 | 通过 | WM_HOTKEY 解析、解除注册、1409 冲突回退、其他错误路径 |
| Windows API | 通过 | 实际加载 user32/kernel32，读取剪贴板序号和前台 HWND；不采集用户正文 |
| 侧栏工作流 | 通过 | 创建项目/Source、合成选文、保存 Memory、复制 Prompt、切换项目清空旧上下文 |
| 界面外观 | 通过 | 使用 Windows 原生 Qt 渲染本应用 QWidget，人工检查中文与布局；仅合成测试资料 |
| 启动与关闭 | 通过 | --smoke-test 返回 0；日志包含 application started / stopped |
| 依赖一致性 | 通过 | pip check: No broken requirements found |
| 当前可见应用 | 已启动 | 窗口 StudyCopilot · 学习上下文；logs/app.log 记录启动成功 |

## 本机快捷键情况

实际 Win32 探测表明：

- Alt+Q 被本机其他软件占用，RegisterHotKey 返回错误 **1409**。
- Alt+Shift+Q 在探测时可用。
- 应用保留 Alt+Q 为默认，只有错误 1409 时自动尝试 Alt+Shift+Q；不抢占其他软件的快捷键。
- 最新运行日志已确认：**hotkey registered shortcut=Alt+Shift+Q**。
- 界面显示实际快捷键；如果两个组合均不可用，保留手动粘贴。

最早启动的 hotkey unavailable 警告属于发现并处理冲突前的运行记录。

## 未完成的外部端到端验证

**尚未通过自动化验证真实 Foxit / Edge 阅读器中的“物理快捷键 → Ctrl+C → 剪贴板恢复 → 侧栏”整条链路。**

Windows computer-use 工具在初始化时连续失败，重置重试后仍报告：

> windows sandbox failed: helper_unknown_error: setup refresh had errors

这不是用户资料或应用运行错误。已完成代码、状态机、原生 API、Qt 窗口渲染与启动验证，但不能把这些测试等同于所有 PDF 阅读器兼容性测试。

## 用户验收步骤

1. 当前应用已打开，创建或选择「模拟电子技术」。
2. 添加或选择「Microelectronic Circuits」作为 Source。
3. 在含文字层且允许复制的 PDF 中选中一段英文。
4. 按下并松开界面显示的快捷键；**本机当前为 Alt+Shift+Q**。
5. 检查原文、进程名称、窗口标题和资料建议是否正确。
6. 如需检查恢复：事先复制一小段测试文字；采集完成后，在点击「复制给 AI」前粘贴到自己空白文档中，确认恢复情况。
7. 保存一条包含选文关键词或关联 Concept 的学习记忆，检查「相关记忆」。
8. 点击「复制给 AI」，粘贴到自己的 AI 对话中，确认项目、资料、选文、偏好与记忆齐全。
9. 切换另一个项目，确认旧项目选文清空、局部记忆没有混入。
10. 关闭再启动应用，确认已保存的项目、资料和 Memory 仍在。

也可用 scripts/reader_fixture.py 的合成文字先手动测试 1200 ms 延迟复制，避免接触个人 PDF。

## 开发产物位置

- 测试报告：test-results/pytest.xml
- 合成界面图：test-results/sidebar.png、test-results/prompt-preview.png
- 测试界面数据：test-results/render-data/
- 冒烟运行日志：test-results/smoke/logs/app.log
- 实际应用日志：logs/app.log
- 测试数据和图片均被 Git 排除，不会进入源码提交。

## 安装验证

默认大包下载超时、镜像 TLS 失败后，从 PyPI 官方地址分段获取 Qt Essentials wheel，并与 PyPI 元数据中的 SHA-256 比较成功：

c8a29def77032773a30879f7f24415b5395ad08592d147c170824ef4c735dfc1

随后从已校验的本地 wheel 安装。没有绕过 TLS 验证，没有安装未校验来源的软件。实际依赖版本记录在 constraints-tested.txt。
