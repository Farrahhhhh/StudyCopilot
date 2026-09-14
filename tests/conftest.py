import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication
from studycopilot.memory.database import Database
from studycopilot.memory.store import MemoryStore
from studycopilot.projects.manager import ProjectManager


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "study.db")
    yield database
    database.close()


@pytest.fixture
def project(db):
    return ProjectManager(db).create_project("模拟电子技术")


@pytest.fixture
def memories(db):
    return MemoryStore(db)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app
    # Release Python-owned image MIME data while the Qt application is still alive.
    app.clipboard().clear()
    app.processEvents()
