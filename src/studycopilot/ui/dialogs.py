from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QPlainTextEdit,
)


class SourceDialog(QDialog):
    def __init__(self, parent=None, suggested: str = ""):
        super().__init__(parent)
        self.setWindowTitle("添加学习资料")
        self.setMinimumWidth(340)
        layout = QFormLayout(self)
        self.title = QLineEdit(suggested)
        self.title.setMaxLength(200)
        self.kind = QComboBox()
        for label, value in [("书籍", "book"), ("PDF", "pdf"), ("论文", "paper"),
                             ("课程讲义", "lecture"), ("网页", "web"), ("手册", "manual"),
                             ("技术文档", "documentation"), ("个人笔记", "notes")]:
            self.kind.addItem(label, value)
        if suggested.lower().endswith(".pdf"):
            self.kind.setCurrentIndex(1)
        layout.addRow("资料名称", self.title)
        layout.addRow("类型", self.kind)
        hint = QLabel("只登记资料名称，不读取或上传文件。")
        hint.setWordWrap(True)
        layout.addRow(hint)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)


class MemoryDialog(QDialog):
    def __init__(self, concepts: list[dict], parent=None, screenshot=False):
        super().__init__(parent)
        self.setWindowTitle("保存学习记忆")
        self.setMinimumWidth(360)
        layout = QFormLayout(self)
        hint = QLabel("保存你明确想保留的疑问或笔记，可先编辑。\n例如：我仍容易混淆 gm 与电压增益。")
        hint.setWordWrap(True)
        layout.addRow(hint)
        self.project_label = QLabel()
        layout.addRow("所属项目", self.project_label)
        self.timestamps = QLabel()
        self.timestamps.setWordWrap(True)
        layout.addRow(self.timestamps)
        self.content = QPlainTextEdit()
        self.content.setPlaceholderText("1–2000 字；不会自动保存整个对话")
        self.content.setMinimumHeight(140)
        self.scope = QComboBox()
        for label, value in [("当前项目 · project", "project"), ("跨项目知识 · global", "global"),
                             ("个人学习偏好 · user", "user")]:
            self.scope.addItem(label, value)
        self.concept = QComboBox()
        self.concept.addItem("不关联 Concept", None)
        for item in concepts:
            self.concept.addItem(item["chinese_name"] or item["canonical_name"], item["id"])
        layout.addRow("内容", self.content)
        layout.addRow("范围", self.scope)
        layout.addRow("关联概念", self.concept)
        self.concept_name = QLineEdit()
        self.concept_name.setMaxLength(200)
        self.concept_name.setPlaceholderText("可选；填写时替换上方关联概念")
        self.aliases = QLineEdit()
        self.aliases.setMaxLength(600)
        self.aliases.setPlaceholderText("可选；逗号分隔，添加到关联概念")
        self.status = QComboBox()
        self.status.addItem("待解决", "pending")
        self.status.addItem("已解决", "resolved")
        self.source_location = QLineEdit()
        self.source_location.setMaxLength(200)
        self.source_location.setPlaceholderText("可选；只填写已知页码或章节")
        layout.addRow("概念名称", self.concept_name)
        layout.addRow("新增别名", self.aliases)
        layout.addRow("状态", self.status)
        layout.addRow("页码／章节", self.source_location)
        self.attach_screenshot = QCheckBox("同时保留当前截图并关联此记忆")
        self.attach_screenshot.setChecked(screenshot)
        self.attach_screenshot.setVisible(screenshot)
        layout.addRow(self.attach_screenshot)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
