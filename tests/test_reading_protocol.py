import json
import time
import pytest
from studycopilot.providers.codex import CodexProvider
from studycopilot.providers.reading import ReadingRequest
from studycopilot.ui.math_text import plain_math
from studycopilot.providers import codex_config

class Pipe:
    def __init__(self):
        self.data=b""
    def readAllStandardOutput(self):
        data,self.data=self.data,b""
        return data

def test_fragmented_utf8_protocol_and_stale_rpc(qapp,tmp_path,monkeypatch):
    p=CodexProvider(tmp_path)
    pipe=Pipe()
    p.process=pipe
    p.current=ReadingRequest("new","prompt",None,"translate")
    p.thread_id="thread"
    p.turn_id="turn"
    shown=[]
    p.text_changed.connect(lambda _,text:shown.append(text))
    message={"method":"item/agentMessage/delta","params":{"threadId":"thread","turnId":"turn","itemId":"a","delta":"跨导"}}
    raw=(json.dumps(message,ensure_ascii=False)+"\n").encode()
    i=raw.index("跨".encode())+1
    pipe.data=raw[:i]
    p._read(pipe)
    assert not shown
    pipe.data=raw[i:]
    p._read(pipe)
    assert shown==["跨导"]
    called=[]
    p.callbacks[4]=(called.append,time.monotonic()+40,"old")
    p.handle_message({"id":4,"result":{"private":"old"}})
    assert not called
    p.process=None
    p.close()

@pytest.mark.parametrize("raw",[b"{bad}\n",b'[]\n',b'{"method":"item/started","params":"wrong"}\n'])
def test_malformed_protocol_fails_safely(qapp,tmp_path,monkeypatch,raw):
    p=CodexProvider(tmp_path)
    pipe=Pipe()
    p.process=pipe
    p.current=ReadingRequest("a","prompt",None,"translate")
    failures=[]
    p.failed.connect(lambda *args:failures.append(args))
    monkeypatch.setattr(p,"_stop_process",lambda:setattr(p,"process",None))
    pipe.data=raw
    p._read(pipe)
    assert failures and failures[0][1]=="protocol"
    p.close()

def test_readonly_isolation_failure_never_sends_image(qapp,tmp_path,monkeypatch):
    p=CodexProvider(tmp_path)
    p.current=ReadingRequest("a","prompt",tmp_path/"private.png","translate")
    calls=[]
    monkeypatch.setattr(p,"_rpc",lambda *args:calls.append(args))
    p._thread_started({"thread":{"id":"t","ephemeral":False},"sandbox":{"type":"readOnly"}})
    assert not calls and p.state=="isolation"
    p.close()

def test_unavailable_model_is_not_silently_substituted(qapp,tmp_path,monkeypatch):
    p=CodexProvider(tmp_path)
    p.models=[{"model":"available","isDefault":True}]
    p.current=ReadingRequest("a","prompt",None,"translate","unavailable")
    calls=[]
    monkeypatch.setattr(p,"_rpc",lambda *args:calls.append(args))
    p._begin_request()
    assert not calls and p.state=="model_unavailable"
    p.close()

def test_desktop_install_discovery_without_path(tmp_path,monkeypatch):
    if codex_config.os.name!="nt":
        pytest.skip("Windows installation discovery")
    executable=tmp_path/"OpenAI/Codex/bin/version/codex.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"test placeholder")
    monkeypatch.setenv("LOCALAPPDATA",str(tmp_path))
    monkeypatch.setattr(codex_config.shutil,"which",lambda _:None)
    assert codex_config.executable()==str(executable)

def test_common_display_fraction_and_unsupported_deep_math():
    assert plain_math(r"\dfrac{A}{1+A\beta}")=="(A)/(1+Aβ)"
    nested="x"
    for _ in range(18):
        nested=r"\frac{"+nested+"}{1}"
    started=time.monotonic()
    assert plain_math(nested)
    assert time.monotonic()-started<1
