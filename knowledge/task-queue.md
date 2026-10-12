# 任务队列与调用轨迹

## 后台任务、背压与任务状态

## 这一课要解决什么

让编译等待进入队列，网页接口继续响应。

## 核心推导

POST 提交返回任务 ID 与 202，客户端轮询读取状态：queued→running→completed 或 failed。线程池限制并行度，但默认队列可能无上限，所以还需有界容量；满时返回 429。服务重启后遗留任务必须标记 interrupted，不能永久显示运行中。

## 一个最小实现

```
capacity = threading.BoundedSemaphore(16)
if not capacity.acquire(blocking=False):
    raise QueueFullError()
# worker 的 finally 中释放容量
```

## 容易误判的地方

async def 不会自动让同步编译非阻塞。同步工作直接占用事件循环会让健康检查和其他用户请求一起等待。

## 回到 VerdictPilot

阅读 platform_service.py 的容量控制、finally 和 platform_store.py 的恢复逻辑。

## 调用轨迹、延迟与错误恢复

## 这一课要解决什么

让每次失败都有可定位的阶段和可复现的输入。

## 核心推导

一次诊断应有 run_id，阶段事件包括开始、检索结束、记忆读取、执行结束和最终回答。延迟要区分排队、编译、测试与模型耗时；P95 比平均值更能反映尾部体验。日志记录必要元数据，避免 Key 与无关个人数据。任务失败返回可理解信息，详细堆栈留在服务日志。

## 一个最小实现

```
trace.emit("tool.cpp_runner.completed", status=report.status, case_count=len(report.cases))
# run_id 将前端记录、执行结果与事件关联
```

## 容易误判的地方

“请求失败”无法定位问题；但把原始密钥或完整敏感请求打印出来也不可取。观测信息要有目的。

## 回到 VerdictPilot

阅读 tracing.py 和平台运行详情，观察没有调用的阶段是否仍被错误宣称。
