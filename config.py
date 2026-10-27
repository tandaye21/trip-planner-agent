"""全局配置：LLM key、高德 key、模型名。

这个文件就干一件事：读密钥、创建全局共用的 LLM 客户端 client。
别的文件(agent.py / tools.py)都从这里 import client 来用。
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

# load_dotenv 会读取 .env 文件，把里面的 KEY=VALUE 写进系统环境变量，
# 之后 os.getenv("XXX") 就能拿到。密钥放在 .env 里，避免写死进代码。
# 用 Path(__file__).parent.parent 定位到 note-agent/.env（和之前项目共用一把 key）
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# 读两把"钥匙"
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")   # 通义千问的 key（调 LLM 用）
AMAP_API_KEY = os.getenv("AMAP_API_KEY")             # 高德地图的 key（调工具用）
AMAP_JS_KEY = os.getenv("AMAP_JS_KEY", "")           # 高德 Web端(JS API) key，前端地图用(可选，不填则前端不显示地图)

# 缺 key 直接报错，避免跑到一半才失败
if not DASHSCOPE_API_KEY:
    raise RuntimeError("缺少 DASHSCOPE_API_KEY：请确认 D:/note-agent/.env 里已填入")
if not AMAP_API_KEY:
    raise RuntimeError(
        "缺少 AMAP_API_KEY：请在 D:/note-agent/.env 里加一行\n"
        "    AMAP_API_KEY=你的高德key"
    )

# base_url 指向通义 DashScope 的 OpenAI 兼容地址。
# 关键理解：openai 这个库不是只能连 OpenAI —— 只要服务端实现了 OpenAI 兼容协议，
# 改 base_url 就能连任意服务。所以"以后换本地 vLLM/Ollama"只需改这里两行。
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
CHAT_MODEL = "qwen-plus"          # 用哪个模型

# 全局共用一个客户端：整个项目都靠这个 client 调 LLM
client = OpenAI(api_key=DASHSCOPE_API_KEY, base_url=BASE_URL)
