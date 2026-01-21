import json
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse
from fastapi.responses import JSONResponse


class ResponseWrapperMiddleware(BaseHTTPMiddleware):
    """统一响应包装中间件

    将所有 API 响应包装成统一格式:
    {
        "code": 0,
        "message": "success",
        "data": <原始响应数据>
    }
    """

    # 不需要包装的路径前缀（如 OpenAPI 文档）
    EXCLUDE_PATHS = ["/docs", "/redoc", "/openapi.json"]

    async def dispatch(self, request: Request, call_next) -> Response:
        # 跳过不需要包装的路径
        if any(request.url.path.startswith(path) for path in self.EXCLUDE_PATHS):
            return await call_next(request)

        response = await call_next(request)

        # 只处理 JSON 响应
        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            return response

        # 处理 StreamingResponse
        if isinstance(response, StreamingResponse):
            body_parts = []
            async for chunk in response.body_iterator:
                body_parts.append(chunk)
            body = b"".join(body_parts)
        else:
            body = b""
            async for chunk in response.body_iterator:
                body += chunk

        # 解析原始响应
        try:
            original_data = json.loads(body.decode())
        except (json.JSONDecodeError, UnicodeDecodeError):
            return response

        # 如果响应已经是统一格式，直接返回
        if self._is_wrapped_response(original_data):
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type="application/json",
            )

        # 包装响应
        wrapped_data = {"code": 0, "message": "success", "data": original_data}

        return JSONResponse(
            content=wrapped_data,
            status_code=response.status_code,
            headers={
                k: v
                for k, v in response.headers.items()
                if k.lower() != "content-length"
            },
        )

    def _is_wrapped_response(self, data: dict) -> bool:
        """检查响应是否已经是统一格式"""
        if not isinstance(data, dict):
            return False
        return (
            "code" in data
            and "message" in data
            and isinstance(data.get("code"), int)
            and isinstance(data.get("message"), str)
        )
