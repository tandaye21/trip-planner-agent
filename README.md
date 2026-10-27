# 🐳 智能旅行助手（Trip Planner Agent）

一个基于 **Function Calling + 高德真实数据 + MBTI 个性化** 的智能旅行规划助手。

输入城市、天数、到达/离开时间、出行偏好和团队 MBTI，自动生成一份带 **真实图片、地图、地铁线路、打车费、三餐时间、休息点、避雷提醒** 的完整行程；还能 **一键保存行程、旅游后上传照片写回顾**。

> 吉祥物「大肥鱼」是 DeepSeek 的民间二创「蓝色鲸鱼娘」形象，来自开源桌宠项目 [RYANFFY/deepseek-dafeiyu-pet](https://github.com/RYANFFY/deepseek-dafeiyu-pet)，遵循 CC BY-NC-SA 4.0 授权（非商业使用）。

---

## ✨ 核心特色

### 1. MBTI 个性化路线（最大亮点）
- 支持 **16 型人格**，可为同行团队添加 **多个人** 的 MBTI
- **团队匹配度打分**：多人出行实时计算默契度（E/I 平衡 + J/P 平衡 + 角色覆盖 + 和谐度），并给出「加一个 ISTJ 负责统筹更好」这类建议
- MBTI 只作参考，用户明确填写的偏好优先，**不刻板**

### 2. 真实数据，不靠编
- 高德真实 POI：景点 / 美食 / 住宿，带实拍图、经纬度
- 真实天气、地铁公交线路（几号线、上下车站、耗时票价）、打车费
- 每个景点带「⭐ 亮点 + ⚠️ 踩坑提醒」

### 3. 完整时间线，从到达到离开
- 明确「几点下高铁/飞机」到「几月几号几点离开」，覆盖全程
- 每天精确到小时，三餐齐全 + 咖啡/茶馆休息点，自动根据到达/离开时间调整

### 4. 个性化问卷
出行方式 · 同行人群 · 人数 · 口味 · 住宿/餐饮预算 · 兴趣 · 主题模板（美食主线/看海发呆/城市人文/历史研学/citywalk）· 旅行期望

### 5. 旅行日记
一键保存行程 → 旅游后上传照片 + 写感受，形成自己的旅行记录

---

## 🚀 快速开始

### 1. 装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置密钥
复制 `.env.example` 为 `.env`（放在 `note-agent/` 根目录），填入三个 key：
- `DASHSCOPE_API_KEY` — 通义千问（阿里云百炼）
- `AMAP_API_KEY` — 高德 Web 服务 Key
- `AMAP_JS_KEY` — 高德 Web 端(JS API) Key（地图显示用）

> 高德两个 key 都在 https://lbs.amap.com/ 免费注册，个人开发者免费额度够用。

### 3. 启动
```bash
cd trip-planner
python -m uvicorn main:app --reload
```
浏览器打开 **http://localhost:8000/** 即可使用。

---

## 🎬 演示 Demo（怎么突出特色）

**一句话 pitch**：
> 别的攻略 App 给你一样的路线，我根据你的 MBTI、口味、预算，给你一条**专属于你的**路线——还告诉你团队里谁和谁更搭。

**演示流程**：

1. **首屏**：鲸鱼娘吉祥物 + 功能思维导图 + 主题模板快捷入口
2. **输入**：「帮我规划北京 3 天旅行」
3. **填问卷（亮点）**：
   - 到达信息「高铁 14:30 到北京南站」、离开信息「11月9日 17:00 高铁离开」
   - 同行人 MBTI 加 3 个人（ISTJ + ENFP + INFP）→ 下面**实时显示「团队默契度 91 分 · 天作之合」**
4. **看结果**：
   - 顶部高德地图标出 D1/D2/D3 景点
   - 时间线：Day1 到达 → Day2 完整 → Day3 离开，三餐齐全、日期对齐
   - 每个景点：真实图 + ⭐亮点 + ⚠️踩坑 + 🚇地铁几号线/打车费
   - 咖啡/茶馆休息点也有真实图
5. **对比（小红书传播点）**：把团队 MBTI 换成「全 E 人」再生成一次 → **同一城市、完全不同路线**
6. **保存回顾**：点「保存到我的行程」→ 顶栏「我的行程」→ 上传照片、写感受

---

## 🏗 架构

```
浏览器 / 前端
   │  POST /plan /chat /photo /trips ...
   ▼
FastAPI (main.py)
   │
   ▼
Agent Loop (agent.py)  ── 循环：模型 → tool_calls → 执行 → 回填
   │              │
   │ 需要工具      │ 需要数据
   ▼              ▼
tools.py         storage.py（行程保存）
高德真实 API       data/trips.json
（景点/天气/路线/照片）
   │
   ▼
LLM：通义千问 qwen-plus
```

## 📁 项目结构

```
trip-planner/
├── main.py            # FastAPI 入口（/plan /chat /photo /trips 等接口）
├── agent.py           # 核心：Function Calling agent loop + 多轮记忆 + 完整性兜底
├── tools.py           # 高德真实 API 工具 + 给模型看的 schema
├── config.py          # key、模型名、client
├── storage.py         # 行程保存/回顾（本地 JSON）
├── cli.py             # 命令行交互版
├── eval.py            # 评测集 + 准确率
├── demo.py            # 快速演示脚本
├── static/            # 前端（index.html + 吉祥物 + 图片）
├── requirements.txt
├── Dockerfile
└── .env.example
```

## 🧰 技术栈

Python · FastAPI · Function Calling · 高德地图 API · 通义千问(qwen-plus) · SSE 流式 · 原生 HTML/CSS/JS

## ⚖️ 版权说明

- 代码：本项目代码可自由使用。
- 吉祥物「大肥鱼」立绘：来自 [RYANFFY/deepseek-dafeiyu-pet](https://github.com/RYANFFY/deepseek-dafeiyu-pet)，**CC BY-NC-SA 4.0**（需署名、非商业、相同方式共享）。**如需商业用途，请更换吉祥物素材**。
