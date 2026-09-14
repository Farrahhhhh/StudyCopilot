from dataclasses import replace
import json
import sqlite3
from uuid import uuid4
import pytest
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QImage, QColor
from PySide6.QtTest import QTest
from studycopilot.providers.reading import ReadingProvider, ReadingRequest
from studycopilot.providers.codex import CodexProvider, error_message
from studycopilot.providers.codex_config import child_environment, launch_arguments, thread_parameters
from studycopilot.capture.active_window import ActiveWindow
from studycopilot.memory.database import Database
from studycopilot.memory.migrations import MIGRATIONS, SCHEMA_VERSION
from studycopilot.projects.manager import ProjectManager
from studycopilot.ui.sidebar import Sidebar
from studycopilot.ui.controller import SidebarController
from studycopilot.ui.math_text import plain_math, readable_markdown

class FakeProvider(ReadingProvider):
    def __init__(self):
        super().__init__()
        self.requests=[]
        self.current=None
        self.cancelled=0
        self.connections=0
    def connect_service(self):
        self.connections+=1
    def login(self):
        self.connect_service()
    def submit(self, request):
        self.current=request
        self.requests.append(request)
    def cancel(self):
        self.cancelled+=1
        self.current=None
    def close(self):
        self.current=None
    def finish(self, text="源极退化引入负反馈。"):
        request=self.current
        self.current=None
        self.completed.emit(request.id,text,"test-visual")

@pytest.fixture
def reading(qapp,db):
    provider=FakeProvider()
    view=Sidebar()
    c=SidebarController(view,db,provider)
    view.show()
    yield view,c,provider
    view.close()

def capture(c,task="translate"):
    image=QImage(320,160,QImage.Format.Format_RGB32)
    image.fill(QColor("white"))
    c.accept_screenshot(image,(1,2,320,160),task,ActiveWindow())
    return c.visual.current.id

def test_auto_one_request_without_clipboard_and_stream_persist(reading,qapp,db):
    v,c,p=reading
    qapp.clipboard().setText("unchanged")
    v.auto_translate.setChecked(True)
    shot=capture(c)
    c.reading.auto_submit()
    assert len(p.requests)==1
    assert p.requests[0].image_path.is_file()
    assert not v.translate_now.isEnabled()
    assert qapp.clipboard().text()=="unchanged"
    request=p.current.id
    p.text_changed.emit(request,"源极退化")
    c.reading._render()
    assert "源极退化" in v.result.toPlainText()
    assert not db.all("SELECT * FROM reading_results")
    p.finish()
    assert db.one("SELECT screenshot_id FROM reading_results")["screenshot_id"]==shot
    assert v.copy_translation.isEnabled()
    assert not db.all("SELECT * FROM memories")
    assert qapp.clipboard().text()=="unchanged"

def test_manual_mode_and_turn_on_does_not_send_existing_capture(reading):
    v,c,p=reading
    capture(c)
    assert not p.requests
    v.auto_translate.setChecked(True)
    assert not p.requests
    v.translate_now.click()
    assert len(p.requests)==1

def test_new_capture_cancels_and_ignores_old_result(reading,db):
    v,c,p=reading
    v.auto_translate.setChecked(True)
    capture(c)
    old=p.current.id
    second=capture(c)
    assert p.cancelled==1
    p.completed.emit(old,"OLD SECRET","test")
    p.text_changed.emit(old,"OLD SECRET")
    assert "SECRET" not in v.result.toPlainText()
    assert not db.all("SELECT * FROM reading_results")
    p.finish("NEW")
    assert db.one("SELECT screenshot_id FROM reading_results")["screenshot_id"]==second

@pytest.mark.parametrize("action",["project","source","clear"])
def test_scope_changes_cancel_and_discard_output(reading,db,action):
    v,c,p=reading
    v.auto_translate.setChecked(True)
    capture(c)
    old=p.current.id
    if action=="project":
        other=ProjectManager(db).create_project("unrelated")
        c.refresh_projects(other["id"])
    elif action=="source":
        source=ProjectManager(db).create_source(v.projects.currentData(),"new","book")
        c.refresh_sources(source["id"])
        c.source_changed()
    else:
        v.clear_image.click()
    p.completed.emit(old,"STALE","test")
    assert "STALE" not in v.result.toPlainText()
    assert p.current is None
    assert not db.all("SELECT * FROM reading_results")

def test_followup_enter_bounded_history_and_new_draft_preserved(reading):
    v,c,p=reading
    v.auto_translate.setChecked(True)
    capture(c)
    original=p.current.image_path
    p.finish("跨导决定电压增益。")
    v.followup.setText("为什么？")
    QTest.keyClick(v.followup,Qt.Key.Key_Return)
    assert len(p.requests)==2
    assert p.current.task_type=="explain" and p.current.image_path==original
    assert "跨导决定" in p.current.prompt and "为什么" in p.current.prompt
    v.followup.setText("下一个问题")
    p.finish("因为跨导将栅源电压转换为漏极电流。")
    assert v.followup.text()=="下一个问题"
    assert len(c.reading.history)==2
    QTest.keyClick(v.followup,Qt.Key.Key_Return,Qt.KeyboardModifier.ShiftModifier)
    assert len(p.requests)==2 and "\n" in v.followup.text()

