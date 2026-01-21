from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
import uvicorn

from routers import users, tasks, system
from middleware import (
    ResponseWrapperMiddleware,
    http_exception_handler,
    validation_exception_handler,
    pydantic_exception_handler,
    generic_exception_handler,
)

app = FastAPI(
    title="ele-autopilot-local",
    description="Local autopilot service",
    version="0.1.0",
)

# 注册响应包装中间件
app.add_middleware(ResponseWrapperMiddleware)

# 注册异常处理器
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(ValidationError, pydantic_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# 注册路由
app.include_router(users.router)
app.include_router(tasks.router)
app.include_router(system.router)


@app.get("/")
async def root():
    return {"message": "Hello from ele-autopilot-local!"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
