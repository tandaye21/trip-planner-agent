"""工具层：高德地图真实 API 工具 + 给模型看的 schema。

【这个文件分"两半"，理解两半的关系就懂了 Function Calling】
  上半：真正的工具函数(search_poi / get_weather / plan_route)
        是"你写的、真正去调高德拿数据"的代码。
  下半：TOOLS，是"给模型看的说明书"，告诉模型有哪些工具、每个工具有什么参数。
  中间：AVAILABLE_FUNCTIONS，是"工具名 → 函数"的对照表，
        agent 靠它把模型说出的工具名翻译成真正要执行的函数。

核心思想（面试必考）：模型不会"执行"工具。它只照着 TOOLS 说明书，
输出"我想调 search_poi，参数 keywords=景点, city=北京"；真正去执行的是你写的函数。
"""
import requests

from config import AMAP_API_KEY

# 高德 Web 服务 API 的根地址
AMAP = "https://restapi.amap.com/v3"


def search_poi(keywords: str, city: str, limit: int = 5) -> dict:
    """关键词搜索：搜某城市的景点/酒店/美食，返回真实名称、地址、经纬度。"""
    # 发 HTTP GET 请求调高德"关键词搜索"接口。
    # params 会被拼成 URL 后面的查询串：?key=xxx&keywords=景点&city=北京&offset=5...
    r = requests.get(
        f"{AMAP}/place/text",
        params={"key": AMAP_API_KEY, "keywords": keywords, "city": city,
                "offset": limit, "citylimit": "true"},
        timeout=10,   # 10 秒超时，防止请求卡死
    )
    data = r.json()   # 把返回的 JSON 字符串解析成 dict
    if data.get("status") != "1":   # 高德的约定：status="1" 才代表成功
        return {"error": data.get("info", "POI 搜索失败")}

    # 从原始返回里挑出我们要的字段，做成干净的列表给模型（别把一大堆冗余字段丢给它）
    pois = []
    for p in data.get("pois", [])[:limit]:
        # 高德的 location 是 "116.397,39.909" 这种"经度,纬度"字符串，拆开
        lng, lat = (p.get("location") or ",").split(",")
        pois.append({
            "name": p.get("name"),
            "address": p.get("address"),
            "lng": lng,
            "lat": lat,
            "type": p.get("type"),
        })
    return {"pois": pois}


def _city_to_adcode(city: str):
    """城市名 → 行政区划编码(adcode)。

    为什么要这步？高德的天气接口只认 adcode(一串数字，如北京的 110000)，
    不认"北京"这种文字名。所以查天气前得先把城市名翻译成 adcode。
    """
    r = requests.get(
        f"{AMAP}/config/district",
        params={"key": AMAP_API_KEY, "keywords": city, "subdistrict": 0},
        timeout=10,
    )
    data = r.json()
    if data.get("status") == "1" and data.get("districts"):
        return data["districts"][0].get("adcode")
    return None


def get_weather(city: str) -> dict:
    """查某城市实时天气。内部是"两跳"：城市名 → adcode → 天气。"""
    # 第一跳：城市名 → adcode
    adcode = _city_to_adcode(city)
    if not adcode:
        return {"error": f"找不到城市「{city}」的行政区划编码"}

    # 第二跳：adcode → 天气
    r = requests.get(
        f"{AMAP}/weather/weatherInfo",
        params={"key": AMAP_API_KEY, "city": adcode, "extensions": "base"},
        timeout=10,
    )
    data = r.json()
    if data.get("status") == "1" and data.get("lives"):
        live = data["lives"][0]
        return {
            "city": live.get("city"),
            "weather": live.get("weather"),
            "temperature": live.get("temperature"),
            "wind": live.get("winddirection"),
            "humidity": live.get("humidity"),
        }
    return {"error": data.get("info", "天气查询失败")}


def plan_route(origin: str, destination: str, route_type: str = "walking") -> dict:
    """两点间路线规划，返回距离(米)和耗时(秒)。驾车时额外返回打车费(元)。"""
    # walking / driving 对应高德不同的接口路径
    path = {"walking": "walking", "driving": "driving"}.get(route_type, "walking")
    r = requests.get(
        f"{AMAP}/direction/{path}",
        params={"key": AMAP_API_KEY, "origin": origin, "destination": destination},
        timeout=10,
    )
    data = r.json()
    if data.get("status") == "1" and data.get("route"):
        paths = data["route"].get("paths") or []
        if paths:
            p = paths[0]   # 高德可能返回多条路线，取第一条
            result = {
                "distance_meters": p.get("distance"),
                "duration_seconds": p.get("duration"),
                "route_type": route_type,
            }
            # 驾车时高德会额外返回 taxi_cost(打车费，单位元)
            taxi = data["route"].get("taxi_cost")
            if route_type == "driving" and taxi:
                result["taxi_cost_yuan"] = taxi
            return result
    return {"error": data.get("info", "路线规划失败")}


