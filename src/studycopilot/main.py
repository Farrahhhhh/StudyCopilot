from __future__ import annotations

import argparse
import logging
from logging.handlers import RotatingFileHandler
import os
import sys

from studycopilot.config import Settings
from studycopilot.knowledge.concepts import ConceptStore
from studycopilot.memory.database import Database
from studycopilot.memory.store import MemoryStore
from studycopilot.projects.manager import ProjectManager


def initialize(settings: Settings) -> Database:
    db = Database(settings.database_path)
    try:
        if not ProjectManager(db).list_projects():
            ProjectManager(db).create_project("未分类")
        MemoryStore(db).seed_preferences()
        ConceptStore(db).seed_terminology()
    except Exception:
        db.close()
        raise
    return db


def configure_logging(settings: Settings) -> None:
    settings.log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(settings.log_path, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="StudyCopilot V0.3 · 本地学习上下文侧栏")
    parser.add_argument("--enable-auto-translate", action="store_true",
                        help="启用截图后自动发送到 ChatGPT 订阅；以后可在界面关闭")
    parser.add_argument("--reading-model", help="保存视觉模型选择，发送前按官方列表核对")
    parser.add_argument("--home", help="数据与日志根目录，默认是项目目录")
    parser.add_argument("--init-db", action="store_true", help="初始化/迁移数据库后退出")
    parser.add_argument("--hotkey", choices=["Alt+Q", "Alt+Shift+Q"], default="Alt+Q", help="V0.1 兼容参数；V0.2 文字采集固定 Alt+Shift+Q")
    parser.add_argument("--no-hotkey", action="store_true", help="不注册任何全局快捷键；保留截图按钮与文字输入")
    parser.add_argument("--smoke-test", action="store_true", help="创建界面后自动关闭，不注册全局快捷键")
    args = parser.parse_args(argv)
    settings = Settings.load(args.home)
    configure_logging(settings)
    logger = logging.getLogger(__name__)
    if args.init_db:
        db = initialize(settings)
        db.close()
        print(f"Database ready: {settings.database_path}")
        return 0

    from PySide6.QtCore import QLockFile, QTimer
    from PySide6.QtWidgets import QApplication, QMessageBox
    from studycopilot.ui.controller import SidebarController
    from studycopilot.ui.sidebar import Sidebar

    app = QApplication([sys.argv[0]])
    app.setApplicationName("StudyCopilot")
    app.setOrganizationName("StudyCopilot")
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(settings.database_path.parent / "app.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(0):
        QMessageBox.information(None, "StudyCopilot", "该数据目录已被另一个 StudyCopilot 使用，请先关闭已有窗口。")
        return 1
    try:
        db = initialize(settings)
    except Exception as error:
        logger.error("initialization failed kind=%s", type(error).__name__)
        QMessageBox.critical(None, "无法启动", "本地数据库初始化失败。请检查目录权限或应用版本；不要删除原数据库。")
        lock.unlock()
        return 1
    view = Sidebar()
    controller = SidebarController(view, db, auto_connect=not args.smoke_test)
    if args.reading_model:
        controller.reading.model = args.reading_model
        controller.reading.persist("reading_model", args.reading_model)
    if args.enable_auto_translate and not args.smoke_test:
        view.auto_translate.setChecked(True)
    from studycopilot.capture.runtime import CaptureRuntime
    runtime = CaptureRuntime(app, controller, no_hotkey=args.no_hotkey or args.smoke_test)

    previous_hook = sys.excepthook

    def handle_exception(error_type, error, traceback):
        # Never log exception messages, local variables or selected text.
        logger.error("unhandled exception kind=%s", error_type.__name__)
        controller.message("操作发生错误，请重试；日志只记录了错误类型。")

    sys.excepthook = handle_exception
    view.place_right()
    view.show()
    logger.info("application started version=0.3.2")
    if args.smoke_test:
        QTimer.singleShot(500, view.close)
    try:
        return app.exec()
    finally:
        runtime.close()
        controller.close()
        db.close()
        lock.unlock()
        sys.excepthook = previous_hook
        logger.info("application stopped")


if __name__ == "__main__":
    raise SystemExit(main())
