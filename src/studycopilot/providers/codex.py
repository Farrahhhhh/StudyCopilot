"""Official subscription transport. GUI-safe QProcess, bounded RPCs, no browser automation."""
from __future__ import annotations

from importlib.resources import files
import json
import logging
from pathlib import Path
import time
from urllib.parse import urlparse

from PySide6.QtCore import QProcess, QProcessEnvironment, QTimer

from .codex_config import child_environment, executable, launch_arguments, thread_parameters
from .reading import ReadingProvider, ReadingRequest


def error_message(error: dict) -> tuple[str, str]:
    """Never surface raw protocol payloads, auth details or prompt text."""
    detail = error.get("codexErrorInfo")
    message = str(error.get("message", "")).lower()
    if detail == "usageLimitExceeded" or "usage limit" in message or "rate limit" in message:
        return "rate_limited", "订阅额度暂时用尽，请恢复额度后点重试；不会自动改用付费 API。"
    if "auth" in message or "unauthorized" in message or "login" in message:
        return "needs_login", "登录已失效，请在设置中重新连接 ChatGPT。"
    if "model" in message and ("not" in message or "support" in message):
        return "model_unavailable", "所选模型当前不可用，请在设置中选择可用的视觉模型。"
    if "timed out" in message or "timeout" in message:
        return "timeout", "翻译服务响应超时，图片已保留，可以重试。"
    return "service_error", "翻译服务暂时不可用，图片已保留，请检查网络后重试。"


logger = logging.getLogger(__name__)


