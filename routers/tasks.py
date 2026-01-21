from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from enum import Enum

router = APIRouter(prefix="/tasks", tags=["tasks"])


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Task(BaseModel):
    id: int | None = None
    title: str
    description: str | None = None
    status: TaskStatus = TaskStatus.PENDING


# 模拟数据库
_tasks_db: dict[int, Task] = {}
_task_id_counter = 1


@router.get("/")
async def list_tasks(status: TaskStatus | None = None):
    """获取任务列表，可按状态筛选"""
    tasks = list(_tasks_db.values())
    if status:
        tasks = [t for t in tasks if t.status == status]
    return tasks


@router.get("/{task_id}")
async def get_task(task_id: int):
    """获取单个任务详情"""
    if task_id not in _tasks_db:
        raise HTTPException(status_code=404, detail="Task not found")
    return _tasks_db[task_id]


@router.post("/")
async def create_task(task: Task):
    """创建新任务"""
    global _task_id_counter
    task.id = _task_id_counter
    _tasks_db[_task_id_counter] = task
    _task_id_counter += 1
    return task


@router.patch("/{task_id}/status")
async def update_task_status(task_id: int, status: TaskStatus):
    """更新任务状态"""
    if task_id not in _tasks_db:
        raise HTTPException(status_code=404, detail="Task not found")
    _tasks_db[task_id].status = status
    return _tasks_db[task_id]


@router.delete("/{task_id}")
async def delete_task(task_id: int):
    """删除任务"""
    if task_id not in _tasks_db:
        raise HTTPException(status_code=404, detail="Task not found")
    del _tasks_db[task_id]
    return {"message": "Task deleted"}
