"""编排层：Function Calling 版 agent loop，带系统提示词 + 多轮记忆 + 结构化 JSON 输出。

【这个文件是干嘛的 —— 整个项目的"大脑"】
它就干一件事：跑一个叫 agent loop 的循环。流程是：

    用户提问
      ↓ 调 LLM(带上工具说明书 tools)
    LLM 说"我要调工具 X，参数是 ..."(返回 tool_calls)
      ↓ 我们执行工具 X
    把工具结果回填给 LLM(role="tool")
      ↓ 再调 LLM
    ... 重复，直到 LLM 不再要调工具，直接给出最终答案

面试问"agent 和普通 chat 的区别"，答的就是这个循环：
普通 chat 是"一问一答"；agent 是"问 → 想 → 调工具 → 拿结果 → 再想 → 答"。
"""
import json
import re

# config.py 里已经创建好的 LLM 客户端(client)和模型名(CHAT_MODEL)
from config import client, CHAT_MODEL
# tools.py 里定义好的：工具"说明书"(TOOLS) 和 工具名→真实函数 的对照表(AVAILABLE_FUNCTIONS)
from tools import AVAILABLE_FUNCTIONS, TOOLS

# 系统提示词：告诉 LLM "你是谁、按什么流程工作、最后输出什么格式"。
# 它会作为 messages 的第一条，role="system"，相当于给模型一份"人设 + 工作手册"。
TRAVEL_SYSTEM_PROMPT = """你是一个专业的旅行规划助手。用户会给出目的地、天数、出发日期、到达信息、离开信息、出行方式、同行人群、同行人数、MBTI性格、兴趣偏好、旅行主题、旅行期望、口味偏好、住宿预算、餐饮预算、住宿偏好等需求。

工作流程：
1. 用 search_poi 搜索该城市的景点/酒店/美食，拿真实名称和坐标
2. 用 get_weather 查该城市天气
3. 用 plan_transit 查景点之间(或酒店到景点)的地铁/公交，用 plan_route(route_type=driving) 查打车费，把交通方式写进每个景点的 transport 字段
4. 最后只输出一个 JSON 对象，不要任何其他文字、解释或 markdown 代码块

必须遵守：
- 用工具拿真实数据，绝不编造景点/天气/酒店/菜品
- 严格按用户说的天数生成：说 N 天就正好 N 天，一天不多一天不少
- 根据出发日期/到达信息/离开信息确定每天的具体 date：第一天=到达当天、最后一天=离开当天，中间按日期顺序排，日期必须和到达/离开对得上，绝不要自己随便选开始日期(否则会把离开当天漏掉)
- 行程要覆盖从到达到离开的完整时间段(到达当天、中间各天、离开当天都要写，别只写中间某一天)，第一天写清楚到达后怎么办，最后一天写清楚怎么去车站/机场离开
- 每天从早到晚按时间段排满，景点和三餐都要有具体时间(time)；完整的一天(既不是到达当天也不是离开当天)必须早中晚三餐齐全，到达/离开当天根据实际到站发车时间安排餐食
- 结合天气、出行方式、同行人群、兴趣偏好、旅行期望安排(自驾考虑停车；带老人少走路多休息；亲子安排适合孩子的景点；想放松就少赶路，想尝美食就多安排特色餐饮)
- MBTI 只是大致倾向的参考，别生硬套用刻板印象(如 INTJ 未必只爱博物馆、E 未必不爱安静)，以用户明确填写的兴趣/口味/期望和实际需求为准；多人同行时参考团队整体偏好、满足大多数人需求即可，不必兼顾每个人
- 结合口味偏好选餐厅(辣/甜/清淡/重口味/减脂餐)；结合同行人数安排餐食(独自推一人食套餐，多人推炒菜聚餐)；住宿价格控制在住宿预算内，每餐人均控制在餐饮预算内
- 每个景点都要写 transport 字段：从上一个地点(酒店/上一景点/餐厅)到这里怎么去，用 plan_transit/plan_route 查真实的地铁/公交/打车费，别只写第一个景点
- 每天安排 1-2 个休息点(咖啡店/茶馆/澡堂/公园等)，写进 breaks 字段，别让游客一直赶景点
- 结合出发日期的星期几和天气调整：周末热门景点早点去避人流、错峰安排，周中可安排更多体验项目；雨天/霾天优先室内
- 每天景点按"地理位置相近、动线顺畅"排序，并给每个景点标注建议游览时间段(time)
- 景点要写亮点(highlight)：用 2-3 句话写具体、有画面感、有代入感，突出最值得看的地方，让人有想去的冲动
- 每个景点还要写踩坑提醒(warning)：节假日人多、需提前预约、周一闭馆、位置偏、商业化重等，一句话点透
- 结合旅行主题安排(美食主线=多安排餐饮探店，看海发呆=多安排海边慢节奏，城市人文=多安排街区市井，历史研学=多安排博物馆遗址，citywalk=多安排步行街区漫步)
- 餐饮要写招牌菜和具体价格(signature)，推荐理由(recommend)要具体到口味、口碑或氛围
- 酒店要说明选择理由(reason)，并符合用户的住宿偏好(平价/舒适/靠近景点/交通方便)

JSON 结构(严格按此)：
{
  "city": "城市名",
  "transportation": "出行方式(高铁/自驾/飞机)",
  "start_date": "出发日期(如 2026-11-01)",
  "group": "同行人群(如 亲子/情侣/独自/带老人)",
  "expectation": "旅行期望(如 放松休闲/看景点/尝美食/留下回忆/陪伴家人)",
  "weather": {"weather": "晴", "temperature": "20"},
  "arrival": "到达信息(如：高铁 14:30 到北京南站)",
  "departure": "离开信息(如：11月9日 17:00 高铁离开)",
  "arrival_tip": "到达后的安排建议，如：高铁到站后先乘地铁去XX酒店放行李，再开始第一天游览",
  "days": [
    {
      "day_index": 0,
      "date": "当天日期(如 2026-11-01)",
      "theme": "当天主题",
      "attractions": [
        {
          "name": "景点名",
          "address": "地址",
          "lng": "116.1",
          "lat": "39.9",
          "time": "09:00-11:30",
          "transport": "从上一地点到这里的交通，如：地铁8号线(前门→金鱼胡同)约20分钟，打车约¥13",
          "visit_duration_min": 150,
          "highlight": "必看亮点(景点特色)",
          "note": "游览提示",
          "warning": "踩坑提醒(如：节假日人爆炸多/需提前预约/周一闭馆/位置偏)"
        }
      ],
      "meals": [
        {
          "type": "breakfast",
          "time": "07:30-08:30",
          "name": "店名",
          "estimated_cost": 40,
          "signature": "招牌菜及价格，如：烤鸭 ¥128",
          "recommend": "推荐理由"
        }
      ],
      "breaks": [
        {"time": "15:00-15:30", "name": "咖啡馆名", "type": "咖啡/茶馆/澡堂/公园歇脚", "note": "休息提示"}
      ],
      "hotel": {"name": "酒店名", "address": "地址", "estimated_cost": 300, "reason": "选择理由"}
    }
  ],
  "budget": {"total": 2000},
  "suggestions": "总体建议(结合用户的个性化信息如 MBTI/口味/预算等，写具体实用的提醒，别写通用套话)"
}
"""


