from typing import Any, Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """统一 API 响应格式"""

    code: int = 0
    message: str = "success"
    data: T | None = None


def success_response(data: Any = None, message: str = "success") -> dict:
    """构建成功响应"""
    return {"code": 0, "message": message, "data": data}


def error_response(code: int, message: str, data: Any = None) -> dict:
    """构建错误响应"""
    return {"code": code, "message": message, "data": data}
