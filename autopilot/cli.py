"""CLI 入口点和 FastAPI 应用定义。

此模块用于 `uv tool install` 或 `uvx` 安装后的命令行入口。
"""

import argparse

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
import uvicorn

from autopilot.app_meta import project_name, project_version
from routers import system, autopilot
from middleware import (
    ResponseWrapperMiddleware,
    http_exception_handler,
    validation_exception_handler,
    pydantic_exception_handler,
    generic_exception_handler,
)


app = FastAPI(
    title=project_name(),
    description="Local autopilot service",
    version=project_version(),
)

# 注册 CORS 中间件（允许前端跨域访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源（本地开发环境）
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册响应包装中间件
app.add_middleware(ResponseWrapperMiddleware)

# 注册异常处理器
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(ValidationError, pydantic_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# 注册路由
app.include_router(system.router)
app.include_router(autopilot.router)


@app.get("/")
async def root():
    return {"message": "Hello from ele-autopilot-local!"}


def cli():
    """命令行入口 - 供 uv tool install 后使用"""
    parser = argparse.ArgumentParser(
        description="Ele Autopilot Local - Browser automation service"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # serve 命令
    serve_parser = subparsers.add_parser("serve", help="Start the HTTP server")
    serve_parser.add_argument(
        "--port", "-p", type=int, default=8000, help="Port to listen on (default: 8000)"
    )
    serve_parser.add_argument(
        "--host", "-H", default="0.0.0.0", help="Host to bind (default: 0.0.0.0)"
    )
    serve_parser.add_argument(
        "--reload", "-r", action="store_true", help="Enable auto-reload for development"
    )

    args = parser.parse_args()

    if args.command == "serve":
        uvicorn.run(
            "autopilot.cli:app", host=args.host, port=args.port, reload=args.reload
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    cli()
