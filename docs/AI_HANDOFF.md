# V0.2 AI 交接评估

> V0.3 已实现：官方 Codex App Server + ChatGPT 订阅已通过本项目真实图片翻译与侧栏回传验证；下文保留 V0.2 手动交接的历史评估。当前使用方式见 [README](../README.md)，实测数据见 [V0.3 验证记录](V0.3_VALIDATION.md)。


检查日期：2026-09-10。当前交付是本地图片 + 厂商无关说明的剪贴板交接。不需要另购 API，不登录、不读取认证信息、不代发内容。

## 为什么选择两步

Windows 允许剪贴板同时提供多种格式，接收程序会选择自己能处理的格式。多格式本身不能证明聊天客户端会把图片和文本一并附入输入框。参见 [Microsoft Clipboard Formats](https://learn.microsoft.com/en-us/windows/win32/dataxchg/clipboard-formats)。

已实现：

1. 准备给 AI：构建 ContextPackage 和独立 Markdown 说明，验证当前图片存在，复制原图。
2. 用户切换客户端并粘贴图片。
3. 复制说明：复制文本，用户在同一对话粘贴并确认发送。

图片剪贴板提供 Qt imageData 与 image/png；该操作有意只提供图片。随后复制文本会替换剪贴板。图片缺失或损坏时提示重截，界面不会继续声称图片已复制。原图文件仍在本地，可以按客户端正常附件操作手动选择。

已在 Windows Qt 剪贴板验证图像格式、原像素尺寸及后续文本复制；没有登录 ChatGPT／Claude，没有在真实对话中实测各版本粘贴，也没有验证一次图片＋文字混合粘贴。Claude 官方明确介绍了图像剪贴板粘贴，但这不是混合内容一次粘贴的保证：[Upload files to Claude](https://support.claude.com/en/articles/8241126-upload-files-to-claude)。

## 官方集成候选

| 路径 | 官方文档支持的方向 | 对 StudyCopilot 的判断 |
| --- | --- | --- |
| ChatGPT Apps／MCP | 通过开发者模式接入 MCP，配置、账户与工作区权限影响可用性；支持公开 HTTPS 服务或文档中的 Secure MCP Tunnel | 可以研究把项目相关的最小上下文暴露为工具；本轮不建服务器。不能据此承诺本地侧栏能自动驱动 Plus 对话并取回答案 |
| Claude Desktop local MCP | 桌面扩展／本地 MCP 可以提供工具和资源 | 和 Local First 较契合，未来可做只读、项目限定的接口；不等同于侧栏可通过 Pro 订阅任意远程调用模型 |
| 厂商 API | 属于独立的模型调用路线 | 保留 providers 抽象，不强制实现或购买 |
| 剪贴板／手动附件 | 使用用户现有客户端正常输入入口 | V0.2 正式路径；可由用户控制附图与发送 |

来源：[OpenAI 官方 MCP 连接文档](https://developers.openai.com/plugins/deploy/connect-chatgpt)、[Claude Desktop 本地 MCP 官方说明](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop)。

以上“对 StudyCopilot 的判断”为工程评估，不是对所有账户功能的承诺。当前文档没有为本项目验证一个“通过 Plus／Pro 订阅从本地侧栏自动发送图片、生成回答并回传”的完整官方接口。继续使用可检查的交接方式，不以私有接口补齐缺口。

## 内部边界

ContextPackage 保留项目、资料、Topic、Session、问题、辅助文字、相关知识与记忆。附件仅是相对路径、媒体类型和尺寸，不包含厂商 API 格式，不把图片二进制塞进 SQLite。

当前交接只复制一张当前图片。最近截图 metadata 可帮助说明学习连续性，但 AI 无法读取本机路径；模板要求不得假装看过未附上的图片。需要多图比较时由用户分别附图。

未来若实现官方 MCP，应从当前项目的只读资源开始，让用户明确选择共享范围。V0.2 没有启动此服务，也没有发生后台上传。
