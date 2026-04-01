# ai-npc-pygame-demo

一个独立的 Pygame MVP 演示项目，通过 HTTP 调用 `AI-NPC` 服务的 `POST /chat` 接口，实现玩家与 NPC 的最小可玩交互循环。

## 目标

- 玩家可键盘移动
- 1~3 个 NPC 待机/巡逻
- 玩家靠近后按 `E` 触发对话
- 游戏端调用 `AI-NPC` 的 `POST /chat`
- 支持动作映射：`dialogue / move / idle`

## 技术栈

- Python 3.10+
- pygame
- requests

## 目录结构

```text
ai-npc-pygame-demo/
  README.md
  requirements.txt
  run.py
  config.py
  game/
    __init__.py
    constants.py
    models.py
    ai_client.py
    world.py
    ui.py
    main_loop.py
  assets/
    fonts/
```

## 后端接口契约

### 请求

`POST http://localhost:5000/chat`

```json
{
  "player_id": "player_001",
  "npc_id": "npc_guard_001",
  "message": "你好",
  "scene_info": {
    "location": "village_square",
    "time": "day",
    "distance_to_player": 1.8,
    "npc_runtime_state": "idle",
    "last_action_result": "success"
  }
}
```

### 响应

```json
{
  "action_type": "dialogue",
  "dialogue": "你好，旅行者。",
  "emotion": "friendly",
  "target_id": null,
  "extra": {}
}
```

## 运行方式

1. 创建并激活虚拟环境（可选）
2. 安装依赖：

```bash
pip install -r requirements.txt
```

3. 启动你的 AI-NPC 后端（默认假设在 `http://localhost:5000`）
4. 运行游戏：

```bash
python run.py
```

## 操作说明

- `WASD` 或方向键：移动玩家
- `E`：与最近且在范围内的 NPC 交互
- `ESC`：退出

## 降级策略

- 请求超时（默认 1.2s）：显示本地兜底台词
- 网络错误：NPC 进入 idle，并显示错误兜底台词
- 返回字段缺失：忽略本次 action，记录错误计数
- 每个 NPC 调用冷却（默认 2.0s）防止请求风暴

## 关键参数（默认）

- 窗口：`960x540`
- FPS：`60`
- 玩家速度：`180 px/s`
- NPC 速度：`90 px/s`
- 交互距离：`80 px`
- AI 冷却：`2.0s`
- AI 超时：`1.2s`
