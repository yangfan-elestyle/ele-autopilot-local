import argparse
import asyncio
from pathlib import Path

from autopilot import Job, JobConfig


async def main(tasks: list[str], max_steps: int = 120, headless: bool = False):
    config = JobConfig(max_steps=max_steps, headless=headless)
    job = Job.create(tasks=tasks, config=config)
    await job.run()

    # 打印执行结果
    print(f"\nJob ID: {job.id}")
    print(f"Job 状态: {job.status}")
    for task_result in job.tasks:
        print(f"\n{'=' * 50}")
        print(f"任务: {task_result.task[:50]}...")
        print(f"状态: {task_result.status}")
        if task_result.error:
            print(f"错误: {task_result.error}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Autopilot CLI - 执行浏览器自动化任务")
    parser.add_argument(
        "--path", required=True, nargs="+", help="Path(s) to task file(s)"
    )
    parser.add_argument("--max-steps", type=int, default=120, help="Max steps per task")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    args = parser.parse_args()

    # 支持多个任务文件
    tasks = []
    for path in args.path:
        task_content = Path(path).read_text(encoding="utf-8")
        tasks.append(task_content)

    asyncio.run(main(tasks, args.max_steps, args.headless))
