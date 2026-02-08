from typing import Union

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from autopilot import get_job_service, TaskStatus, JobConfig
from autopilot.job import TaskInput

router = APIRouter(prefix="/autopilot", tags=["autopilot"])


class AutopilotRunRequest(JobConfig):
    """
    启动 autopilot Job 的请求体

    支持两种模式：
    1. Local 独立模式：tasks 为字符串列表
    2. Server 集成模式：tasks 为 TaskInput 列表（含 id 和 text）

    Server 集成模式时，job_id 和 callback_url 必填。
    """

    job_id: str | None = None  # Server 传入则使用，否则 Local 自己生成
    tasks: list[str] | list[TaskInput]  # 支持字符串列表或 TaskInput 列表
    callback_url: str | None = None  # 有则回调 Server，无则不回调


@router.post("/run")
async def run_autopilot(request: AutopilotRunRequest):
    """
    启动一个 autopilot Job（后台异步执行，支持多个任务）

    立即返回 job_id；可用 /autopilot/status/{job_id} 或 /autopilot/jobs/{job_id} 查询状态。

    支持两种任务格式：
    - 字符串列表：["任务1", "任务2"] （Local 独立模式）
    - TaskInput 列表：[{"id": "task-id", "text": "任务1"}] （Server 集成模式）
    """
    service = get_job_service()
    try:
        # 解析 tasks：支持字符串列表或 TaskInput 列表
        tasks: list[str] | list[TaskInput] = []
        for task in request.tasks:
            if isinstance(task, str):
                tasks.append(task)
            elif isinstance(task, dict):
                # 从字典构造 TaskInput
                tasks.append(
                    TaskInput(id=task.get("id", ""), text=task.get("text", ""))
                )
            elif isinstance(task, TaskInput):
                tasks.append(task)
            else:
                raise ValueError(f"Invalid task format: {task}")

        config = JobConfig.model_validate(
            request.model_dump(exclude={"tasks", "job_id", "callback_url"})
        )
        job = await service.create_job(
            tasks=tasks,
            config=config,
            job_id=request.job_id,
            callback_url=request.callback_url,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"job_id": job.id, "status": job.status}


@router.get("/status/{job_id}")
async def get_autopilot_status(job_id: str):
    """获取指定 Job 的当前快照（包含状态与任务列表）"""
    service = get_job_service()
    try:
        return await service.get_job(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found")


@router.get("/jobs/{job_id}")
async def get_autopilot_job(job_id: str):
    """获取单个 Job（等价于 /status/{job_id}，仅用于更贴近 REST 命名）"""
    return await get_autopilot_status(job_id)


@router.get("/jobs/{job_id}/tasks")
async def list_autopilot_job_tasks(job_id: str):
    """列出指定 Job 的任务列表（运行中也可查询）"""
    service = get_job_service()
    try:
        return await service.get_job_tasks(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found")


@router.get("/jobs")
async def list_autopilot_jobs(status: TaskStatus | None = None):
    """列出所有 Job（可按状态筛选，默认按创建时间倒序）"""
    service = get_job_service()
    return await service.list_jobs(status=status)


class StopRequest(BaseModel):
    """停止 Job 或指定 task 的请求体"""

    task_id: str | None = None  # 有值则停止指定 task，无值则停止整个 Job


@router.post("/jobs/{job_id}/stop")
async def stop_job(job_id: str, request: StopRequest | None = None):
    """
    停止 Job 或指定 task

    行为：
    - 不传 task_id（或空 body）：停止整个 Job，当前 task 失败，剩余 task 全部跳过
    - 传 task_id：只停止当前正在 RUNNING 且 task_id 匹配的 task，后续 task 继续执行
      - 若该 task 不在 RUNNING 状态，返回 400 错误
    """
    service = get_job_service()
    task_id = request.task_id if request else None
    try:
        result = await service.stop(job_id, task_id=task_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found")
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.delete("/jobs/{job_id}")
async def delete_autopilot_job(job_id: str):
    """删除一个 Job 记录（运行中的 Job 不允许删除）"""
    service = get_job_service()
    try:
        await service.delete_job(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"message": "Job deleted"}
