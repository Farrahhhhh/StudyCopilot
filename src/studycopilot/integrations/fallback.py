from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Callable

from studycopilot.context.package import ContextPackage


@dataclass(frozen=True)
class PreparedHandoff:
    package: ContextPackage
    prompt: str
    image_path: Path | None


class ClipboardIntegration:
    def format(self, package: ContextPackage) -> str:
        templates = {"translate": "translation.md", "explain": "explain.md"}
        if package.task_type not in templates:
            raise ValueError("不支持的任务类型。")
        prompt = files("studycopilot").joinpath("prompts/" + templates[package.task_type]).read_text(encoding="utf-8").strip()
        return f"{prompt}\n\nContext Package（JSON 数据）：\n{package.to_json()}"

    def copy(self, package: ContextPackage, write_text: Callable[[str], None]) -> str:
        prompt = self.format(package)
        write_text(prompt)
        return prompt

    def prepare(self, package: ContextPackage, image_path: Path | None = None) -> PreparedHandoff:
        if package.current_screenshot and (image_path is None or not image_path.is_file()):
            raise ValueError("当前截图文件缺失，请重新截图。")
        return PreparedHandoff(package, self.format(package), image_path)

    def copy_image(self, prepared: PreparedHandoff, clipboard) -> None:
        from PySide6.QtCore import QByteArray, QMimeData
        from PySide6.QtGui import QImage
        if prepared.image_path is None:
            raise ValueError("当前没有截图。")
        image = QImage(str(prepared.image_path))
        if image.isNull():
            raise ValueError("截图读取失败，请重新截图。")
        mime = QMimeData()
        # Image-only clipboard. The receiver chooses formats; never pretend it also pasted text.
        mime.setImageData(image)
        mime.setData("image/png", QByteArray(prepared.image_path.read_bytes()))
        clipboard.setMimeData(mime)
