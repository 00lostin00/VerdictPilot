# 代码执行信任边界

## 执行边界：本机、容器与不可信输入

## 这一课要解决什么

准确说明限制覆盖了什么，也说明没有覆盖什么。

## 核心推导

本地执行是在宿主机运行用户程序，只适合自用可信代码。受限 Docker 后端通过禁网、非 root、只读根文件系统、CPU/内存/进程限制收窄风险，但并不等于生产级恶意代码隔离。超时、输出上限、进程树清理与凭证隔离应分别检查。

## 一个最小实现

```
docker run --network none --read-only --cpus 1 --memory 256m \
  --pids-limit 64 --security-opt no-new-privileges ...
```

## 容易误判的地方

在 subprocess 完成后才截断 stdout，并不能防止运行过程中内存被超大输出耗尽。本地教学模式必须明确边界。

## 回到 VerdictPilot

阅读 docs/THREAT_MODEL.md；不要将本地服务端口暴露给不可信网络。
