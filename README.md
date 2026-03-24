# AI NPC 后端

为游戏中的 NPC 提供具备**长期记忆、世界观感知与结构化动作决策**的 AI 后端。采用 RAG + Function Calling，与游戏引擎通过 HTTP JSON 对接。

## 架构概览

```
游戏客户端 (前端)  ←—— HTTP POST /chat (JSON) ——→  AI 决策端 (本服务)
       ↓                                                    ↓
  画面 / 输入                                    短期记忆 + 长期记忆 (ChromaDB)
       ↓                                                    ↓
  解析动作 JSON 执行表现                         LLM (DeepSeek) → 结构化动作
```

- **Gateway**：`POST /chat` 接收 `player_id`、`message`、`scene_info`，返回动作 JSON。
- **短期记忆**：进程内保留最近 N 轮对话，保证上下文连贯。
- **长期记忆 (RAG)**：ChromaDB 存世界观 (Lore) 与玩家交互摘要，按语义检索召回。
- **推理**：System Prompt + 召回记忆 + 对话历史 → LLM（Function Calling）→ 标准动作 JSON。
- **沉淀**：每轮结束后将本轮对话写入长期记忆，供后续检索。

## 本地运行

### 1. 安装依赖

```bash
cd AI+NPC
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # Linux/macOS
pip install -r requirements.txt
```

### 2. 配置

- 复制 `config.example.yaml` 为 `config.yaml`。
- 在 `config.yaml` 中填写 LLM 的 `api_key`，或设置环境变量 `AI_NPC_LLM_API_KEY`。
- **不要将包含真实 api_key 的 config.yaml 提交到仓库。**

### 3. 启动服务

```bash
python run.py
```

默认监听 `http://0.0.0.0:5000`。

### 4. 健康检查

```bash
curl http://localhost:5000/health
```

## 接口说明

> 该项目目前没有单独的可视化前端界面；对外提供的是 HTTP API。

### POST /chat

**请求体 (JSON)**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| player_id | string | 是 | 玩家唯一标识 |
| message | string | 是 | 玩家当前对话内容 |
| scene_info | object | 否 | 场景信息（地点、时间等） |
| npc_id | string | 否 | 当前对话的 NPC 标识 |

**示例**

```json
{
  "player_id": "player_001",
  "message": "你好，今天天气怎么样？",
  "scene_info": { "location": "村口", "time": "早晨" }
}
```

**响应 (200)**

```json
{
  "action_type": "dialogue",
  "dialogue": "早上好，今天天气不错，适合出门走走。",
  "emotion": "friendly"
}
```

**动作字段说明**

| 字段 | 类型 | 说明 |
|------|------|------|
| action_type | string | dialogue / move / emote / use_item / idle |
| dialogue | string | NPC 台词 |
| emotion | string | 可选，情绪/表情 |
| target_id | string | 可选，动作目标 |
| extra | object | 可选，扩展 |

## 配置项

| 配置 | 说明 |
|------|------|
| use_rag | 是否启用长期记忆检索 |
| use_consolidation | 是否将每轮对话沉淀到长期记忆 |
| llm.* | 大模型 API 地址、模型名、temperature、超时等 |
| embeddings.* | 向量化模型（用于 RAG），默认 BGE 中文 |
| vectorstore.* | ChromaDB 持久化目录与集合名 |
| memory.short_term_turns | 短期记忆保留轮数 |
| memory.rag_top_k | RAG 召回条数 |
| mcp.enabled | 是否启用 MCP 工具动态发现与调用 |
| mcp.command | 启动 MCP 服务进程的命令（默认当前 python） |
| mcp.args | 启动 MCP 服务参数（默认 `npc_mcp/local_server.py`） |

## 世界观 (Lore) 导入

可将静态世界观文本写入 ChromaDB 的 `lore` 集合，供 RAG 检索。你可以直接使用内置脚本把 `lore/*.md` 导入：

```bash
python scripts/import_lore.py
```

## 技术栈

- **Web**：Flask
- **LLM**：DeepSeek API（OpenAI 兼容）
- **向量库**：ChromaDB
- **嵌入**：sentence-transformers (BAAI/bge-small-zh-v1.5)

## 许可证

按项目约定。

## 项目目录与文件作用

### 根目录
- `config.yaml`：运行配置（LLM、嵌入模型、ChromaDB 持久化目录、短期/长期记忆参数等）。建议不要提交真实 `api_key`。
- `config.example.yaml`：配置示例（用于复制后自行填写密钥）。
- `requirements.txt`：Python 依赖列表。
- `run.py`：Flask 启动入口，启动 `app.main.create_app()`，监听 `0.0.0.0:5000`。
- `README.md`：项目说明。
- `.gitignore`：忽略虚拟环境、`config.yaml`、`data/`、`models/` 等不应提交的内容。

