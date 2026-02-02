"""
回调客户端：Local 主动回调 Server 更新状态

职责：
- 上报单个 task 状态（包含完整执行结果）
- 上报 Job 完成状态
"""

import logging
from datetime import datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class CallbackClient:
    """回调客户端（Local 主动回调 Server）"""

    def __init__(self, callback_url: str | None):
        """
        初始化回调客户端

        Args:
            callback_url: Server 的回调基础 URL，格式：http://server-host:port/api/jobs/{job_id}/callback
                         如果为 None，则不执行回调（Local 独立运行模式）
        """
        self.callback_url = callback_url
        self.client = httpx.AsyncClient(timeout=30.0) if callback_url else None

    async def report_task_update(
        self,
        task_index: int,
        task_id: str,
        status: str,
        result: dict[str, Any] | None = None,
        error: str | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> bool:
        """
        上报单个 task 状态到 Server

        重要：result 包含完整的执行结果（参考 task_action_out.template.json），
        数据量可能很大，但需要全量上传，后续在 UI 中展示。

        Args:
            task_index: 任务在 flat 数组中的索引
            task_id: 来源的叶子节点 TaskRow id
            status: 任务状态（running / completed / failed）
            result: 完整执行结果（TaskActionResult）
            error: 错误信息（status=failed 时有值）
            started_at: 开始时间
            completed_at: 完成时间

        Returns:
            回调是否成功
        """
        if not self.client:
            return True  # 无回调 URL，视为成功

        payload = {
            "task_index": task_index,
            "task_id": task_id,
            "status": status,
            "result": result,
            "error": error,
            "started_at": started_at.isoformat() if started_at else None,
            "completed_at": completed_at.isoformat() if completed_at else None,
        }

        try:
            url = f"{self.callback_url}/task"
            response = await self.client.post(url, json=payload)
            if response.status_code != 200:
                logger.warning(
                    "Task callback returned non-200 status: %d, body: %s",
                    response.status_code,
                    response.text[:500],
                )
                return False
            return True
        except Exception as e:
            # 回调失败不影响任务执行，仅记录日志
            logger.warning("Task callback failed: %s", e)
            return False

    async def report_job_complete(
        self,
        status: str,
        error: str | None = None,
        completed_at: datetime | None = None,
    ) -> bool:
        """
        上报 Job 完成到 Server

        Args:
            status: Job 最终状态（completed / failed）
            error: 错误信息（status=failed 时有值）
            completed_at: 完成时间

        Returns:
            回调是否成功
        """
        if not self.client:
            return True  # 无回调 URL，视为成功

        payload = {
            "status": status,
            "error": error,
            "completed_at": completed_at.isoformat() if completed_at else None,
        }

        try:
            url = f"{self.callback_url}/complete"
            response = await self.client.post(url, json=payload)
            if response.status_code != 200:
                logger.warning(
                    "Job complete callback returned non-200 status: %d, body: %s",
                    response.status_code,
                    response.text[:500],
                )
                return False
            return True
        except Exception as e:
            logger.warning("Job complete callback failed: %s", e)
            return False

    async def close(self) -> None:
        """关闭 HTTP 客户端"""
        if self.client:
            await self.client.aclose()
            self.client = None
