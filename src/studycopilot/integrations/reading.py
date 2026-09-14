"""Small, scoped model payload; local bookkeeping stays local."""
import json
from importlib.resources import files

def format_reading(package):
    instruction = files("studycopilot").joinpath(
        "prompts/reading_translation.md" if package.task_type == "translate" else "prompts/reading_explanation.md"
    ).read_text(encoding="utf-8").strip()
    data={}
    if package.selected_text:
        data["文字"]=package.selected_text
    if package.question:
        data["问题"]=package.question
    if package.project and package.project.get("name") != "未分类":
        data["学习项目"]=package.project.get("name")
    if package.source:
        data["资料"]=package.source.get("title")
    if package.topic:
        data["主题"]=package.topic.get("name")
    if package.recent_context:
        data["近期问答"]=package.recent_context
    if package.related_concepts:
        data["术语"]=[{k:c[k] for k in ("canonical_name","chinese_name") if c.get(k)}
                      for c in package.related_concepts]
    if package.relevant_memories:
        data["相关记忆"]=[{
            "content": m["content"], "concept": m.get("concept", ""),
            "status": m.get("status", "pending"),
            "source": {k: m.get("source", {}).get(k, "") for k in ("title", "location")}
        } for m in package.relevant_memories]
    if package.user_preferences:
        data["学习偏好"]=package.user_preferences
    return instruction + ("\n资料数据："+json.dumps(data,ensure_ascii=False,separators=(",",":")) if data else "")