@pytest.mark.parametrize("mode",["stop","error","disable"])
def test_partial_never_saved_or_claimed_completed(reading,db,mode):
    v,c,p=reading
    v.auto_translate.setChecked(True)
    capture(c)
    old=p.current.id
    p.text_changed.emit(old,"部分回答")
    if mode=="stop":
        v.stop_translation.click()
    elif mode=="disable":
        v.auto_translate.setChecked(False)
    else:
        p.current=None
        p.failed.emit(old,"rate_limited","订阅额度用尽")
    p.completed.emit(old,"LATE","test")
    assert not db.all("SELECT * FROM reading_results")
    assert not v.copy_translation.isEnabled()
    assert v.retry_translation.isVisible()
    v.retry_translation.click()
    assert len(p.requests)==2

def test_recent_restore_is_local_and_scoped(reading):
    v,c,p=reading
    v.auto_translate.setChecked(True)
    first=capture(c)
    p.finish("第一张译文")
    capture(c)
    p.finish("第二张译文")
    i=v.recent_images.findData(first)
    c.visual.choose_recent(i)
    assert v.result.toPlainText()=="第一张译文"
    assert len(p.requests)==2

def test_results_bounded_and_deleted_with_temporary_image(reading,db):
    v,c,p=reading
    capture(c)
    package=c.package
    for i in range(65):
        c.reading.store.save(str(uuid4()),package,str(i),"test")
    assert db.one("SELECT count(*) AS n FROM reading_results")["n"]==60
    db.execute("DELETE FROM screenshots WHERE id=?",(c.visual.current.id,))
    assert not db.all("SELECT * FROM reading_results")

def test_rebound_image_rejects_old_record(reading,db):
    v,c,p=reading
    capture(c)
    package=c.package
    source=ProjectManager(db).create_source(v.projects.currentData(),"new","book")
    c.refresh_sources(source["id"])
    c.source_changed()
    with pytest.raises(ValueError):
        c.reading.store.save("old",package,"OLD","test")

def test_v2_migration_preserves_rows_and_backup(tmp_path):
    path=tmp_path/"study.db"
    conn=sqlite3.connect(path)
    conn.executescript(MIGRATIONS[1]+MIGRATIONS[2]+"PRAGMA user_version=2;")
    conn.execute("INSERT INTO projects VALUES (?,?,?,?,?)",("old","Existing","","before","before"))
    conn.commit()
    conn.close()
    db=Database(path)
    assert db.one("SELECT name FROM projects")["name"]=="Existing"
    assert db.connection.execute("PRAGMA user_version").fetchone()[0]==SCHEMA_VERSION
    assert not db.connection.execute("PRAGMA foreign_key_check").fetchall()
    db.close()
    backup=sqlite3.connect(next((tmp_path/"backups").glob("study-v2-*.db")))
    assert backup.execute("PRAGMA user_version").fetchone()[0]==2
    assert backup.execute("SELECT name FROM projects").fetchone()[0]=="Existing"
    backup.close()

def test_v3_failure_transactional(tmp_path,monkeypatch):
    path=tmp_path/"study.db"
    conn=sqlite3.connect(path)
    conn.executescript(MIGRATIONS[1]+MIGRATIONS[2]+"PRAGMA user_version=2;")
    conn.close()
    monkeypatch.setitem(MIGRATIONS,3,"CREATE TABLE partial(id); INVALID;")
    with pytest.raises(sqlite3.Error):
        Database(path)
    conn=sqlite3.connect(path)
    assert conn.execute("PRAGMA user_version").fetchone()[0]==2
    assert not conn.execute("SELECT name FROM sqlite_master WHERE name='partial'").fetchone()
    conn.close()

@pytest.fixture
def provider(qapp,tmp_path):
    p=CodexProvider(tmp_path)
    yield p
    p.close()

def active(p):
    p.current=ReadingRequest("request","test",None,"translate")
    p.thread_id="thread"
    p.turn_id="turn"
    p.actual_model="visual"

def event(p,method,**params):
    p.handle_message({"method":method,"params":{"threadId":"thread","turnId":"turn",**params}})

def test_protocol_correlates_stream_and_ignores_commentary(provider,monkeypatch):
    p=provider
    monkeypatch.setattr(p,"_rpc",lambda *a:None)
    active(p)
    shown=[]; done=[]
    p.text_changed.connect(lambda _,s:shown.append(s))
    p.completed.connect(lambda *a:done.append(a))
    event(p,"item/started",item={"id":"comment","type":"agentMessage","phase":"commentary"})
    event(p,"item/agentMessage/delta",itemId="comment",delta="Do not show")
    p.handle_message({"method":"item/agentMessage/delta","params":{"threadId":"other","itemId":"x","delta":"SECRET"}})
    event(p,"item/started",item={"id":"answer","type":"agentMessage","phase":"final_answer"})
    event(p,"item/agentMessage/delta",itemId="answer",delta="中文")
    event(p,"item/completed",item={"id":"answer","type":"agentMessage","phase":"final_answer","text":"中文译文"})
    event(p,"turn/completed",turn={"id":"turn","status":"completed"})
    assert shown==["中文","中文译文"]
    assert done==[("request","中文译文","visual")]
    event(p,"item/agentMessage/delta",itemId="answer",delta="LATE")
    assert shown[-1]=="中文译文"

