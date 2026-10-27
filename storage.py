"""本地存储层：保存旅行记录(计划 + 回顾文字 + 照片)。

用本地 JSON 文件存，照片以 base64 存进记录里(个人项目够用)。
生产环境应换成 SQLite/数据库 + 对象存储(OSS/S3)存图片。
"""
import json
import time
import uuid
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
TRIPS_FILE = DATA_DIR / "trips.json"


def _load() -> list:
    """读全部记录，文件不存在或损坏时返回空列表。"""
    if TRIPS_FILE.exists():
        try:
            return json.loads(TRIPS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def _save(trips: list) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    TRIPS_FILE.write_text(json.dumps(trips, ensure_ascii=False, indent=1), encoding="utf-8")


def list_trips() -> list:
    """返回所有记录(新的在前)。为了省体积，列表里不带照片数据。"""
    return [{k: v for k, v in t.items() if k != "photos"} for t in _load()]


def get_trip(tid: str):
    for t in _load():
        if t["id"] == tid:
            return t
    return None


def add_trip(question: str, plan: dict) -> dict:
    trips = _load()
    trip = {
        "id": uuid.uuid4().hex[:12],
        "created_at": time.strftime("%Y-%m-%d %H:%M"),
        "city": (plan or {}).get("city", ""),
        "question": question,
        "plan": plan,
        "review": "",       # 旅行感受文字
        "photos": [],       # base64 图片列表
    }
    trips.insert(0, trip)   # 新的放最前面
    _save(trips)
    return trip


def update_trip(tid: str, review: str = None, photos: list = None) -> dict:
    trips = _load()
    for t in trips:
        if t["id"] == tid:
            if review is not None:
                t["review"] = review
            if photos is not None:
                t["photos"] = photos
            _save(trips)
            return t
    return None


def delete_trip(tid: str) -> bool:
    trips = _load()
    new = [t for t in trips if t["id"] != tid]
    if len(new) == len(trips):
        return False
    _save(new)
    return True
