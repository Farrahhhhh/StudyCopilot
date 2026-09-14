from dataclasses import replace
import pytest
from PySide6.QtCore import QMimeData
from studycopilot.capture.active_window import ActiveWindow
from studycopilot.capture.clipboard import SelectionCapture, clone_mime


class FakeClipboard:
    def __init__(self):
        self.mime = QMimeData()
        self.mime.setText("original")
        self.mime.setHtml("<b>original</b>")

    def mimeData(self):
        return self.mime

    def setMimeData(self, mime):
        self.mime = mime

    def text(self):
        return self.mime.text()

    def set_text(self, text):
        self.mime = QMimeData()
        self.mime.setText(text)


class FakeAPI:
    def __init__(self):
        self.seq = 10
        self.handle = 123
        self.held = False
        self.copies = 0

    def sequence(self):
        return self.seq

    def foreground_handle(self):
        return self.handle

    def modifiers_down(self):
        return self.held

    def copy_selection(self):
        self.copies += 1


@pytest.fixture
def capture(qapp):
    clipboard = FakeClipboard()
    api = FakeAPI()
    clock = [0.0]
    window = ActiveWindow(handle=123, process_id=-1, process_name="reader.exe", window_title=None)
    instance = SelectionCapture(clipboard, api, clock=lambda: clock[0],
                                window_reader=lambda _: window)
    results, errors = [], []
    instance.captured.connect(lambda text, active: results.append((text, active)))
    instance.failed.connect(errors.append)
    yield instance, clipboard, api, clock, results, errors
    instance.cancel()


def test_delayed_copy_restores_text_html_and_missing_window_title(capture):
    instance, clipboard, api, clock, results, errors = capture
    instance.start()
    instance._tick()
    assert api.copies == 1
    clock[0] = 1.1
    instance._tick()
    assert api.copies == 1  # polling must not queue a second delayed Ctrl+C
    clipboard.set_text("The source resistance introduces negative feedback.")
    api.seq += 1
    instance._tick()
    assert not errors and not instance.busy
    assert results[0][0].endswith("negative feedback.")
    assert results[0][1].window_title is None
    assert clipboard.text() == "original"
    assert clipboard.mimeData().html() == "<b>original</b>"


def test_same_text_copy_detected_by_sequence(capture):
    instance, clipboard, api, clock, results, errors = capture
    instance.start()
    instance._tick()
    clipboard.set_text("original")
    api.seq += 1
    instance._tick()
    assert results[0][0] == "original"


def test_empty_copy_handled_without_using_old_clipboard(capture):
    instance, clipboard, api, clock, results, errors = capture
    instance.start()
    instance._tick()
    clipboard.set_text("")
    api.seq += 1
    instance._tick()
    assert not results and errors
    assert clipboard.text() == "original"


def test_no_selection_times_out_without_old_text(capture):
    instance, clipboard, api, clock, results, errors = capture
    instance.start()
    instance._tick()
    clock[0] = 2.3
    instance._tick()
    assert not results and errors and not instance.busy
    assert clipboard.text() == "original"


def test_modifiers_wait_is_nonblocking_and_debounced(capture):
    instance, clipboard, api, clock, results, errors = capture
    api.held = True
    instance.start()
    instance.start()
    instance._tick()
    assert api.copies == 0 and instance.busy
    api.held = False
    instance._tick()
    assert api.copies == 1
    clipboard.set_text("selected")
    api.seq += 1
    instance._tick()
    instance.start()
    assert not instance.busy  # immediate repeat ignored
    clock[0] = 0.6
    instance.start()
    assert instance.busy


def test_held_keys_and_changed_window_cancel(capture):
    instance, clipboard, api, clock, results, errors = capture
    api.held = True
    instance.start()
    clock[0] = 1.3
    instance._tick()
    assert not instance.busy and errors and api.copies == 0
    clock[0] = 2
    api.held = False
    instance.start()
    api.handle = 999
    instance._tick()
    assert not instance.busy and len(errors) == 2


def test_preserves_new_user_clipboard_while_waiting(capture):
    instance, clipboard, api, clock, results, errors = capture
    instance.start()
    clipboard.set_text("new user content")
    api.seq += 1
    instance._tick()
    assert clipboard.text() == "new user content"
    assert api.copies == 0 and not results and errors


def test_snapshot_size_guard_and_empty(qapp):
    assert clone_mime(None).formats() == []
    mime = QMimeData()
    mime.setText("x" * 100)
    with pytest.raises(ValueError):
        clone_mime(mime, max_bytes=10)


def test_restore_skips_changed_clipboard(capture):
    instance, clipboard, api, clock, results, errors = capture
    instance.start()
    clipboard.set_text("newer content")
    api.seq = 99
    instance._restore(98)
    assert clipboard.text() == "newer content"


def test_capture_logs_do_not_contain_selection(capture, caplog):
    instance, clipboard, api, clock, results, errors = capture
    caplog.set_level("INFO")
    instance.start()
    instance._tick()
    clipboard.set_text("PRIVATE_TEXT_UNIQUE_SENTINEL")
    api.seq += 1
    instance._tick()
    assert "capture success" in caplog.text
    assert "PRIVATE_TEXT_UNIQUE_SENTINEL" not in caplog.text
