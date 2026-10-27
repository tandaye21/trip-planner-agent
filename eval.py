"""评测：造 eval 集，跑 agent.plan()，按规则打分，输出准确率报告。

用法（PowerShell）：
    cd D:\note-agent\trip-planner
    python eval.py
"""
import time

from agent import Agent

# eval 集：(问题, 期望天数)
EVAL_SET = [
    ("帮我规划北京3天旅行，喜欢历史文化", 3),
    ("杭州2天，想去西湖周边", 2),
    ("成都1天美食之旅", 1),
    ("上海2天亲子游", 2),
    ("西安3天，喜欢博物馆", 3),
]


def score_one(plan: dict, expected_days: int) -> tuple[bool, list[str]]:
    """按规则打分：返回 (是否通过, 问题列表)。"""
    issues = []

    # 解析失败(plan 里带 error 字段)
    if "error" in plan:
        return False, [f"解析失败: {plan['error']}"]

    if not plan.get("city"):
        issues.append("缺 city")

    days = plan.get("days")
    if not isinstance(days, list) or not days:
        issues.append("days 为空或格式错")
    else:
        if len(days) != expected_days:
            issues.append(f"天数不符(期望 {expected_days}，实际 {len(days)})")
        for d in days:
            attrs = d.get("attractions") or []
            if not attrs:
                issues.append("某天缺景点")
                break
            for a in attrs:
                if not a.get("name") or not a.get("lng") or not a.get("lat"):
                    issues.append("景点缺 name/坐标(疑似编造)")
                    break
            if not d.get("hotel") or not d["hotel"].get("name"):
                issues.append("某天缺酒店")
            if not d.get("meals"):
                issues.append("某天缺三餐")

    if not plan.get("weather"):
        issues.append("缺天气")

    return (len(issues) == 0), issues


def main() -> None:
    agent = Agent()
    passed = 0
    total = len(EVAL_SET)
    print(f"评测集 {total} 条，开始跑...\n")

    for i, (q, days) in enumerate(EVAL_SET, 1):
        agent.reset()  # 每条独立，避免多轮记忆串扰
        t0 = time.time()
        plan = agent.plan(q)
        ok, issues = score_one(plan, days)
        passed += int(ok)
        mark = "✅ 通过" if ok else "❌ " + "; ".join(issues)
        print(f"[{i}/{total}] {q}\n    → {mark}  ({time.time()-t0:.0f}s)")

    print(f"\n准确率：{passed}/{total} = {passed/total*100:.0f}%")


if __name__ == "__main__":
    main()
