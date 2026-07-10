# Contributing

感谢参与 RepoCourier。

1. Fork 仓库并创建功能分支。
2. 保持改动范围清晰，为新逻辑补充测试。
3. 运行 `pytest` 和 `ruff check .`。
4. 提交 Pull Request，并说明行为变化与验证方式。

新增推送通道时，请实现 `pushers/base.py` 中的 `Pusher` 协议，不要在日志中输出完整 Token、Webhook 或消息服务响应中的敏感字段。
