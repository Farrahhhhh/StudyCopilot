import time
from studycopilot.providers.codex import CodexProvider
from studycopilot.providers.reading import ReadingRequest
from studycopilot.context.package import ContextPackage
from studycopilot.integrations.reading import format_reading
from test_reading import reading, capture

def test_compact_prompt_excludes_local_metadata_and_keeps_context():
    package=ContextPackage("translate","caption",project={"id":"PRIVATE_ID","name":"模拟电路"},
        source={"id":"PRIVATE_SOURCE","title":"Microelectronics"},
        current_screenshot={"file_path":"PRIVATE_PATH"},window_title="PRIVATE_WINDOW",
        attachments=[{"path":"PRIVATE_ATTACHMENT"}],metadata={"local":"PRIVATE_METADATA"},
        relevant_memories=[{"id":"PRIVATE_MEMORY","content":"区分跨导与电压增益"}],
        related_concepts=[{"canonical_name":"transconductance","chinese_name":"跨导","id":"PRIVATE_CONCEPT"}],
        question="为什么",recent_context=["上一回答"],user_preferences={"language":"zh"})
    text=format_reading(package)
    assert "PRIVATE" not in text
    for value in ("caption","模拟电路","Microelectronics","区分跨导","transconductance","为什么","上一回答"):
        assert value in text

def test_empty_screenshot_prompt_is_small():
    text=format_reading(ContextPackage("translate","",project={"name":"未分类"}))
    assert len(text)<180
    assert "目录逐项翻译" in text

def test_cancel_keeps_connection_and_drops_old_rpc(qapp,tmp_path,monkeypatch):
    provider=CodexProvider(tmp_path)
    pipe=object()
    provider.process=pipe
    provider.ready=True
    provider.current=ReadingRequest("old","text",None,"translate")
    provider.thread_id="old-thread"
    provider.turn_id="old-turn"
    provider.callbacks[1]=(lambda _:None,time.monotonic()+40,"old")
    calls=[]
    monkeypatch.setattr(provider,"_rpc",lambda *args:calls.append(args))
    provider.cancel()
    assert provider.ready and provider.process is pipe
    assert not provider.callbacks
    assert [r[0] for r in calls]==["turn/interrupt","thread/unsubscribe"]
    assert provider.current is None
    provider.current=ReadingRequest("new","text",None,"translate")
    provider.thread_id="new-thread"
    shown=[]
    provider.text_changed.connect(lambda *args:shown.append(args))
    provider.handle_message({"method":"item/agentMessage/delta","params":{
        "threadId":"old-thread","turnId":"old-turn","itemId":"a","delta":"OLD"}})
    assert not shown
    provider.process=None
    provider.close()

def test_cancel_before_turn_id_uses_safe_restart(qapp,tmp_path,monkeypatch):
    provider=CodexProvider(tmp_path)
    provider.ready=True
    provider.current=ReadingRequest("old","text",None,"translate")
    called=[]
    monkeypatch.setattr(provider,"_stop_process",lambda:called.append(True))
    provider.cancel()
    assert called and not provider.ready
    provider.close()

def test_wait_state_tracks_ready_and_elapsed(reading):
    view,c,p=reading
    view.auto_translate.setChecked(True)
    capture(c)
    request=p.current.id
    c.reading.connection("connecting","正在连接")
    assert "正在连接" in view.result_status.text()
    c.reading.connection("ready","已连接")
    assert "正在连接" not in view.result_status.text()
    p.request_progress.emit(request,"waiting")
    c.reading.started_at=time.monotonic()-12
    c.reading.wait_status()
    assert "等待首段译文" in view.result_status.text()
    assert "12 秒" in view.result_status.text()
    p.text_changed.emit(request,"真实文字")
    c.reading.wait_status()
    assert not c.reading.wait_timer.isActive()
    assert "生成中" in view.result_status.text()
    p.finish()
    assert not c.reading.wait_timer.isActive()

def test_old_progress_does_not_replace_new_state(reading):
    view,c,p=reading
    view.auto_translate.setChecked(True)
    capture(c)
    old=p.current.id
    capture(c)
    p.request_progress.emit(p.current.id,"waiting")
    expected=view.result_status.text()
    p.request_progress.emit(old,"connecting")
    assert view.result_status.text()==expected
