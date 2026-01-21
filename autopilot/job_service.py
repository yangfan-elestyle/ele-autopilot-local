"""
Job 服务层：负责 Job 的生命周期与对外查询

职责：
- Job 的创建/查询/列表/删除
- 异步调度 Job 执行
- 维护内存态的 Job 存储（当前为单进程）
"""

import asyncio
import logging

from .config import JobConfig
from .job import Job
from .task import TaskResult, TaskStatus

logger = logging.getLogger(__name__)


class JobService:
    """
    Job 生命周期与状态管理

    说明：
    - 当前实现为单进程内存存储
    - 如需多实例/重启不丢，后续可替换存储层为 Redis/DB
    """

    def __init__(self):
        self._jobs: dict[str, Job] = {}
        self._lock = asyncio.Lock()

    async def create_job(self, tasks: list[str], config: JobConfig) -> Job:
        """
        创建并启动 Job

        Args:
            tasks: 任务描述列表
            config: 执行配置

        Returns:
            创建的 Job 实例
        """
        if not tasks:
            raise ValueError("tasks cannot be empty")

        job = Job.create(tasks=tasks, config=config)

        async with self._lock:
            self._jobs[job.id] = job

        asyncio.create_task(self._run_job(job.id))

        return job

    async def get_job(self, job_id: str) -> Job:
        """获取指定 Job（不存在则抛 KeyError）"""
        async with self._lock:
            job = self._jobs.get(job_id)
        if not job:
            raise KeyError("Job not found")
        return job

    async def list_jobs(self, status: TaskStatus | None = None) -> list[Job]:
        """
        列出 Jobs

        Args:
            status: 按状态过滤

        Returns:
            Job 列表（按创建时间倒序）
        """
        async with self._lock:
            jobs = list(self._jobs.values())
        if status:
            jobs = [j for j in jobs if j.status == status]
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        return jobs

    async def get_job_tasks(self, job_id: str) -> list[TaskResult]:
        """获取指定 Job 的任务列表"""
        job = await self.get_job(job_id)
        return job.tasks

    async def delete_job(self, job_id: str) -> None:
        """
        删除 Job

        注意：运行中的 Job 不允许删除（避免状态混乱）
        """
        job = await self.get_job(job_id)
        if job.status == TaskStatus.RUNNING:
            raise ValueError("Cannot delete a running job")
        async with self._lock:
            self._jobs.pop(job_id, None)

    async def _run_job(self, job_id: str) -> None:
        """执行 Job（内部调度入口：捕获异常并落到 Job 状态上）"""
        try:
            job = await self.get_job(job_id)
        except KeyError:
            return

        try:
            await job.run()
        except Exception as e:
            # Job.run 已做兜底并尽量不抛异常；这里仅作为最后保险，避免 background task 泄漏异常。
            logger.exception("Unexpected error while running job_id=%s: %s", job_id, e)


# 模块级单例：在 FastAPI 进程内复用同一个 JobService
_job_service_singleton: JobService | None = None


def get_job_service() -> JobService:
    """获取 JobService 单例"""
    global _job_service_singleton
    if _job_service_singleton is None:
        _job_service_singleton = JobService()
    return _job_service_singleton