class Agent:
    def __init__(self, model: str = CHAT_MODEL, tools: list = TOOLS,
                 functions: dict = AVAILABLE_FUNCTIONS,
                 system_prompt: str = TRAVEL_SYSTEM_PROMPT, max_steps: int = 8):
        # ===== 下面只是把参数存到实例(self)上，方便别的方法用 =====
        self.model = model            # 用哪个模型，默认 qwen-plus
        self.tools = tools            # 工具的"说明书"，调 LLM 时传给它，让它知道能调啥
        self.functions = functions    # 工具名 → 真实函数 的对照表，执行工具时靠它找到函数
        self.system_prompt = system_prompt
        self.max_steps = max_steps    # loop 最多转几圈，防止 LLM 一直要调工具导致死循环

        # ===== 多轮记忆的关键 =====
        # self.messages 存"整段对话历史"。因为它是实例属性(挂在 self 上)，
        # 而不是 run() 里的局部变量，所以一次 run() 结束后它还留着，
        # 下一次 run() 接着用 —— 这就是"多轮记忆"。
        # 开头先放一条 system 消息(人设)，之后每次问答往里追加。
        self.messages = [{"role": "system", "content": system_prompt}]

    def reset(self):
        """清空对话历史，开新一轮(把 messages 恢复成只有一条 system 消息)。"""
        self.messages = [{"role": "system", "content": self.system_prompt}]

    def _run_tool(self, name: str, args: dict):
        """按工具名找到真实函数并执行。名字带下划线开头 = 内部方法，外面不直接调。"""
        fn = self.functions.get(name)
        if fn is None:
            return {"error": f"没有名为 {name} 的工具"}
        try:
            # **args 把字典解包成关键字参数。例如：
            #   args = {"keywords": "景点", "city": "北京"}
            #   fn(**args) 等价于 fn(keywords="景点", city="北京")
            return fn(**args)
        except Exception as e:
            # 工具执行出错时不崩掉整个程序，而是把错误信息当作结果回填给 LLM，
            # 让 LLM 知道"工具坏了"，它会自己换个问法重试。
            return {"error": str(e)}

    def run(self, question: str) -> str:
        """非流式：跑一轮 loop，返回最终文本(同时保留多轮上下文)。"""
        # ---- 第 1 步：把用户问题追加进历史 ----
        self.messages.append({"role": "user", "content": question})

        # ---- 第 2 步：开始循环(最多 max_steps 圈) ----
        for _ in range(self.max_steps):
            # 调 LLM。关键参数 tools=self.tools —— 把工具说明书交给 LLM，
            # 它这次就可能返回 tool_calls(说"我要调工具")而不是直接回答。
            resp = client.chat.completions.create(
                model=self.model, messages=self.messages, tools=self.tools,
            )
            msg = resp.choices[0].message   # LLM 这一轮的回复

            # ---- 第 3 步：判断 LLM 想"调工具"还是"直接回答" ----
            if not msg.tool_calls:
                # 没有 tool_calls = LLM 已经给出最终答案，答案在 msg.content 里
                answer = msg.content or ""
                # 把最终答案也存进历史，这样下一轮问答时 LLM 能"记得自己说过啥"
                self.messages.append({"role": "assistant", "content": answer})
                return answer

            # ---- 有 tool_calls = LLM 要调工具，我们帮它执行 ----
            # 先把这条"要求调工具"的 assistant 消息原样存回历史(里面带 tool_calls 信息)
            self.messages.append(msg)
            # 逐个执行 LLM 要调的工具(一次可能调多个)
            for call in msg.tool_calls:
                name = call.function.name                              # 工具名
                # LLM 给的参数是 JSON 字符串，如 '{"city":"北京"}'，json.loads 转成 dict
                args = json.loads(call.function.arguments or "{}")
                result = self._run_tool(name, args)                    # 真正执行工具
                # 回填：把工具结果以 role="tool" 存回历史。
                # 注意！必须带 tool_call_id，LLM 才能把这个结果对应到它之前的那次调用。
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(result, ensure_ascii=False),
                })
            # 一圈工具执行完，回到 for 开头再调 LLM，让它根据工具结果继续判断

        # 循环跑满还没得到最终答案(LLM 一直要调工具)，兜底返回
        self.messages.append({"role": "assistant", "content": "任务未完成：达到最大步数"})
        return "任务未完成：达到最大步数"

    def _extract_json(self, text: str) -> dict:
        """从 LLM 输出的文本里抠出 JSON(容忍它夹带 markdown 代码块或废话)。"""
        if not text:
            return {"error": "空响应"}
        # 如果 LLM 用 ```json ... ``` 包起来了，先剥掉代码块围栏
        if "```" in text:
            start = text.find("```")
            end = text.rfind("```")
            inner = text[start + 3:end]
            inner = inner.split("\n", 1)[-1] if "\n" in inner else inner
            text = inner
        # 取第一个 { 到最后一个 } 之间的内容
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            return {"error": "响应中没有 JSON", "raw": text[:500]}
        try:
            return json.loads(text[start:end + 1])   # JSON 字符串 → dict
        except json.JSONDecodeError as e:
            return {"error": f"JSON 解析失败: {e}", "raw": text[:500]}

    def plan(self, question: str) -> dict:
        """跑一轮并返回结构化 JSON(dict)。给 /plan 接口和前端直接消费。"""
        text = self.run(question)        # 先跑 loop 拿到最终文本(通常是 JSON 字符串)
        data = self._extract_json(text)  # 再抠出 JSON 转成 dict
        # 完整性兜底：天数不足 / 完整的一天三餐不齐时，追问模型补全(最多重试 2 次)
        for _ in range(2):
            reason = self._incomplete_reason(data, question)
            if not reason or "error" in data:
                break
            data = self._extract_json(
                self.run(f"你刚才的计划不完整：{reason}。请重新输出完整 JSON，别再漏。")
            )
        return data

    def _incomplete_reason(self, data: dict, question: str) -> str:
        """检查计划是否完整，返回不完整原因(空串=完整)。"""
        days = data.get("days") or []
        if not days:
            return "没有任何 days"
        m = re.search(r'(\d+)\s*天', question)
        if m and int(m.group(1)) > len(days):
            return f"用户要 {int(m.group(1))} 天，只给了 {len(days)} 天"
        # 完整的一天(不是到达当天也不是离开当天)必须三餐齐全
        for i, d in enumerate(days):
            meals = d.get("meals") or []
            is_full_day = (i != 0) and (i != len(days) - 1)
            if is_full_day and len(meals) < 3:
                return f"第 {i + 1} 天是完整的一天，却只有 {len(meals)} 餐，应早中晚三餐齐全"
        return ""

    async def run_stream(self, question: str):
        """流式版：逻辑和 run() 一样，但用 yield 边跑边把进展"吐"出去。

        异步生成器：调用它不会立刻执行完，而是每次 yield 就交出一小段结果，
        调用方(如 main.py 的 SSE)拿到一段就发一段给用户 —— 这就是"流式"。
        """
        self.messages.append({"role": "user", "content": question})

        for step in range(self.max_steps):
            # 先把"正在思考"这个进展 yield 出去
            yield f"[步骤 {step + 1}] 模型思考中…"
            resp = client.chat.completions.create(
                model=self.model, messages=self.messages, tools=self.tools,
            )
            msg = resp.choices[0].message

            if not msg.tool_calls:
                # 拿到最终答案了。这次用 stream=True 让 LLM 逐 token 吐，
                # 我们每拿到一小段就 yield 出去，实现"一个字一个字出来"。
                stream = client.chat.completions.create(
                    model=self.model, messages=self.messages, stream=True,
                )
                full = []   # 一边 yield 一边累积，最后把完整答案存进历史
                for chunk in stream:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if delta and delta.content:
                        full.append(delta.content)
                        yield delta.content   # 每拿到一段就吐一段
                self.messages.append({"role": "assistant", "content": "".join(full)})
                return

            self.messages.append(msg)
            for call in msg.tool_calls:
                name = call.function.name
                args = json.loads(call.function.arguments or "{}")
                yield f"→ 调用工具 {name}({args})"       # 把"要调哪个工具"也实时吐给用户
                result = self._run_tool(name, args)
                yield f"  结果：{json.dumps(result, ensure_ascii=False)}"
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(result, ensure_ascii=False),
                })
        yield "（达到最大步数，任务未完成）"
