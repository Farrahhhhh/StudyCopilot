# StudyCopilot Agent Guide

## Mission
帮助用户阅读复杂 STEM 内容，提供翻译、理解、问答、长期学习记忆与跨资料知识联动。完整需求见 `PROJECT_TASK.md`。

## Current Priority Domains
Analog Electronics, Analog Circuits, Microelectronic Circuits, Semiconductor Devices.

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

## Current scope and implementation rules
- V0.1/V0.2 are complete. User-approved current scope: V0.3 screenshot → automatic real translation → in-sidebar response and bounded follow-up through official Codex App Server with ChatGPT subscription. No OCR, paid API provider, PDF reader, cloud sync or automatic summaries.
- Automatic sending is opt-in and persists; a subsequent explicit capture is the send action. Never send existing stored images merely on startup or enabling the option.
- Use official managed authentication; never read auth.json, tokens or cookies. Do not buy/redeem quota or fall back to paid API automatically.
- Reading requests must be ephemeral, without environment/tool capabilities; reject unexpected tool requests. Scope responses by request/thread/turn and project/source/session.
- Preserve original V0.1/V0.2 regression behavior. SQLite v3 adds bounded completed reading results; incomplete output is never persisted as success.
- Keep UI, capture, projects, context, knowledge, memory, integrations and providers separate. Prompts belong in Markdown resources.
- SQLite is authoritative. Migrate transactionally; never delete user data to fix a schema problem. Enable foreign keys on every connection.
- Project memory must never leak into unrelated projects. Cross-project retrieval is disabled in V0.1.
- Do not log selected text, memory contents, credentials or generated prompts. Do not capture screenshots without explicit user action.
- Windows capture must be bounded, debounced, nonblocking, and restore supported clipboard formats when safe.
- Use Python 3.11+, PySide6, sqlite3 and dataclasses; avoid unnecessary dependencies.
- Run `python -m pytest` after changes affecting behavior. Document untested external reader behavior honestly.
- README must provide concrete Windows commands and plain Chinese instructions.

- If Git reports the known sandbox-owner mismatch, use a per-command safe.directory override limited to the current checkout. Do not add a wildcard global trust setting.

## V0.2 priorities
- Screenshot First; Vision Before OCR for visual understanding.
- Reading UX Before Knowledge Graph Complexity.
- AI Prompt Is an Implementation Detail: default UI shows screenshot, real response and follow-up; manual handoff stays in More.
- Minimize User Workflow Steps; never promise combined image/text paste without client verification.
- Preserve Existing User Data; incremental migration with backup, never database recreation.
- Region capture only on explicit user shortcut/button. Never background-monitor the screen.
- Alt+Q: screenshot translation; Alt+A: screenshot explanation; Alt+Shift+Q: legacy text capture.
- Keep V0.1 regression tests. Update version expectations when schema advances; do not drop behavior coverage.
- Requirements are PROJECT_TASK.md, PROJECT_TASK_V0.2.md and PROJECT_TASK_V0.3.md; the latest user-approved V0.3 scope wins where they differ.