### `app/`
- `app/__init__.py`：包初始化文件（用于 Python 模块识别）。
- `app/config.py`：加载 `config.yaml`，并支持环境变量 `AI_NPC_LLM_API_KEY` 覆盖敏感的 LLM `api_key`。
- `app/main.py`：Web Gateway 与路由实现。
  - `GET /health`：健康检查。
  - `POST /chat`：核心对话接口（接收状态 -> 组装 prompt -> 调用 LLM -> 输出动作 JSON -> 记忆更新与沉淀）。
- `app/schemas/`
  - `__init__.py`：导出请求/响应相关类型（便于外部模块直接导入）。
  - `request.py`：定义 `/chat` 请求体结构 `ChatRequest`。
  - `response.py`：定义后端返回动作结构 `ActionResponse`（`action_type`、`dialogue`、`emotion`、`target_id`、`extra`）。
- `app/memory/`（双轨记忆）
  - `__init__.py`：导出短期/长期记忆类。
  - `short_term.py`：短期记忆（进程内，按 `player_id + npc_id` 分桶，保留最近 N 轮）。
  - `long_term.py`：长期记忆与 RAG（ChromaDB 持久化，既检索交互摘要，也检索 Lore）。
  - `consolidation.py`：记忆沉淀（每轮对话结束后把摘要/关键内容写入 ChromaDB，供后续 RAG 检索）。
- `app/reasoning/`（推理）
  - `__init__.py`：导出推理相关方法（prompt/llm 调用）。
  - `prompts.py`：将“场景信息 + 短期历史 + RAG 召回内容”组装成发送给 LLM 的消息（system/user）。
  - `llm.py`：调用 DeepSeek（OpenAI 兼容接口）并使用 Function Calling 输出结构化动作。
- `app/tools/`（本地工具）
  - `location_tools.py`：本地地点解析工具，输入地点字符串返回预置坐标。
  - `__init__.py`：导出本地工具。

### `lore/`
- `world.md`：世界观示例文本。该目录下的 `.md` 会被 `scripts/import_lore.py` 导入到 ChromaDB 的 `lore` 集合。

### `scripts/`
- `import_lore.py`：把 `lore/` 下的文本切片后写入 ChromaDB（用于 RAG 的 lore 检索）。

### `npc_mcp/`
- `local_server.py`：本地 MCP 服务，挂载 `get_npc_runtime_state(npc_id)` 工具。
- `README.md`：MCP 服务使用说明。

### 运行期生成/使用的目录
- `data/chroma/`：ChromaDB 持久化存储目录（由 `vectorstore.persist_dir` 决定）。
- `models/`：向量化模型缓存目录（由 `embeddings.cache_dir` 决定）。

## 启动后如何访问

`run.py` 启动时绑定 `0.0.0.0:5000`，所以：
- 在本机：访问 `http://localhost:5000/health`、`http://localhost:5000/chat`
- 在同局域网其它机器：访问 `http://<你的服务器IP>:5000/health`、`http://<你的服务器IP>:5000/chat`

注意：这里没有 UI 页面，只有 API 接口（游戏客户端/引擎需要直接调用这些 HTTP 地址）。

## MCP 启动与联动

1. 启动 MCP 服务（新终端）：

```bash
python npc_mcp/local_server.py
```

2. 启动 AI 后端（另一个终端）：

```bash
python run.py
```

3. 确保 `config.yaml` 中 `mcp.enabled: true`。

服务运行后，`/chat` 流程会在每轮对话中动态发现 MCP tools，并在模型产生对应 `tool_call` 时自动调用；你不需要手工调接口。

## 一次 /chat 请求的执行链路

1. 游戏客户端向后端发送 `POST /chat`，携带 `player_id`、`message`、可选 `scene_info`、可选 `npc_id`。
2. `app/main.py` 解析并校验请求，构建 `ChatRequest`。
3. `ShortTermMemory.get_recent()` 获取该玩家（与 NPC）最近 N 轮对话。
4. 若 `use_rag=true`：
   - `LongTermMemory.search()` 基于当前 `message`（+ `scene_info`）做语义检索
   - 检索交互摘要（按 `player_id` 过滤）+ Lore（不按玩家过滤）
5. `prompts.build_messages()` 将：
   - system：NPC 角色指令 + 长期记忆片段（RAG 召回）
   - user：场景信息 + 短期历史 + 当前玩家消息
   组装为发给 LLM 的 messages。
6. `llm.call_llm_with_tools()` 调用 DeepSeek（OpenAI 兼容接口），并通过 Function Calling 要求输出 `npc_action`。
7. `llm.py` 解析 tool call 的 `arguments`，映射为 `ActionResponse`（其中 `dialogue` 为必填）。
8. 更新短期记忆：
   - 写入本轮 `user`（玩家消息）
   - 写入本轮 `assistant`（NPC 回复）
9. 若 `use_consolidation=true`：
   - `consolidation.consolidate_turn()` 将本轮“玩家说/ NPC 回复（可附带场景）”写入 ChromaDB 的长期记忆（`kbase` 集合）。
10. 返回 `ActionResponse` 的 JSON 给游戏客户端，游戏引擎据此执行对话/动作表现。
