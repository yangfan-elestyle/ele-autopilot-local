"""
任务执行单元：负责把「自然语言任务」交给浏览器自动化 Agent 执行

职责：
- 定义任务状态与任务执行记录（含时间戳/结果/错误）
- 初始化 LLM / Browser 并执行单个任务
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from browser_use import Agent, Browser
from browser_use.llm import ChatGoogle

from utils.chrome_profile import resolve_chrome_user_data_dir

from .config import JobConfig

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """任务生命周期状态（用于 Job 聚合与对外查询）"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TaskResult:
    """单个任务的执行记录（结果与错误二选一）"""

    task: str
    task_id: str = ""  # 来源的叶子节点 TaskRow id（Server 集成时使用）
    task_index: int = 0  # 任务索引（在 flat 数组中的位置）
    status: TaskStatus = TaskStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: Any = None
    error: str | None = None


class TaskRunner:
    """单个任务执行器：为每次执行创建 Agent，并负责资源清理"""

    def __init__(self, config: JobConfig):
        self.config = config
        self._llm = None

    def _init_llm(self):
        """初始化 LLM，model 通过 config 传入，api_key 通过环境变量配置"""
        if self._llm is None:
            self._llm = ChatGoogle(
                model=self.config.gemini_model,
                api_key=os.getenv("ELE_LLM_API_KEY"),
                temperature=0.0,
                max_output_tokens=65536,
            )
        return self._llm

    async def _init_browser(self) -> Browser:
        """初始化浏览器实例（支持通过环境变量指定 Chrome 配置）"""
        chrome_executable_path = os.getenv("CHROME_EXECUTABLE_PATH")
        chrome_user_data_dir = os.getenv("CHROME_USER_DATA_DIR")
        chrome_profile_directory = os.getenv("CHROME_PROFILE_DIRECTORY")
        profile_directory = chrome_profile_directory or "Default"
        resolved_user_data_dir = resolve_chrome_user_data_dir(
            chrome_executable_path=chrome_executable_path,
            chrome_user_data_dir=chrome_user_data_dir,
            profile_directory=profile_directory,
            log=logger,
        )

        return Browser(
            executable_path=chrome_executable_path,
            user_data_dir=resolved_user_data_dir,
            profile_directory=profile_directory,
            headless=self.config.headless,
            keep_alive=False,
        )

    async def _cleanup(self, browser: Browser | None):
        """清理浏览器资源"""
        if browser is None:
            return
        try:
            await browser.stop()
        except Exception:
            pass

    def _build_agent_kwargs(self) -> dict:
        """构建 Agent 初始化参数：只包含 config 中有值的参数"""
        # Agent 参数与 config 字段的映射
        param_mapping = {
            "use_vision": "use_vision",
            "max_failures": "max_failures",
            "max_actions_per_step": "max_actions_per_step",
            "use_thinking": "use_thinking",
            "flash_mode": "flash_mode",
            "llm_timeout": "llm_timeout",
            "step_timeout": "step_timeout",
        }
        # 字符串参数需要额外判断空字符串（空字符串覆盖系统提示词会导致 Agent 失去基础指令）
        str_param_mapping = {
            "override_system_message": "override_system_message",
            "extend_system_message": "extend_system_message",
        }

        kwargs = {}
        for agent_param, config_field in param_mapping.items():
            value = getattr(self.config, config_field, None)
            if value is not None:
                kwargs[agent_param] = value

        for agent_param, config_field in str_param_mapping.items():
            value = getattr(self.config, config_field, None)
            if value:  # 同时排除 None 和空字符串
                kwargs[agent_param] = value

        return kwargs

    async def run(self, task: str) -> TaskResult:
        """执行单个任务并返回可序列化的执行记录"""
        task_result = TaskResult(task=task)
        task_result.status = TaskStatus.RUNNING
        task_result.started_at = datetime.now()

        browser: Browser | None = None
        try:
            llm = self._init_llm()
            browser = await self._init_browser()

            # 构建 Agent 参数：只传递 config 中有值的参数，其余使用 Agent 默认值
            agent_kwargs = self._build_agent_kwargs()
            logger.info(f"Creating Agent with task={task!r}, agent_kwargs={agent_kwargs}")
            agent = Agent(task=task, llm=llm, browser=browser, **agent_kwargs)

            result = await agent.run(max_steps=self.config.max_steps)
            task_result.result = str(result) if result else None
            task_result.status = TaskStatus.COMPLETED

            # 保存 agent history 用于生成云端 payload
            # result 是 AgentHistoryList 类型
            task_result._agent_history = result  # type: ignore[attr-defined]

        except Exception as e:
            task_result.status = TaskStatus.FAILED
            task_result.error = str(e)
        finally:
            await self._cleanup(browser)

        task_result.completed_at = datetime.now()
        return task_result
