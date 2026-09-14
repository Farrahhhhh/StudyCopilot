from .math_text import readable_markdown

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import QPlainTextEdit, QTextBrowser


class QuestionEdit(QPlainTextEdit):
    returnPressed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.limit = 1000
        self.setFixedHeight(52)
        self.textChanged.connect(self._limit)

    def text(self):
        return self.toPlainText()

    def setText(self, text):
        self.setPlainText(text[:self.limit])

    def setMaxLength(self, value):
        self.limit = value

    def _limit(self):
        if len(self.toPlainText()) > self.limit:
            cursor = self.textCursor()
            position = min(cursor.position(), self.limit)
            self.blockSignals(True)
            self.setPlainText(self.toPlainText()[:self.limit])
            cursor = self.textCursor()
            cursor.setPosition(position)
            self.setTextCursor(cursor)
            self.blockSignals(False)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not (
            event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        ):
            self.returnPressed.emit()
            event.accept()
        else:
            super().keyPressEvent(event)


class ReadingResult(QTextBrowser):
    """Render text safely without resolving remote images or activating links."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)
        self.setObjectName("ReadingResult")
        self.setMinimumHeight(175)

    def loadResource(self, resource_type, url):
        return None

    def show_answer(self, text):
        scroll = self.verticalScrollBar()
        position = scroll.value()
        follow_end = position >= scroll.maximum() - 12
        # MarkdownNoHTML avoids rendering arbitrary HTML from model output.
        self.document().setMarkdown(readable_markdown(text), QTextDocument.MarkdownFeature.MarkdownDialectGitHub | QTextDocument.MarkdownFeature.MarkdownNoHTML)
        scroll.setValue(scroll.maximum() if follow_end else min(position, scroll.maximum()))
