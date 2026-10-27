"""服务层：FastAPI 入口。

接口：
  GET  /           前端页面
  POST /chat       流式(SSE)，边想边吐
  POST /plan       返回结构化 JSON
  POST /reset      清空对话历史
  GET  /photo      按关键词+城市取一张真实照片 URL(给前端用)

说明：agent 是全局单例，历史共享，适合单人演示。
生产环境应按 session_id 维护独立 agent 并加锁。
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import storage
from agent import Agent
from config import AMAP_JS_KEY
from tools import get_poi_photos

app = FastAPI(title="Trip Planner Agent", description="基于高德地图 + Function Calling 的旅行规划助手")

# 托管 static 目录里的静态资源(图片等)
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")

agent = Agent()   # 一个全局 agent 实例，所有请求共用(对话历史也因此共享)


class ChatRequest(BaseModel):
    """请求体模型。pydantic 会自动校验/解析请求里的 JSON。"""
    question: str


class SaveRequest(BaseModel):
    question: str
    plan: dict


class TripUpdate(BaseModel):
    review: str = ""
    photos: list = []


@app.get("/")
def index():
    """返回前端页面。加 no-cache 头，避免浏览器缓存旧页面。"""
    return FileResponse(
        Path(__file__).parent / "static" / "index.html",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


@app.get("/photo")
def photo(keyword: str, city: str, w: int = 600):
    """前端懒加载图片用：传景点/餐厅/酒店名 + 城市，返回多张真实照片 URL 列表。"""
    urls = get_poi_photos(keyword, city, w)
    return {"urls": urls}


@app.get("/config")
def get_config():
    """给前端返回高德 JS key(用于地图显示)。没配置返回空串，前端跳过地图。"""
    return {"amap_js_key": AMAP_JS_KEY}


@app.post("/chat")
async def chat(req: ChatRequest):
    # 流式接口：返回一个 SSE(Server-Sent Events)流，边生成边发送
    async def event_stream():
        async for chunk in agent.run_stream(req.question):
            for line in chunk.split("\n"):
                yield f"data: {line}\n"
            yield "\n"
    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/plan")
def plan(req: ChatRequest):
    """非流式：直接返回结构化 JSON 行程(dict)。"""
    return agent.plan(req.question)


@app.post("/reset")
def reset():
    agent.reset()
    return {"msg": "对话已清空"}


# ===== 旅行记录(保存/查看/编辑/回顾) =====

@app.get("/trips")
def trips():
    """列出所有保存的行程记录。"""
    return {"trips": storage.list_trips()}


@app.post("/trips")
def save_trip(req: SaveRequest):
    """保存一份行程计划。"""
    return storage.add_trip(req.question, req.plan)


@app.get("/trips/{tid}")
def get_trip(tid: str):
    """查看某条行程(含回顾文字和照片)。"""
    t = storage.get_trip(tid)
    return t or {"error": "记录不存在"}


@app.put("/trips/{tid}")
def edit_trip(tid: str, req: TripUpdate):
    """更新某条行程的回顾文字/照片。"""
    t = storage.update_trip(tid, review=req.review or None, photos=req.photos or None)
    return t or {"error": "记录不存在"}


@app.delete("/trips/{tid}")
def remove_trip(tid: str):
    storage.delete_trip(tid)
    return {"msg": "已删除"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