class CodexProvider(ReadingProvider):
    MAX_BUFFER = 4 * 1024 * 1024
    MAX_ANSWER = 100_000

    def __init__(self, runtime: Path, parent=None):
        super().__init__(parent)
        self.runtime = runtime.resolve()
        self.process = None
        self.buffer = b""
        self.serial = 0
        self.callbacks = {}
        self.ready = False
        self.closed = False
        self.state = "disconnected"
        self.models = []
        self.current: ReadingRequest | None = None
        self.thread_id = None
        self.turn_id = None
        self.actual_model = ""
        self.item_text = {}
        self.item_phases = {}
        self.finished_text = ""
        self.login_requested = False
        self.login_id = None
        self.started_at = 0.0
        self.first_text_seconds = None
        self.deadline = QTimer(self)
        self.deadline.setSingleShot(True)
        self.deadline.timeout.connect(lambda: self._fail("timeout", "翻译等待超时，图片已保留，可以重试。"))
        self.rpc_clock = QTimer(self)
        self.rpc_clock.setInterval(1000)
        self.rpc_clock.timeout.connect(self._check_rpcs)

    def _status(self, state, message):
        self.state = state
        self.connection_changed.emit(state, message)

    def connect_service(self):
        if self.closed or self.state == "connecting":
            return
        if self.current and (self.thread_id or self.ready):
            return
        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            self._status("connecting", "正在检查 ChatGPT 订阅……")
            self.deadline.start(45000)
            self._rpc("account/read", {"refreshToken": False}, self._account)
            return
        try:
            command, args = executable(), launch_arguments(self.runtime)
        except (ValueError, OSError) as error:
            self._fail("configuration", str(error))
            return
        self.ready = False
        self.buffer = b""
        proc = QProcess(self)
        self.process = proc
        env = QProcessEnvironment()
        for key, value in child_environment().items():
            env.insert(key, value)
        proc.setProcessEnvironment(env)
        proc.setWorkingDirectory(str(self.runtime))
        proc.setProgram(command)
        proc.setArguments(args)
        proc.started.connect(lambda: self._started(proc))
        proc.readyReadStandardOutput.connect(lambda: self._read(proc))
        # CLI diagnostics can contain paths/payloads: drain without logging or showing them.
        proc.readyReadStandardError.connect(lambda: proc.readAllStandardError())
        proc.errorOccurred.connect(lambda _: self._process_error(proc))
        proc.finished.connect(lambda *_: self._process_finished(proc))
        self._status("connecting", "正在连接 ChatGPT 订阅……")
        self.rpc_clock.start()
        self.deadline.start(45000)
        proc.start()

    def _started(self, proc):
        if proc is not self.process:
            return
        self._rpc("initialize", {
            "clientInfo": {"name": "studycopilot", "title": "StudyCopilot", "version": "0.3.1"},
            "capabilities": {"experimentalApi": True},
        }, self._initialized)

    def _initialized(self, result):
        self._notify("initialized")
        self._rpc("account/read", {"refreshToken": False}, self._account)

    def _account(self, result):
        account = result.get("account") or {}
        if account.get("type") != "chatgpt":
            self.ready = False
            if self.login_requested:
                self.login_requested = False
                self._rpc("account/login/start", {"type": "chatgpt"}, self._login_started)
                self.deadline.start(180000)
                return
            self._fail("needs_login", "请先连接 ChatGPT 订阅。不会使用 API Key 自动扣费。", stop=False)
            return
        self.login_requested = False
        self.login_id = None
        self.models = []
        self._rpc("model/list", {"includeHidden": False}, self._models)

    def _models(self, result):
        self.models = [m for m in result.get("data", [])
                       if "image" in (m.get("inputModalities") or []) and not m.get("hidden")]
        self.models_changed.emit(self.models)
        if not self.models:
            self._fail("model_unavailable", "当前账号没有公布可用的视觉模型，请稍后重新连接。")
            return
        self._rpc("account/rateLimits/read", {}, self._limits)

    def _limits(self, result):
        limits = (result.get("rateLimitsByLimitId") or {}).get("codex") or result.get("rateLimits") or {}
        blocked = any((limits.get(key) or {}).get("usedPercent", 0) >= 100
                      for key in ("primary", "secondary"))
        if blocked or limits.get("spendControlReached"):
            self._fail("rate_limited", "订阅额度暂时用尽，恢复后点击重新连接；不会自动购买额度。", stop=False)
            return
        if self.models:
            self._connected()

    def _connected(self):
        self.ready = True
        self.deadline.stop()
        self._status("ready", "已连接 ChatGPT 订阅")
        if self.current and not self.thread_id:
            self._begin_request()

    def login(self):
        self.login_requested = True
        self.connect_service()

    def _login_started(self, result):
        url = result.get("authUrl", "")
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in {"auth.openai.com", "chatgpt.com"}:
            self._fail("configuration", "官方登录地址无法核对，请使用 Codex 官方登录后重新连接。")
            return
        self.login_id = result.get("loginId")
        self._status("needs_login", "请在官方浏览器页面完成登录，再返回这里。")
        self.login_url.emit(url)

    def submit(self, request):
        if self.current:
            self.cancel()
        if request.image_path is not None:
            from PySide6.QtGui import QImage
            if not request.image_path.is_file() or QImage(str(request.image_path)).isNull():
                self.failed.emit(request.id, "image_missing", "当前截图缺失或损坏，请重新截图。")
                return
        self.current = request
        self.thread_id = self.turn_id = None
        self.item_text = {}
        self.item_phases = {}
        self.finished_text = ""
        self.started_at = time.monotonic()
        self.first_text_seconds = None
        self.deadline.start(90000)
        if self.ready:
            self._begin_request()
        else:
            self.connect_service()

    def _begin_request(self):
        if not self.current:
            return
        self.request_progress.emit(self.current.id, "preparing")
        desired = self.current.model
        selected = next((m for m in self.models if m["model"] == desired), None) if desired else next(
            (m for m in self.models if m.get("isDefault")), self.models[0])
        if not selected:
            self._fail("model_unavailable", "所选模型已不可用，请在设置中选择模型；未自动替换。")
            return
        self.actual_model = selected["model"]
        supported = [e["reasoningEffort"] for e in selected.get("supportedReasoningEfforts", [])]
        self.effort = next((e for e in ("none", "minimal", "low") if e in supported),
                           selected.get("defaultReasoningEffort", "low"))
        instructions = files("studycopilot").joinpath("prompts/reading_system.md").read_text(encoding="utf-8")
        self.deadline.start(90000)
        self._rpc("thread/start", thread_parameters(self.runtime, self.actual_model, instructions),
                  self._thread_started, self.current.id)

    def _thread_started(self, result):
        if not self.current:
            return
        thread = result.get("thread") or {}
        if (not thread.get("ephemeral") or result.get("instructionSources")
                or (result.get("sandbox") or {}).get("type") != "readOnly"):
            self._fail("isolation", "当前 Codex 版本的阅读隔离检查未通过，未发送图片。")
            return
        self.thread_id = thread["id"]
        items = [{"type": "text", "text": self.current.prompt}]
        if self.current.image_path:
            items.append({"type": "localImage", "path": str(self.current.image_path)})
        self.request_progress.emit(self.current.id, "waiting")
        self._rpc("turn/start", {
            "threadId": self.thread_id, "input": items, "effort": self.effort,
            "environments": [], "serviceTierForTurn": "default",
        }, self._turn_started, self.current.id)

    def _turn_started(self, result):
        if self.current:
            self.turn_id = result["turn"]["id"]

    def _read(self, proc):
        if proc is not self.process:
            proc.readAllStandardOutput()
            return
        self.buffer += bytes(proc.readAllStandardOutput())
        if len(self.buffer) > self.MAX_BUFFER:
            self._fail("protocol", "翻译服务返回异常数据，已停止。")
            return
        while b"\n" in self.buffer:
            line, self.buffer = self.buffer.split(b"\n", 1)
            if not line.strip():
                continue
            try:
                message = json.loads(line)
                if not isinstance(message, dict):
                    raise ValueError()
            except (ValueError, UnicodeError):
                self._fail("protocol", "翻译服务协议不兼容，请更新官方 Codex 后重试。")
                return
            try:
                self.handle_message(message)
            except (AttributeError, KeyError, TypeError, ValueError):
                self._fail("protocol", "服务返回格式不兼容，请更新官方 Codex 后重新连接。")
                return

    def handle_message(self, message):
        if "id" in message and "method" in message:
            # This client never grants tool, permission, or credential requests.
            self._write({"id": message["id"], "error": {
                "code": -32601, "message": "Tools are disabled in this reading client."}})
            self._fail("tool_blocked", "翻译请求意外要求工具权限，已停止。")
            return
        if "id" in message:
            entry = self.callbacks.pop(message["id"], None)
            if not entry:
                return
            callback, expires, request_id = entry
            if request_id and (not self.current or self.current.id != request_id):
                return
            if "error" in message:
                code, text = error_message(message["error"])
                self._fail(code, text)
            else:
                callback(message.get("result") or {})
            return
        method, params = message.get("method"), message.get("params") or {}
        if method == "account/login/completed":
            if params.get("success"):
                self._rpc("account/read", {"refreshToken": False}, self._account)
            else:
                self._fail("needs_login", "登录没有完成，请重新连接。", stop=False)
            return
        if not self.current or params.get("threadId") != self.thread_id:
            return
        event_turn = params.get("turnId") or (params.get("turn") or {}).get("id")
        if self.turn_id and event_turn and self.turn_id != event_turn:
            return
        if method == "turn/started":
            self.turn_id = (params.get("turn") or {}).get("id") or self.turn_id
        elif method in ("item/started", "item/completed"):
            item = params.get("item") or {}
            kind, item_id = item.get("type"), item.get("id")
            if kind not in {"userMessage", "agentMessage", "reasoning", "contextCompaction"}:
                self._fail("tool_blocked", "翻译请求出现不需要的工具操作，已停止。")
                return
            if kind == "agentMessage":
                self.item_phases[item_id] = item.get("phase")
                if method == "item/completed":
                    self.item_text[item_id] = item.get("text", "")
                    if item.get("phase") != "commentary":
                        self.finished_text = item.get("text", "")
                        self._emit_text()
        elif method == "item/agentMessage/delta":
            item_id = params.get("itemId")
            self.item_text[item_id] = self.item_text.get(item_id, "") + params.get("delta", "")
            self._emit_text()
        elif method == "error":
            code, text = error_message(params.get("error") or {})
            self._fail(code, text)  # no hidden retries after a failed stream
        elif method == "turn/completed":
            turn = params.get("turn") or {}
            if turn.get("status") != "completed":
                code, text = error_message(turn.get("error") or {})
                self._fail(code, text)
                return
            answer = self.finished_text or self._visible_text()
            if not answer.strip():
                self._fail("empty_answer", "服务没有返回译文，图片已保留，可以重试。")
                return
            logger.info("reading completed seconds=%.3f", time.monotonic() - self.started_at)
            request_id, thread_id = self.current.id, self.thread_id
            self.current = None
            self.thread_id = self.turn_id = None
            self.deadline.stop()
            self.completed.emit(request_id, answer, self.actual_model)
            self._rpc("thread/unsubscribe", {"threadId": thread_id}, None)

    def _visible_text(self):
        return "\n\n".join(text for item, text in self.item_text.items()
                           if self.item_phases.get(item) != "commentary")

    def _emit_text(self):
        if not self.current:
            return
        text = self._visible_text()
        if len(text) > self.MAX_ANSWER:
            self._fail("answer_too_long", "回复超过本次阅读长度上限，已停止，请缩小选区。")
            return
        if text:
            if self.first_text_seconds is None:
                self.first_text_seconds = time.monotonic() - self.started_at
                logger.info("reading first_text seconds=%.3f", self.first_text_seconds)
            self.text_changed.emit(self.current.id, text)

    def _rpc(self, method, params, callback, request_id=None):
        self.serial += 1
        if callback is not None:
            self.callbacks[self.serial] = (callback, time.monotonic() + 40, request_id)
        self._write({"id": self.serial, "method": method, "params": params})

    def _notify(self, method):
        self._write({"method": method})

    def _write(self, message):
        if self.process and self.process.state() == QProcess.ProcessState.Running:
            self.process.write((json.dumps(message, ensure_ascii=False) + "\n").encode("utf-8"))

    def _check_rpcs(self):
        if any(expiry < time.monotonic() for _, expiry, _ in self.callbacks.values()):
            self._fail("timeout", "连接服务超时，请检查网络后重试。")

    def _process_error(self, proc):
        if proc is self.process:
            self._fail("connection", "无法启动官方翻译连接，请检查 Codex 安装与配置。")

    def _process_finished(self, proc):
        if proc is self.process:
            self._fail("connection", "翻译连接已断开，图片已保留，可以重新连接。")

    def _fail(self, code, message, stop=True):
        request_id = self.current.id if self.current else None
        self.current = None
        self.ready = False
        self.thread_id = self.turn_id = None
        self.deadline.stop()
        if stop:
            self._stop_process()
        self._status(code, message)
        if request_id:
            self.failed.emit(request_id, code, message)

    def cancel(self):
        request_id = self.current.id if self.current else None
        thread_id, turn_id = self.thread_id, self.turn_id
        self.current = None
        self.thread_id = self.turn_id = None
        self.deadline.stop()
        # Ignore outstanding RPCs for the retired request, including late turn/start.
        self.callbacks = {key: entry for key, entry in self.callbacks.items()
                          if not request_id or entry[2] != request_id}
        if self.ready and self.process and thread_id and turn_id:
            # Interrupt only this ephemeral turn, preserving the authenticated transport.
            self._rpc("turn/interrupt", {"threadId": thread_id, "turnId": turn_id}, None)
            self._rpc("thread/unsubscribe", {"threadId": thread_id}, None)
            logger.info("reading cancelled connection_reused=true")
            self._status("ready", "已连接 ChatGPT 订阅")
            return
        if self.ready and self.process and not request_id:
            return
        # Before a turn has an addressable id, restart safely instead of leaving it running.
        self.ready = False
        self._stop_process()
        self._status("disconnected", "已停止；下次翻译自动重新连接。")

    def _stop_process(self):
        proc, self.process = self.process, None
        self.callbacks.clear()
        self.buffer = b""
        self.rpc_clock.stop()
        if proc:
            proc.closeWriteChannel()
            proc.terminate()
            QTimer.singleShot(1500, proc, lambda: proc.kill() if proc.state() != QProcess.ProcessState.NotRunning else None)
            proc.finished.connect(proc.deleteLater)

    def close(self):
        self.closed = True
        self.current = None
        self.deadline.stop()
        self.ready = False
        proc = self.process
        self._stop_process()
        if proc and proc.state() != QProcess.ProcessState.NotRunning:
            # Bounded process reaping only during app shutdown.
            if not proc.waitForFinished(500):
                proc.kill()
                proc.waitForFinished(500)
