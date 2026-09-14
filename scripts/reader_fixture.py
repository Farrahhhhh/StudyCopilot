"""Visible, synthetic reader for opt-in Windows integration testing.
No personal files are opened. Ctrl+C can be delayed to simulate a slow PDF reader.
"""
import argparse
import sys
from PySide6.QtCore import QTimer
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication, QLabel, QPlainTextEdit, QVBoxLayout, QWidget

parser = argparse.ArgumentParser()
parser.add_argument("--delay-ms", type=int, default=1200)
args = parser.parse_args()
app = QApplication(sys.argv[:1])


class Reader(QPlainTextEdit):
    def keyPressEvent(self, event):
        if event.matches(QKeySequence.StandardKey.Copy):
            text = self.textCursor().selectedText().replace("\u2029", "\n")
            if text:
                QTimer.singleShot(args.delay_ms, lambda: app.clipboard().setText(text))
            event.accept()
        else:
            super().keyPressEvent(event)


window = QWidget()
window.setWindowTitle("Microelectronic Circuits.pdf - StudyCopilot Test Reader")
window.resize(700, 300)
layout = QVBoxLayout(window)
layout.addWidget(QLabel(f"测试阅读器 · Ctrl+C 延迟 {args.delay_ms} ms · 仅含合成测试文字"))
editor = Reader()
editor.setReadOnly(True)
editor.setPlainText("The source resistance introduces negative feedback.\n"
                    "The small-signal transconductance is denoted by g_m.")
layout.addWidget(editor)
window.show()
raise SystemExit(app.exec())
