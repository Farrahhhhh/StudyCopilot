"""Opt-in A/B latency test. Only a generated contents-page image is sent."""
import json
from pathlib import Path
import sys
import time
from uuid import uuid4
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QImage,QColor,QPainter,QFont
from PySide6.QtWidgets import QApplication
from studycopilot.providers.codex import CodexProvider
from studycopilot.providers.reading import ReadingRequest
from studycopilot.integrations.fallback import ClipboardIntegration
from studycopilot.integrations.reading import format_reading
from studycopilot.context.package import ContextPackage
sys.stdout.reconfigure(encoding="utf-8")
app=QApplication([])
out=Path(__file__).resolve().parents[1]/"test-results"/("latency-"+str(uuid4())[:8])
out.mkdir(parents=True)
image=QImage(850,600,QImage.Format.Format_RGB32)
image.fill(QColor("white"))
painter=QPainter(image)
painter.setFont(QFont("Segoe UI",16))
painter.setPen(QColor("black"))
source="""17 CMOS Processing Technology
17.1 General Considerations
17.2 Wafer Processing
17.3 Photolithography
17.4 Oxidation
17.5 Ion Implantation
17.6 Deposition and Etching
17.7 Device Fabrication
  17.7.1 Active Devices
  17.7.2 Passive Devices
  17.7.3 Interconnects
17.8 Latch-Up"""
painter.drawText(image.rect().adjusted(20,20,-20,-20),Qt.AlignmentFlag.AlignLeft,source)
painter.end()
path=out/"synthetic-contents.png"
image.save(str(path))
package=ContextPackage("translate","",project={"id":"test-project","name":"未分类"},
 current_screenshot={"id":"test-shot","file_path":"screenshots/test.png","width":850,"height":600},
 session={"id":"test-session"},metadata={"capture_type":"screenshot"})
prompts={"before":ClipboardIntegration().format(package),"after":format_reading(package)}
provider=CodexProvider(out/"runtime")
steps=["before","after","before","after","replace"]
index=0; started=0; first=None; rows=[]; launch_once=False; old_pid=None
watch=QTimer()
watch.setSingleShot(True)

def start():
 global started,first
 started=time.monotonic();first=None
 kind=steps[index]
 print(json.dumps({"start":kind,"prompt_chars":len(prompts.get(kind,prompts["after"]))}),flush=True)
 provider.submit(ReadingRequest(str(uuid4()),prompts.get(kind,prompts["after"]),path,"translate","gpt-5.6-luna"))
 watch.start(100000)
 if kind=="replace":
  QTimer.singleShot(1500,replace)

def replace():
 global old_pid,started
 if not provider.current or not provider.turn_id:
  QTimer.singleShot(100,replace)
  return
 old_pid=provider.process.processId()
 provider.cancel()
 assert provider.ready
 assert provider.process.processId()==old_pid
 started=time.monotonic()
 provider.submit(ReadingRequest(str(uuid4()),prompts["after"],path,"translate","gpt-5.6-luna"))
 print("Replaced active image with the same connected process.",flush=True)

def ready(state,message):
 global launch_once
 if state=="ready" and not launch_once:
  launch_once=True
  QTimer.singleShot(0,start)

def delta(_id,text):
 global first
 if first is None:
  first=time.monotonic()-started
  print(json.dumps({"first_text":round(first,3)}),flush=True)

def done(_id,text,model):
 global index
 watch.stop()
 rows.append({"kind":steps[index],"first_seconds":first,"total_seconds":time.monotonic()-started,
              "answer":text,"model":model,"connection_reused":bool(old_pid) if steps[index]=="replace" else None})
 print(json.dumps({k:v for k,v in rows[-1].items() if k!="answer"}),flush=True)
 index+=1
 if index<len(steps):
  QTimer.singleShot(400,start)
 else:
  finish()

def fail(*args):
 rows.append({"error":args[-2:]})
 print("Benchmark request failed: "+str(args[-2:]),flush=True)
 finish()

def finish():
 (out/"results.json").write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding="utf-8")
 print("Evidence: "+str(out),flush=True)
 provider.close()
 app.quit()
provider.connection_changed.connect(ready)
provider.text_changed.connect(delta)
provider.completed.connect(done)
provider.failed.connect(fail)
watch.timeout.connect(lambda:fail("timeout","benchmark deadline"))
provider.connect_service()
QTimer.singleShot(45000,lambda:fail("startup","not ready") if not launch_once else None)
app.exec()
