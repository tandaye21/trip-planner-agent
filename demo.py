"""手动验证：结构化 JSON 输出 + 多轮记忆。

用法（PowerShell）：
    cd D:\note-agent\trip-planner
    python demo.py

中文若乱码，先执行 `chcp 65001`。
"""
import json

from agent import Agent


def main() -> None:
    agent = Agent()

    print("=" * 60)
    print("一、结构化 JSON 输出（plan 接口）")
    print("=" * 60)
    plan = agent.plan("帮我规划北京2天旅行，喜欢历史文化")
    print(json.dumps(plan, ensure_ascii=False, indent=2))

    print("\n" + "=" * 60)
    print("二、多轮记忆：追问（引用上一步的「第二天」）")
    print("=" * 60)
    print(agent.run("把第二天的行程换成美食主题"))


if __name__ == "__main__":
    main()
