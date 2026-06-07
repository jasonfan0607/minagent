# AI Prompt 与问题解决记录

## 开发 Prompt

用户题目要求：

```text
允许使用任何 AI 工具辅助开发，从零实现一个最小可用的 Agent。
要求支持多轮对话和 session 维护；不直接依赖现成 Agent 框架完成主流程，如 LangChain / OpenHands 等，核心 runtime 需要自己实现。
Agent 至少支持一个基本循环：接收用户输入；判断是直接回答，还是调用工具；执行工具；读取工具结果；继续下一步，直到给出最终答案。
至少提供 3 个工具，例如 calculator、search（可 mock）、read_docs / todo / weather（可自定义）。
需要最大步数限制、基本异常处理、工具调用 trace 或执行日志。
至少支持一个跨轮次继续执行场景：第一轮发起一个任务，Agent 创建任务并记录状态；第二轮用户追问进度，Agent 能基于已有状态继续处理，而不是把每轮都当成全新问题。
需要使用真实的 LLM API。
提交内容包含代码链接、终端或网页操作录屏、README（运行方式、系统设计、memory 的召回时机与放置方式说明）、AI Prompt 与问题解决记录。
```

前端可视化追加需求：

```text
帮我写一个前端页面，能将以上内容（对话、工具调用等操作）可视化。
```

## 使用 AI 辅助的方式

- 用 AI 辅助拆解题目验收点，形成最小可用 Agent 的模块边界。
- 用 AI 辅助生成 runtime 循环、工具接口、session 存储和前端可视化页面的实现草案。
- 用 AI 辅助检查 README 是否逐项覆盖提交要求。
- 最终代码仍围绕自实现 runtime：没有使用 LangChain、OpenHands 等现成 Agent 框架完成主流程。

## 关键设计决策

1. 不引入 LangChain / OpenHands 等 Agent 框架，runtime 循环写在 `min_agent/runtime.py`。
2. 使用 OpenAI Chat Completions 风格接口，支持真实 LLM API，同时允许通过 `LLM_BASE_URL` 切换 DeepSeek 等兼容服务。
3. LLM 与 runtime 通过严格 JSON 协议交互：`final` 表示最终回答，`tool` 表示请求工具调用。
4. session 使用本地 JSON 文件持久化，便于演示、调试和录屏检查。
5. todo 工具直接读写 session 中的 `tasks`，用于跨轮次任务继续执行。
6. calculator 使用 AST 白名单解析，避免 `eval` 执行任意代码。
7. 前端不引入构建工具和第三方依赖，使用原生 HTML / CSS / JavaScript，由 Python 标准库 HTTP 服务托管。
8. 前端直接读取同一份 session 数据，将 messages、tasks、traces 分别可视化，便于解释 Agent 的执行过程。

## 问题与处理

### LLM 可能输出 Markdown 包裹的 JSON

- 问题：模型有时返回 ```json 代码块，而不是纯 JSON。
- 处理：`runtime.py` 会提取 JSON 代码块；如果没有代码块，会尝试截取文本中的第一个 JSON 对象。

### LLM 可能调用不存在的工具或参数错误

- 问题：模型可能返回未知工具名，或传入缺失参数。
- 处理：runtime 捕获异常，把错误作为 observation 返回给 LLM，同时记录到 trace。

### Agent 可能无限循环调用工具

- 问题：如果 LLM 一直选择工具调用，可能无法结束。
- 处理：`AGENT_MAX_STEPS` 限制最大步数，到达限制后返回兜底答案。

### 跨轮次状态容易丢失

- 问题：如果只依赖单轮 prompt，第二轮无法知道第一轮创建的任务。
- 处理：每轮开始加载 session，结束保存 session；任务状态结构化保存在 `session.tasks`，不是只存在聊天文本中。

### `.env` 文件不会自动生效

- 问题：项目无第三方依赖，不能依赖 `python-dotenv` 自动加载 `.env`。
- 处理：在 `llm.py` 中用标准库实现简单 `.env` 加载逻辑，优先不覆盖系统环境变量。

### 需要网页录屏展示 trace

- 问题：单纯 CLI 对工具调用和 trace 的展示不够直观。
- 处理：新增 `min_agent/web.py`、`web/index.html`、`web/styles.css`、`web/app.js`，提供可视化控制台。

### API Key 不能提交到仓库

- 问题：本地测试需要真实 API Key，但提交代码不能泄露密钥。
- 处理：保留 `.env.example` 作为模板，通过 `.gitignore` 忽略 `.env`，README 中提醒提交前确认真实 Key 未进入仓库。

## 验收样例

CLI 验收：

```powershell
python -m min_agent.cli --session exam --message "计算 (12+8)*3，并创建任务：整理 Agent 要求"
python -m min_agent.cli --session exam --message "继续刚才的任务，现在进度是什么？"
Get-Content .agent_data\sessions\exam.json
```

前端验收：

```powershell
python -m min_agent.web
```

然后打开：

```text
http://127.0.0.1:8765/
```

推荐测试输入：

```text
请计算 (12+8)*3，并告诉我计算结果。
```

```text
请搜索 minimal agent runtime 的资料，并总结两点。
```

```text
创建一个任务：整理 Agent 笔试题要求，并记录当前状态为已开始。
```

```text
继续刚才的任务，现在进度怎样？请更新一条进度说明。
```

## 最终提交前检查

- README 已包含运行方式、系统设计、memory 召回时机与放置方式说明。
- `AI_PROMPTS_AND_NOTES.md` 已记录开发 Prompt、设计决策和问题解决过程。
- `.env.example` 保留模板，`.env` 不提交。
- `.agent_data` 不提交，避免把本地运行数据作为源码提交。
- `__pycache__` 不提交。
- 录屏建议使用前端页面展示对话流、工具调用时间线、任务状态和 session trace。
