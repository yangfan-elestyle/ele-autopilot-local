from fastapi import APIRouter, HTTPException

from autopilot import get_job_service, TaskStatus, JobConfig

router = APIRouter(prefix="/autopilot", tags=["autopilot"])


class AutopilotRunRequest(JobConfig):
    """启动 autopilot Job 的请求体（任务列表 + 执行配置）"""

    tasks: list[str]


@router.post("/run")
async def run_autopilot(request: AutopilotRunRequest):
    """
    启动一个 autopilot Job（后台异步执行，支持多个任务）

    立即返回 job_id；可用 /autopilot/status/{job_id} 或 /autopilot/jobs/{job_id} 查询状态。
    """
    service = get_job_service()
    try:
        config = JobConfig.model_validate(request.model_dump(exclude={"tasks"}))
        job = await service.create_job(tasks=request.tasks, config=config)
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
