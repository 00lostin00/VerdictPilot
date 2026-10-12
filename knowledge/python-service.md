# Python 接口与 SQLite 事务

## Python 类型与数据契约

## 这一课要解决什么

让请求在进入业务逻辑前就被验证。

## 核心推导

类型注解帮助理解与静态检查，运行时输入仍需校验。Pydantic 模型把字段长度、枚举范围和列表上限放在接口边界；错误返回 422 而不是在深层代码崩溃。业务约束例如不存在的题目应返回 404，队列满应返回 429，不能统统变成 500。

## 一个最小实现

```
class Submission(BaseModel):
    code: str = Field(min_length=1, max_length=60000)
# 输入契约与业务结果分开表示
```

## 容易误判的地方

忽略字段验证会让超大请求拖垮服务；仅靠前端限制也无效，因为客户端可以直接调用 API。

## 回到 VerdictPilot

阅读 src/verdictpilot/platform_models.py 与 api.py 的验证边界。

## SQLite 事务与可持久化进度

## 这一课要解决什么

让刷新、重启和并发请求不会丢掉学习证据。

## 核心推导

事务把一组相关写入合并为原子操作，例如测验记录与最佳分数一起提交。WAL 让读写并发更顺畅，但 SQLite 仍只有一个写者，需要短事务与 busy timeout。唯一键 (learner_id,lesson_id) 避免重复进度，UPSERT 更新最佳成绩时必须取 max。

## 一个最小实现

```
with connection:
    connection.execute("INSERT INTO attempts ...")
    connection.execute("UPDATE progress SET best_score=MAX(best_score, ?)", (score,))
```

## 容易误判的地方

跨线程共享默认 connection 会违反线程约束。每个操作独立连接，事务里不要等待外部模型或编译器。

## 回到 VerdictPilot

阅读 platform_store.py 的 record_quiz 与 connect。
