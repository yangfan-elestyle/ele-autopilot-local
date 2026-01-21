"""
Job 执行配置：用于控制 autopilot 运行参数（如步数上限、是否无头）
"""

from pydantic import BaseModel


class JobConfig(BaseModel):
    """Job 执行配置（会被 Job/TaskRunner 读取）"""

    max_steps: int = 120
    headless: bool = False
