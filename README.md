# ele-autopilot-local

Local autopilot service.

## 启动

```bash
uv run uvicorn main:app --reload
```

## API 响应格式

所有 API 统一返回以下格式：

```json
{"code": 0, "message": "success", "data": ...}
```

| code | 说明 |
|------|------|
| 0 | 成功 |
| 404 | 资源不存在 |
| 422 | 参数校验失败 |
| 500 | 服务器错误 |