@pytest.mark.parametrize("kind",["commandExecution","mcpToolCall","fileChange"])
def test_protocol_blocks_unexpected_tools(provider,kind):
    active(provider)
    failures=[]
    provider.failed.connect(lambda *a:failures.append(a))
    event(provider,"item/started",item={"type":kind,"id":"x"})
    assert failures[0][1]=="tool_blocked" and provider.current is None

def test_protocol_server_request_denied_and_quota_no_ready(provider,monkeypatch):
    writes=[]
    monkeypatch.setattr(provider,"_write",writes.append)
    active(provider)
    provider.handle_message({"id":4,"method":"item/commandExecution/requestApproval","params":{}})
    assert writes[0]["error"]["code"]==-32601
    provider.models=[{"model":"test"}]
    provider._limits({"rateLimits":{"primary":{"usedPercent":100}}})
    assert not provider.ready and provider.state=="rate_limited"

def test_starting_connection_not_initialized_twice(provider,monkeypatch):
    calls=[]
    monkeypatch.setattr(provider,"_rpc",lambda *a:calls.append(a))
    provider.state="connecting"
    provider.connect_service()
    assert not calls

def test_timeout_and_empty_output_cannot_complete(provider):
    active(provider)
    done=[];failures=[]
    provider.completed.connect(lambda *a:done.append(a))
    provider.failed.connect(lambda *a:failures.append(a))
    event(provider,"turn/completed",turn={"id":"turn","status":"completed"})
    assert not done and failures[0][1]=="empty_answer"
    active(provider)
    provider.deadline.timeout.emit()
    assert failures[-1][1]=="timeout"

def test_configuration_uses_subscription_without_inherited_tools(tmp_path,monkeypatch):
    home=tmp_path/"official"
    home.mkdir()
    (home/"config.toml").write_text('[mcp_servers.private_server]\ncommand="secret"\n',encoding="utf-8")
    monkeypatch.setenv("CODEX_HOME",str(home))
    monkeypatch.setenv("OPENAI_API_KEY","secret")
    monkeypatch.setenv("CODEX_APP_TOOLS_PIPE_PATH","secretpipe")
    args=launch_arguments(tmp_path/"runtime")
    assert "mcp_servers.private_server.enabled=false" in args
    assert 'forced_login_method="chatgpt"' in args
    assert "model_providers.studycopilot-subscription.supports_websockets=false" in args
    assert "secret" not in " ".join(args)
    env=child_environment()
    assert "OPENAI_API_KEY" not in env and "CODEX_APP_TOOLS_PIPE_PATH" not in env
    assert env["CODEX_HOME"]==str(home)
    params=thread_parameters(tmp_path,"visual","instructions")
    assert params["environments"]==[] and params["selectedCapabilityRoots"]==[]
    assert params["ephemeral"] and params["sandbox"]=="read-only"

@pytest.mark.parametrize("error,code",[
    ({"codexErrorInfo":"usageLimitExceeded"},"rate_limited"),
    ({"message":"Unauthorized token SECRET"},"needs_login"),
    ({"message":"model not supported SECRET"},"model_unavailable"),
    ({"message":"timeout SECRET"},"timeout"),
    ({"message":"unknown SECRET"},"service_error"),
])
def test_errors_are_actionable_without_raw_payload(error,code):
    actual,message=error_message(error)
    assert actual==code and "SECRET" not in message

def test_math_and_untrusted_rendering(reading):
    v,_,_=reading
    assert plain_math(r"A_v=\frac{-g_m R_D}{1+g_m R_S}")=="A_v=(-g_m R_D)/(1+g_m R_S)"
    assert plain_math(r"\beta^2 + \mu")== "β² + μ"
    assert plain_math(r"\unknown{x}")==r"\unknown{x}"
    v.result.show_answer(r"跨导 \(g_m\)"+"\n\n"+r"\[A_v=\frac{-g_m R_D}{1+g_m R_S}\]")
    assert "A_v=(-g_m R_D)/(1+g_m R_S)" in v.result.toPlainText()
    assert v.result.loadResource(2,QUrl("https://example.com/private.png")) is None
    assert not v.result.openExternalLinks()


def test_explanation_retry_keeps_task(reading):
    v,c,p=reading
    capture(c)
    v.explain_current.click()
    old=p.current.id
    p.current=None
    p.failed.emit(old,"timeout","超时")
    v.retry_translation.click()
    assert p.current.task_type=="explain"