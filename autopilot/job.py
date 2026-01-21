"""
Job 模型：持有 Job 数据并负责串行执行多个任务

职责：
- 定义可序列化的 Job 数据结构
- 负责编排 Job 内多个 Task 的执行与状态汇总
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .config import JobConfig
from .task import TaskResult, TaskRunner, TaskStatus


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

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @classmethod
    def create(cls, tasks: list[str], config: JobConfig) -> "Job":
        """从任务描述列表构造 Job（初始化为 PENDING）"""
        task_results = [
            TaskResult(task=task, status=TaskStatus.PENDING) for task in tasks
        ]
        return cls(
            tasks=task_results,
            config=config,
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
        执行 Job 内所有任务（顺序执行）

        说明：
        - 每个任务由 TaskRunner 执行并返回 TaskResult
        - 如发生未捕获异常（包含初始化阶段），会将未完成任务统一标记为 FAILED
        """
        self.started_at = datetime.now()
        self.status = TaskStatus.RUNNING

        try:
            runner = TaskRunner(config=self.config)
            for idx, task_result in enumerate(self.tasks):
                # 记录开始时间，便于外部轮询展示进度
                task_result.status = TaskStatus.RUNNING
                task_result.started_at = datetime.now()

                # 执行并得到新的 TaskResult（包含结果/错误/结束时间）
                result = await runner.run(task_result.task)

                # 用执行结果替换占位记录（保持列表顺序不变）
                self.tasks[idx] = result

        except Exception as e:
            # 兜底异常：将 Job 及未完成任务统一标记为失败，避免出现“永远 RUNNING”
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
