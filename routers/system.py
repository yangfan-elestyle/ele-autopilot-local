from fastapi import APIRouter
from datetime import datetime

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health")
async def health_check():
    """健康检查接口"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@router.get("/version")
async def get_version():
    """获取系统版本信息"""
    return {
        "name": "ele-autopilot-local",
        "version": "0.1.0",
        "api_version": "v1",
    }


@router.get("/config")
async def get_config():
    """获取系统配置（示例）"""
    return {
        "max_concurrent_tasks": 10,
        "timeout_seconds": 300,
        "features": {
            "auto_retry": True,
            "logging_enabled": True,
        },
    }
