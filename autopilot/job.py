"""
Job 模型：持有 Job 数据并负责串行执行多个任务

职责：
- 定义可序列化的 Job 数据结构
- 负责编排 Job 内多个 Task 的执行与状态汇总
- 支持回调 Server 更新状态（Server 集成模式）
"""

import logging
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

from .callback import CallbackClient
from .config import JobConfig
from .task import TaskResult, TaskRunner, TaskStatus
from .task_action import TaskActionHandler


class TaskInput(BaseModel):
    """单个任务输入（Server 集成时使用）"""

    id: str  # 来源的叶子节点 TaskRow id
    text: str  # 任务文本


class Job(BaseModel):
    """
    Job 实体：包含任务列表、执行配置与聚合状态
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    tasks: list[TaskResult] = Field(default_factory=list)
    config: JobConfig
    callback_url: str | None = None  # Server 回调 URL（有则回调，无则不回调）

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @classmethod
    def create(
        cls,
        tasks: list[str] | list[TaskInput],
        config: JobConfig,
        job_id: str | None = None,
        callback_url: str | None = None,
    ) -> "Job":
        """
        从任务描述列表构造 Job（初始化为 PENDING）

        Args:
            tasks: 任务列表，可以是字符串列表（Local 独立模式）或 TaskInput 列表（Server 集成模式）
            config: 执行配置
            job_id: Server 传入的 job_id（可选，不传则自己生成）
            callback_url: Server 回调 URL（可选，有则回调）
        """
        task_results = []
        for idx, task in enumerate(tasks):
            if isinstance(task, TaskInput):
                task_results.append(
                    TaskResult(
                        task=task.text,
                        task_id=task.id,
                        task_index=idx,
                        status=TaskStatus.PENDING,
                    )
                )
            else:
                # 兼容原有的字符串列表模式
                task_results.append(
                    TaskResult(
                        task=task,
                        task_id="",
                        task_index=idx,
                        status=TaskStatus.PENDING,
                    )
                )

        return cls(
            id=job_id or str(uuid.uuid4()),
            tasks=task_results,
            config=config,
            callback_url=callback_url,
        )

    def _update_status(self):
        """按任务状态聚合更新 Job 状态（RUNNING > COMPLETED > FAILED > PENDING）"""
        if not self.tasks:
            self.status = TaskStatus.PENDING
            return

        if any(t.status == TaskStatus.RUNNING for t in self.tasks):
            self.status = TaskStatus.RUNNING
        elif all(t.status == TaskStatus.COMPLETED for t in self.tasks):
            self.status = TaskStatus.COMPLETED
        elif any(t.status == TaskStatus.FAILED for t in self.tasks):
            self.status = TaskStatus.FAILED
        else:
            self.status = TaskStatus.PENDING

    async def run(self) -> None:
        """
        执行 Job 内所有任务（顺序执行），支持回调 Server 更新状态

        说明：
        - 每个任务由 TaskRunner 执行并返回 TaskResult
        - 如发生未捕获异常（包含初始化阶段），会将未完成任务统一标记为 FAILED
        - 如有 callback_url，每个 task 完成后会回调 Server
        """
        callback = CallbackClient(self.callback_url)
        self.started_at = datetime.now()
        self.status = TaskStatus.RUNNING

        logger.info(f"Job {self.id} started with config: {self.config.model_dump()}")

        try:
            runner = TaskRunner(config=self.config)
            for idx, task_result in enumerate(self.tasks):
                # 记录开始时间，便于外部轮询展示进度
                task_result.status = TaskStatus.RUNNING
                task_result.started_at = datetime.now()
                task_result.task_index = idx

                # 上报 task 开始到 Server（此时 result 为 None）
                await callback.report_task_update(
                    task_index=idx,
                    task_id=task_result.task_id,
                    status="running",
                    result=None,
                    started_at=task_result.started_at,
                    completed_at=task_result.started_at,  # 临时值
                )

                cloud_payload: dict[str, Any] | None = None
                try:
                    # 执行任务（TaskRunner 返回的是简单 TaskResult）
                    result = await runner.run(task_result.task)

                    # 复制执行结果到当前 task_result（保留 task_id 和 task_index）
                    task_result.status = result.status
                    task_result.result = result.result
                    task_result.error = result.error
                    task_result.completed_at = result.completed_at

                    # 如果有 agent 历史，提取完整执行结果用于回调
                    if hasattr(result, "_agent_history") and result._agent_history:
                        handler = TaskActionHandler(result._agent_history)
                        cloud_payload = handler.to_cloud_payload(
                            config=self.config.model_dump()
                        )

                except Exception as e:
                    task_result.status = TaskStatus.FAILED
                    task_result.error = str(e)
                    task_result.completed_at = datetime.now()

                # 上报 task 完成到 Server（携带完整执行结果）
                await callback.report_task_update(
                    task_index=idx,
                    task_id=task_result.task_id,
                    status=task_result.status.value,
                    result=cloud_payload,
                    error=task_result.error,
                    started_at=task_result.started_at,
                    completed_at=task_result.completed_at,
                )

        except Exception as e:
            # 兜底异常：将 Job 及未完成任务统一标记为失败，避免出现"永远 RUNNING"
            completed_at = datetime.now()
            error = str(e)
            for t in self.tasks:
                if t.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
                    t.status = TaskStatus.FAILED
                    t.completed_at = completed_at
                    t.error = error
        finally:
            self.completed_at = datetime.now()
            self._update_status()

            # 上报 Job 完成到 Server
            await callback.report_job_complete(
                status=self.status.value,
                error=None,  # Job 级别的错误通过 tasks 体现
                completed_at=self.completed_at,
            )

            await callback.close()
