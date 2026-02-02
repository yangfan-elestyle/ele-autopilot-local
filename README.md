# ele-autopilot-local

Local autopilot service for browser automation.

## 命令 TLDR

```bash
release: uv tool install git+xxx && ele-autopilot serve
dev: uv run ele-autopilot serve --reload
```

## 安装

```bash
# 从 GitHub 安装
uv tool install git+https://github.com/yourname/ele-autopilot-local

# 或本地安装（开发用）
git clone https://github.com/yourname/ele-autopilot-local
cd ele-autopilot-local
uv tool install .
```

## 使用

```bash
# 查看帮助
ele-autopilot --help
ele-autopilot serve --help

# 启动服务
ele-autopilot serve                    # 默认 0.0.0.0:8000
ele-autopilot serve -p 9000            # 指定端口
ele-autopilot serve -H 127.0.0.1       # 只监听本地
ele-autopilot serve --reload           # 开发模式（自动重载）
```

## 开发

```bash
# 克隆项目
git clone https://github.com/yourname/ele-autopilot-local
cd ele-autopilot-local

# 安装依赖
uv sync

# 查看帮助
uv run ele-autopilot --help
uv run ele-autopilot serve --help

# 启动服务（推荐）
uv run ele-autopilot serve
uv run ele-autopilot serve -p 9000 --reload

# 或直接运行 uvicorn
uv run uvicorn main:app --reload
```

## API 响应格式

所有 API 统一返回以下格式：

```json
{"code": 0, "message": "success", "data": ...}
```

| code | 说明         |
| ---- | ------------ |
| 0    | 成功         |
| 404  | 资源不存在   |
| 422  | 参数校验失败 |
| 500  | 服务器错误   |
