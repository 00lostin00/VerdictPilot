# Agent 工具与持久记忆

## 函数工具与 Agent 循环

## 这一课要解决什么

让模型在明确契约下选择工具，并从执行结果继续推理。

## 核心推导

工具描述说明何时调用、参数限制与返回语义。模型提出调用，运行时验证参数并执行，结果返回给模型，直到产生最终输出或达到停止条件。检索、代码执行、记忆写入具有不同副作用；写记忆要有执行证据或用户确认，不能把猜测固化成事实。

## 一个最小实现

```
@function_tool
def retrieve_algorithm_knowledge(query: str, limit: int = 4) -> str:
    """检索本地算法资料；诊断前先寻找适用条件。"""
    return serialize(store.search(query, limit))
```

## 容易误判的地方

工具数量多并不等于 Agent 更强。描述重叠、参数松散与无限重试会增加成本和错误路径。

## 回到 VerdictPilot

阅读 openai_agent.py，按自己的账户配置模型后检查真实 trace。

## 持久记忆与间隔复习

## 这一课要解决什么

把确认后的教训保存下来，并用复习反馈调整时间。

## 核心推导

会话上下文、长期错题记忆和运行 trace 有不同用途。错题记录保存问题、症状、类别与自己的教训；复习调度保存下一次日期与间隔。首次错误应立即复盘；再次回忆失败缩短间隔，容易回忆时延长。它是学习安排，不是对真实能力的认证。

## 一个最小实现

```
interval = {"again": 1, "hard": old, "good": old*2, "easy": old*3}[rating]
due_at = now + timedelta(days=min(interval, 90))
```

## 容易误判的地方

仅点“记住了”不能证明问题已解决。应重写代码或复述不变量，再评价回忆质量。历史记录的检索也应限定学习档案。

## 回到 VerdictPilot

阅读 platform_store.py 的 add_mistake 与 review，记录调度算法的局限。
