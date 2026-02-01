import argparse
import asyncio
import sys
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    current = start
    while current != current.parent:
        if (current / "pyproject.toml").exists() or (current / ".git").exists():
            return current
        current = current.parent
    return start


_REPO_ROOT = _find_repo_root(Path(__file__).resolve())
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from autopilot import Job, JobConfig


async def main(tasks: list[str], headless: bool = False):
    config = JobConfig(headless=headless)
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
        "--path",
        nargs="+",
        help="指定 task 文件路径列表",
    )
    parser.add_argument(
        "--directory",
        help="指定包含 task 文件的目录，读取目录下所有 txt 文件",
    )
    parser.add_argument(
        "--headless", action="store_true", help="Run browser in headless mode"
    )
    args = parser.parse_args()

    # 必须指定 --path 或 --directory
    if not args.path and not args.directory:
        parser.error("必须指定 --path 或 --directory 之一")

    # 支持多个任务文件
    tasks = []
    if args.path:
        task_paths = [Path(path) for path in args.path]
    else:
        task_dir = Path(args.directory)
        if not task_dir.is_dir():
            raise NotADirectoryError(f"指定的目录不存在：{task_dir}")
        task_paths = sorted(task_dir.glob("*.txt"), key=lambda p: p.name)
        if not task_paths:
            raise FileNotFoundError(f"未找到任务文件：{task_dir}/*.txt")

    for path in task_paths:
        task_content = path.read_text(encoding="utf-8")
        tasks.append(task_content)

    asyncio.run(main(tasks, args.headless))