def plan_transit(origin: str, destination: str, city: str) -> dict:
    """公交/地铁方案：返回乘坐线路(几号线)、上下车站、耗时、票价。"""
    r = requests.get(
        f"{AMAP}/direction/transit/integrated",
        params={"key": AMAP_API_KEY, "origin": origin, "destination": destination, "city": city},
        timeout=10,
    )
    data = r.json()
    if data.get("status") != "1" or not data.get("route"):
        return {"error": data.get("info", "公交规划失败")}
    transits = data["route"].get("transits") or []
    if not transits:
        return {"error": "没有找到公交/地铁方案"}
    t = transits[0]
    steps = []
    for seg in t.get("segments") or []:
        bus = seg.get("bus") or {}
        lines = bus.get("buslines") or []
        if lines:
            ln = lines[0]
            dep = (ln.get("departure_stop") or {}).get("name", "")
            arr = (ln.get("arrival_stop") or {}).get("name", "")
            steps.append(f"{ln.get('name', '')}({dep}→{arr})")
        else:
            wd = seg.get("walking_distance")
            if wd:
                steps.append(f"步行{wd}米")
    return {
        "route": " → ".join(steps),
        "duration_min": round(int(t.get("duration") or 0) / 60),
        "walking_meters": t.get("walking_distance"),
        "cost_yuan": t.get("cost"),
    }


def get_poi_photos(keyword: str, city: str, width: int = 600, limit: int = 3) -> list:
    """按"关键词+城市"搜 POI，依次尝试多个结果直到找到有照片的，返回照片 URL 列表。"""
    try:
        # 第一跳：关键词搜索，多取几个 POI(offset 拉大，提高命中率)
        r = requests.get(
            f"{AMAP}/place/text",
            params={"key": AMAP_API_KEY, "keywords": keyword, "city": city,
                    "offset": 5, "citylimit": "true"},
            timeout=10,
        )
        pois = r.json().get("pois") or []
        # 依次尝试每个 POI，找到有照片的就返回(很多博物馆第一结果可能没照片)
        for poi in pois[:5]:
            pid = poi.get("id")
            r2 = requests.get(
                f"{AMAP}/place/detail",
                params={"key": AMAP_API_KEY, "id": pid, "show_fields": "photos"},
                timeout=10,
            )
            p = (r2.json().get("pois") or [{}])[0]
            photos = p.get("photos") or []
            if not photos:
                continue
            urls = []
            for ph in photos[:limit]:
                url = ph.get("url", "")
                if url:
                    urls.append(f"{url}?x-oss-process=image/resize,w_{width}")
            if urls:
                return urls
        return []
    except Exception:
        return []


# ==================== 注册表：工具名 → 真实函数 ====================
# agent 拿到模型说的工具名(如 "search_poi")后，靠这个字典找到对应函数去执行
AVAILABLE_FUNCTIONS = {
    "search_poi": search_poi,
    "get_weather": get_weather,
    "plan_route": plan_route,
    "plan_transit": plan_transit,
}


# ==================== 工具的 schema(给模型看的"说明书") ====================
# 这是 OpenAI Function Calling 的标准格式：
#   一个工具 = {"type": "function", "function": {...}}
# function 里三样关键东西：
#   name        —— 工具名(要和 AVAILABLE_FUNCTIONS 的 key 一致)
#   description —— 干什么用的(模型主要靠这段文字判断"现在该不该调它")
#   parameters  —— 参数定义(JSON Schema 格式)，required 是必填参数
#
# 模型看到这份说明书后，会在回答里输出类似：
#   tool_calls = [{function: {name: "search_poi", arguments: '{"keywords":"景点","city":"北京"}'}}]
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_poi",
            "description": "高德关键词搜索：搜某城市的景点/酒店/美食等 POI，返回名称、地址、经纬度",
            "parameters": {
                "type": "object",
                "properties": {
                    "keywords": {"type": "string", "description": "搜索关键词，如「景点」「公园」「酒店」"},
                    "city": {"type": "string", "description": "城市名，如「北京」"},
                    "limit": {"type": "integer", "description": "返回条数，默认 5"},
                },
                "required": ["keywords", "city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "查询某城市实时天气",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名，如「北京」"},
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "plan_route",
            "description": "两个坐标点之间的路线规划，返回距离和耗时；route_type=driving 时额外返回打车费(taxi_cost_yuan)。origin/destination 传「经度,纬度」",
            "parameters": {
                "type": "object",
                "properties": {
                    "origin": {"type": "string", "description": "起点坐标「经度,纬度」"},
                    "destination": {"type": "string", "description": "终点坐标「经度,纬度」"},
                    "route_type": {"type": "string", "description": "walking 或 driving，默认 walking。市内短距离用 walking，要打车费用 driving"},
                },
                "required": ["origin", "destination"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "plan_transit",
            "description": "查询两点间的公交/地铁方案，返回乘坐线路(几号线)、上下车站、耗时和票价。origin/destination 传「经度,纬度」，city 传城市名",
            "parameters": {
                "type": "object",
                "properties": {
                    "origin": {"type": "string", "description": "起点坐标「经度,纬度」"},
                    "destination": {"type": "string", "description": "终点坐标「经度,纬度」"},
                    "city": {"type": "string", "description": "城市名，如「北京」"},
                },
                "required": ["origin", "destination", "city"],
            },
        },
    },
]
