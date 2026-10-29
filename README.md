# 智能旅行助手

一个基于 MBTI 个性化与大模型 Function Calling 的旅行规划应用。输入城市、天数、到达离开时间和个人偏好，它会生成一份带真实图片、地图、交通、预算和完整时间线的行程。

完整的功能介绍和截图见 [DEMO.md](DEMO.md)。

> 首页的鲸鱼娘吉祥物来自开源桌宠项目 [RYANFFY/deepseek-dafeiyu-pet](https://github.com/RYANFFY/deepseek-dafeiyu-pet)，遵循 CC BY-NC-SA 4.0 授权（非商业使用）。

## 功能

- 按 MBTI 定制路线，支持为同行团队添加多人的 MBTI，并实时计算团队默契度、给出建议
- 景点、美食、住宿、天气、地铁公交、打车费均为高德真实数据，每个景点带推荐亮点和踩坑提醒
- 从到达到离开的完整时间线，精确到小时，三餐齐全，穿插休息点
- 个性化问卷：出行方式、口味、预算、兴趣、旅行主题、旅行期望等
- 行程一键保存，旅游后上传照片、写感受

<p align="center"><img src="screenshots/01-home.png" width="80%" alt="首页"></p>

## 快速开始

```bash
pip install -r requirements.txt
```

复制 `.env.example` 为 `.env`（放在 `note-agent/` 根目录），填入三个 key：

- `DASHSCOPE_API_KEY`：通义千问（阿里云百炼）
- `AMAP_API_KEY`：高德 Web 服务 Key
- `AMAP_JS_KEY`：高德 Web 端(JS API) Key（地图显示用，可选）

两个高德 key 都在 https://lbs.amap.com/ 免费注册。

```bash
cd trip-planner
python -m uvicorn main:app --reload
```

浏览器打开 http://localhost:8000/ 即可使用。

## 项目结构

```
trip-planner/
├── main.py          # FastAPI 入口
├── agent.py         # Function Calling agent 循环 + 多轮记忆 + 完整性校验
├── tools.py         # 高德真实 API 工具 + schema
├── config.py        # key、模型名、client
├── storage.py       # 行程保存/回顾
├── cli.py           # 命令行交互版
├── eval.py          # 评测集
├── static/          # 前端 + 吉祥物 + 图片
├── screenshots/     # 演示截图
└── requirements.txt
```

## 技术栈

Python · FastAPI · Function Calling · 高德地图 API · 通义千问(qwen-plus) · 原生 HTML/CSS/JS

## 版权说明

代码可自由使用。鲸鱼娘立绘来自开源桌宠项目，遵循 CC BY-NC-SA 4.0（署名、非商业、相同方式共享），如需商业用途请更换吉祥物素材。
