"""Opt-in real subscription verification using generated study material only."""
import argparse
import json
from pathlib import Path
import sys
import time
from uuid import uuid4
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QFont
from PySide6.QtWidgets import QApplication
from studycopilot.memory.database import Database
from studycopilot.ui.sidebar import Sidebar
from studycopilot.ui.controller import SidebarController
from studycopilot.capture.active_window import ActiveWindow

sys.stdout.reconfigure(encoding="utf-8")
parser = argparse.ArgumentParser()
parser.add_argument("--followup", action="store_true")
parser.add_argument("--count", type=int, default=1, choices=range(1, 11))
parser.add_argument("--model", default="gpt-5.6-luna")
args = parser.parse_args()
out = Path(__file__).resolve().parents[1] / "test-results" / ("v03-live-" + str(uuid4())[:8])
out.mkdir(parents=True)
app = QApplication([])
app.setQuitOnLastWindowClosed(False)
db = Database(out / "study.db")
view = Sidebar()
controller = SidebarController(view, db)
reading = controller.reading
reading.model = args.model
reading.enabled = True
view.auto_translate.blockSignals(True)
view.auto_translate.setChecked(True)
view.auto_translate.blockSignals(False)
reading.update_privacy()
view.resize(430, 820)
view.show()
cases = [
    ("Source degeneration introduces negative feedback.\nTransconductance is denoted by gm.\nAv = -gm RD / (1 + gm RS)", "translate"),
    ("1  Introduction to Analog Design\n1.1  Why Analog?\n1.2  Why Integrated Circuits?\n1.3  Why CMOS?", "translate"),
    ("The small-signal model is valid near the bias point.\nThe gate current of an ideal MOSFET is zero.", "translate"),
    ("Channel-length modulation gives a finite output resistance.\nro = 1 / (lambda ID)", "translate"),
    ("The common-source amplifier inverts the signal.\nA larger drain resistance increases the gain magnitude.", "translate"),
    ("At room temperature, the thermal voltage is about 26 mV.\nFor a bipolar transistor, gm = IC / VT.", "translate"),
    ("Negative feedback trades gain for improved linearity.\nThe closed-loop gain is A / (1 + A beta).", "translate"),
    ("Parameter        Symbol        Unit\nVoltage gain     Av            V/V\nTransconductance gm            A/V\nOutput resistance ro           ohm", "translate"),
    ("Circuit:\nVDD --- RD --- drain of NMOS\nvin --- gate\nsource --- RS --- ground\nvout is measured at the drain.", "explain"),
    ("Do not assume missing context.\nThe symbols beta and gm depend on the device model.", "translate"),
][:args.count]
if args.followup:
    cases=[cases[0], ('为什么源极电阻会降低电压增益？', 'explain')]
results=[]
started=0
index=0
exit_code=0
first_render=False
case_timer=QTimer()
case_timer.setSingleShot(True)

def grab(name):
    view.grab().save(str(out / name))

def next_case():
    global started, first_render
    if index == len(cases):
        finish()
        return
    first_render=False
    text, task=cases[index]
    if args.followup and index == 1:
        started=time.monotonic()
        view.followup.setText(text)
        view.send_question.click()
        assert reading.current_id, "follow-up did not start"
        case_timer.start(120000)
        return
    image=QImage(1100, 320, QImage.Format.Format_RGB32)
    image.fill(QColor("white"))
    painter=QPainter(image)
    painter.setPen(QColor("#202124"))
    painter.setFont(QFont("Segoe UI", 20))
    painter.drawText(image.rect().adjusted(26,18,-20,-18), Qt.AlignmentFlag.AlignLeft, text)
    painter.end()
    image.save(str(out / f"source-{index+1:02}.png"))
    started=time.monotonic()
    controller.accept_screenshot(image, (0,0,1100,320),task,ActiveWindow())
    if not reading.current_id:
        fail("", "not_started", view.result_status.text())
        return
    print(json.dumps({"case":index+1,"waiting_state_seconds":round(time.monotonic()-started,3)},ensure_ascii=False),flush=True)
    if index == 0:
        QTimer.singleShot(100, lambda: grab("waiting.png"))
    case_timer.start(120000)

def delta(*_):
    global first_render
    if not first_render:
        first_render=True
        print(json.dumps({"case":index+1,"first_text_seconds":round(time.monotonic()-started,3)},ensure_ascii=False),flush=True)

def complete(request_id, answer, model):
    global index
    case_timer.stop()
    results.append({"case":index+1,"task":cases[index][1],"answer":answer,"model":model,
                    "first_text_seconds":reading.provider.first_text_seconds,
                    "total_seconds":round(time.monotonic()-started,3),
                    "saved":db.one("SELECT count(*) AS n FROM reading_results")["n"],
                    "visible_answer":view.result.toPlainText()})
    print(json.dumps({k:v for k,v in results[-1].items() if k not in ("answer","visible_answer")}),flush=True)
    grab(f"completed-{index+1:02}.png")
    index+=1
    QTimer.singleShot(750,next_case)

def fail(request_id, code, message):
    global exit_code
    exit_code=1
    results.append({"case":index+1,"error":code,"message":message})
    print(json.dumps(results[-1],ensure_ascii=False),flush=True)
    grab("failed.png")
    finish()

def finish():
    case_timer.stop()
    (out/"results.json").write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf-8")
    print("Evidence: "+str(out),flush=True)
    view.close()
    db.close()
    app.quit()

reading.provider.text_changed.connect(delta)
reading.provider.completed.connect(complete)
reading.provider.failed.connect(fail)
case_timer.timeout.connect(lambda: fail("", "timeout", "verification deadline"))
QTimer.singleShot(100,next_case)
app.exec()
raise SystemExit(exit_code)
