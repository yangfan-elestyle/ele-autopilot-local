from fastapi import APIRouter
from datetime import datetime, timezone
import os
import time

from app_meta import project_name, project_version

router = APIRouter(prefix="/system", tags=["system"])

_STARTED_AT = datetime.now(timezone.utc)
_STARTED_MONO = time.monotonic()


@router.get("/health")
async def health_check():
    """健康检查接口"""
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/connect")
async def connect_check():
    """连接检测接口：让外部服务确认本服务已启动"""
    uptime_seconds = int(time.monotonic() - _STARTED_MONO)
    return {
        "status": "running",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "started_at": _STARTED_AT.isoformat(),
        "uptime_seconds": max(uptime_seconds, 0),
        "service": {
            "name": project_name(),
            "version": project_version(),
            "pid": os.getpid(),
        },
    }


@router.get("/version")
async def get_version():
    """获取系统版本信息"""
    return {
        "name": project_name(),
        "version": project_version(),
        "api_version": "v1",
    }
