# VerdictPilot

算法训练与代码诊断工作台。将课程、C++提交、知识检索、执行结果、错题记忆和复习记录放在同一流程中。

![学习概览](docs/screenshots/dashboard.png)

## 功能

| 模块 | 内容 |
| --- | --- |
| 训练内容 | 6条路径、24节课程、48道测验、12道代码题和61个固定判题用例 |
| 代码诊断 | BM25检索、C++测试证据、逐用例输出和调用轨迹 |
| 记忆与复习 | SQLite错题记录、笔记、草稿和复习反馈 |
| 工具接口 | 知识检索、代码测试、错题读取与写入四类函数工具 |
| 后台执行 | 有界提交队列、并发拒绝、超时/输出清理和中断标记 |
| Web与API | 桌面/手机布局、任务历史、知识检索和档案导出 |

## 快速运行

需要Python3.11+、uv；执行代码还需g++。

```bash
git clone https://github.com/00lostin00/VerdictPilot.git
cd VerdictPilot
uv sync --frozen --extra dev
uv run --frozen --extra dev verdictpilot serve --port 8000
```

访问 http://127.0.0.1:8000，接口文档在/docs。默认关闭代码执行，只读学习与检索可以运行。对已经检查过的本地可信代码，可用--trusted-local启动；宿主机执行不提供文件、网络或内存隔离。受限Docker后端配置见[平台说明](docs/PLATFORM.md)和[威胁模型](docs/THREAT_MODEL.md)。

## 示例与验证

```bash
uv run --frozen --extra dev verdictpilot analyze --input examples/graph-hint.json --provider offline
uv run --frozen --extra dev pytest
uv run --frozen --extra dev ruff check .
uv run --frozen --extra dev verdictpilot eval
uv run --frozen --extra dev python tools/verify_bank.py
```

本地记录为24项测试、7条离线回归、12份参考程序通过61个题库用例。它们验证固定流程与样本，不是大模型诊断准确率。可选模型使用OPENAI_API_KEY、OPENAI_MODEL及VERDICTPILOT_PROVIDER=openai，配置从环境变量读取，不自动加载.env。

## 文档

- [架构](docs/ARCHITECTURE.md)
- [平台与部署](docs/PLATFORM.md)
- [威胁模型](docs/THREAT_MODEL.md)
- [评测范围](docs/EVAL_RESULTS.md)

当前面向单实例本地训练。学习标识不等于登录身份，公网多用户服务需要认证、授权与独立执行环境。课程和项目里程碑是训练内容，不表示用户已经完成所有进阶实现。

MIT License.
