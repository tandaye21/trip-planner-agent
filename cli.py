"""交互式测试：像真实用户一样在命令行里用旅行助手（含多轮记忆）。

用法（PowerShell）：
    cd D:\note-agent\trip-planner
    python cli.py

命令：
    直接输入需求   → 生成易读的行程
    /stream        → 切换流式输出（逐 token 吐，看底层机制）
    /reset         → 清空对话
    /quit          → 退出
"""
import asyncio

from agent import Agent


def format_plan(plan: dict) -> str:
    """把结构化行程 dict 渲染成易读文本（纯展示，不影响底层 JSON）。

    为什么单独写这个？agent.plan() 返回的是给机器/前端读的 JSON dict，
    命令行里直接 print 会是一坨难读的 JSON。这里把它排版成人类易读的行程。
    """
    if "error" in plan:
        return f"[错误] {plan['error']}"

    # 顶部：城市 + 天气
    weather = plan.get("weather") or {}
    w = weather.get("weather", "")
    t = weather.get("temperature", "")
    sep = "=" * 40
    lines = [sep, f"城市：{plan.get('city', '未知')}    天气：{w} {t}°C", sep, ""]

    # 逐天渲染
    meal_label = {"breakfast": "早餐", "lunch": "午餐", "dinner": "晚餐"}
    for d in plan.get("days", []):
        lines.append(f"【Day {d.get('day_index', 0) + 1}】{d.get('theme', '')}")
        # 景点
        lines.append("  景点：")
        for a in d.get("attractions", []):
            lines.append(f"    - {a.get('name', '')}（{a.get('address', '')}）约 {a.get('visit_duration_min', '')} 分钟")
            if a.get("note"):
                lines.append(f"      -> {a['note']}")
        # 三餐
        lines.append("  餐饮：")
        for m in d.get("meals", []):
            label = meal_label.get(m.get("type"), m.get("type", ""))
            lines.append(f"    {label}：{m.get('name', '')}（¥{m.get('estimated_cost', '')}）")
        # 住宿
        hotel = d.get("hotel") or {}
        if hotel.get("name"):
            lines.append(f"  住宿：{hotel['name']}（¥{hotel.get('estimated_cost', '')}）")
        lines.append("")

    # 底部：预算 + 建议
    budget = plan.get("budget") or {}
    if budget.get("total"):
        lines.append(f"总预算：¥{budget['total']}")
    if plan.get("suggestions"):
        lines.append(f"建议：{plan['suggestions']}")
    return "\n".join(lines)


async def ask_stream(agent: Agent, q: str) -> None:
    """流式提问：async for 逐个消费 run_stream 吐出的片段并打印。"""
    async for chunk in agent.run_stream(q):
        print(chunk, end="", flush=True)
    print()


def main() -> None:
    agent = Agent()          # 一个 agent 实例，对话历史在它内部累积(多轮记忆)
    streaming = False        # 默认非流式(输出易读行程)

    print("旅行助手已启动。直接输入需求，如：帮我规划北京3天旅行")
    print("命令：/stream 切流式  /reset 清空  /quit 退出\n")

    while True:
        try:
            q = input("你> ").strip()   # 等用户敲一行，去掉首尾空格
        except (EOFError, KeyboardInterrupt):
            break                       # 用户按 Ctrl+C 或文件结束就退出

        if not q:
            continue                    # 空输入直接跳过
        if q == "/quit":
            break
        if q == "/reset":
            agent.reset()
            print("(对话已清空)\n")
            continue
        if q == "/stream":
            streaming = not streaming   # 切换流式/非流式
            print(("(已切换为流式)\n" if streaming else "(已切换为非流式)\n"))
            continue

        print("助手> ", end="", flush=True)
        if streaming:
            # 流式：run_stream 是异步生成器，要用 asyncio.run 驱动
            asyncio.run(ask_stream(agent, q))
        else:
            # 非流式：plan() 返回 dict，再用 format_plan 渲染成易读文本
            print(format_plan(agent.plan(q)))
        print()


if __name__ == "__main__":
    main()
