# 本地 MCP 服务

当前提供一个工具：`get_npc_runtime_state(npc_id)`，返回：
- 当前坐标（location）
- 职业（job）
- 当前任务（task）
- 可行动作（available_actions）

## 启动

```bash
python npc_mcp/local_server.py
```

默认使用 stdio 模式，供 MCP 客户端接入。

