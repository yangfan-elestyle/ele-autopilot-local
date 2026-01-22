# Repository Guidelines

## 项目概述

- ele-autopilot-local 是本地浏览器自动化服务，基于 `browser-use==0.11.3`。
- 对外提供 FastAPI HTTP API，通过 LLM Agent 驱动浏览器执行任务；任务以 Job 形式异步运行，可查询/删除。

## 架构与核心流程

- **HTTP Request** → `routers/autopilot.py` 接收 Job 创建/查询/删除等请求
- **JobService**（`autopilot/job_service.py`）创建 Job、内存存储并异步调度执行
- **Job**（`autopilot/job.py`）串行执行多个 Task，聚合状态（PENDING → RUNNING → COMPLETED/FAILED）
- **TaskRunner**（`autopilot/task.py`）初始化 LLM/Browser，调用 `browser_use.Agent` 执行单个自然语言任务
- **TaskActionHandler**（`autopilot/task_action.py`）解析 `AgentHistoryList`，提取 summary/steps 等结构化信息用于日志/云端备份 payload

## 项目结构与模块组织

- `main.py`：FastAPI 应用入口与 CLI；`app_meta.py` 提供项目信息与版本。
- `routers/`：对外 API 路由（如 `/system/*`、`/autopilot/*`）。
- `middleware/`：统一响应包装与异常处理（`{code, message, data}`）。
- `autopilot/`：Job/Task 执行核心（`job_service.py`、`job.py`、`task.py`、`task_action.py`、`config.py`）。
- `schemas/`：Pydantic 请求/响应模型（如需复用/对外暴露的结构优先放这里）。
- `langchain/`：LLM 集成封装；`scripts/help/`：本地 CLI 辅助脚本（如 `run-cli.py`）。
- 依赖锁在 `uv.lock`；配置示例在 `.env.template`，真实配置使用 `.env`。
- 新增路由文件放在 `routers/`，并在 `main.py` 中注册；新增模型放在 `schemas/` 以便复用。

## 构建、测试与开发命令

- `uv sync`：安装/同步依赖（Python 3.12+）。
- `uv tool install .`：本地安装 CLI（命令为 `ele-autopilot`）。
- `uv run main.py serve --reload`：开发模式启动服务。
- `uv run main.py serve -p 9000`：指定端口启动服务。
- `uv run uvicorn main:app --reload`：直接用 Uvicorn 启动。
- `ele-autopilot serve -p 9000`：安装工具后启动服务。
- `uv run main.py --help`、`uv run main.py serve --help` 或 `ele-autopilot --help`：查看 CLI 帮助。

## 运行与调试提示

- 默认监听 `0.0.0.0:8000`，本地调试可用 `ele-autopilot serve -H 127.0.0.1`。
- CLI 辅助脚本示例：`uv run scripts/help/run-cli.py --path scripts/help/task1.txt`。
- 如需无头模式执行任务，附加 `--headless`；可用 `--max-steps` 控制步数上限。

## API 响应规范

- 成功响应由中间件统一包装为：`{"code": 0, "message": "success", "data": ...}`。
- 异常响应的 `code` 通常等于 HTTP status（如 400/404/422/500）。

## browser-use 集成注意

- 依赖版本固定为 `browser-use==0.11.3`（见 `pyproject.toml`）。
- 常见 action 名称：`navigate`、`search`、`click`、`input`、`scroll`、`done` 等；不要使用 `click_element` / `input_text` 这类名字。
- 关键类型：`Agent`、`Browser`、`AgentHistoryList`（可用 `final_result()`、`is_done()`、`model_actions()` 等做结果提取/调试）。

## 编码风格与命名约定

- 代码遵循现有 Python 风格：4 空格缩进，分组导入（标准库/第三方/本地）。
- 命名：包与模块使用 `snake_case`，类用 `PascalCase`，函数/变量用 `snake_case`。
- 路由逻辑保持轻量，业务逻辑优先放在 `autopilot/`，数据结构放在 `schemas/`。

## 测试指南

- 无需测试

## 提交与 PR 指南

- 提交信息沿用历史风格：`<type>: <summary>`，如 `feat: add autopilot feature`。
- PR 说明包含：变更概述、运行方式/测试结果、配置变更（新增环境变量等）、API 变更示例。
- 依赖变更请同步更新 `uv.lock`，并在说明里标注。
- 若修改 CLI 或 API 文档，请同步更新 `README.md` 的示例与说明。

## 配置与安全

- `.env` 已被 `.gitignore` 忽略，勿提交密钥；参考 `.env.template` 配置 LLM 与 Chrome 参数。
- LLM 必需配置：`ELE_LLM_AUTOPILOT_MODEL`、`ELE_LLM_API_KEY`、`ELE_LLM_BASE_URL`。
- Chrome 可选配置：`CHROME_EXECUTABLE_PATH`、`CHROME_USER_DATA_DIR`（支持 `~` 展开）、`CHROME_PROFILE_DIRECTORY`。
- 如修改默认端口/主机，确保在说明中标明启动命令示例。
