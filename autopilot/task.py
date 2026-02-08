"""
任务执行单元：负责把「自然语言任务」交给浏览器自动化 Agent 执行

职责：
- 定义任务状态与任务执行记录（含时间戳/结果/错误）
- 初始化 LLM / Browser 并执行单个任务
"""

import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

import psutil
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


@dataclass
class _ShouldStopState:
    """should_stop 回调的内部状态"""

    browser_pid: int | None = None
    had_focus: bool = False
    focus_lost_since: float | None = None


class TaskRunner:
    """单个任务执行器：为每次执行创建 Agent，并负责资源清理"""

    _FOCUS_LOSS_GRACE_SECONDS = 1.5
    _FOCUS_RECOVERY_TIMEOUT_SECONDS = 0.5

    def __init__(self, config: JobConfig):
        self.config = config
        self._llm = None
        self._current_agent: Agent | None = None
        self._browser_closed: bool = False

    @property
    def browser_closed(self) -> bool:
        """浏览器是否被用户关闭"""
        return self._browser_closed

    @staticmethod
    def _get_browser_pid(browser: Browser) -> int | None:
        """从 BrowserSession 获取本地浏览器进程 PID"""
        try:
            watchdog = browser._local_browser_watchdog
            if watchdog and watchdog._subprocess:
                return watchdog._subprocess.pid
        except Exception:
            pass
        return None

    @staticmethod
    def _acquire_browser_pid(browser: Browser, current_pid: int | None) -> int | None:
        """懒加载浏览器 PID（进程启动后才可获取）"""
        if current_pid is not None:
            return current_pid

        pid = TaskRunner._get_browser_pid(browser)
        if pid is not None:
            logger.info(f"Browser process watchdog acquired pid={pid}")
        return pid

    def _mark_browser_closed(self, message: str, *args) -> bool:
        """统一记录浏览器关闭并返回 stop 信号"""
        logger.warning(message, *args)
        self._browser_closed = True
        return True

    def _is_browser_process_closed(self, browser_pid: int | None) -> bool:
        """检查 Chrome 进程是否已退出"""
        if browser_pid is None:
            return False

        try:
            proc = psutil.Process(browser_pid)
            if not proc.is_running() or proc.status() in (
                psutil.STATUS_ZOMBIE,
                psutil.STATUS_DEAD,
            ):
                return self._mark_browser_closed(
                    "Browser process %s is no longer running", browser_pid
                )
        except psutil.NoSuchProcess:
            return self._mark_browser_closed(
                "Browser process %s no longer exists", browser_pid
            )
        except psutil.AccessDenied:
            logger.warning("Access denied checking browser process %s", browser_pid)
        except Exception:
            pass

        return False

    @staticmethod
    async def _try_recover_focus(browser: Browser, timeout_seconds: float) -> bool:
        """尝试通过 browser-use 内置机制恢复 focus"""
        session_manager = getattr(browser, "session_manager", None)
        if session_manager is None:
            return False

        try:
            recovered = await session_manager.ensure_valid_focus(timeout=timeout_seconds)
        except Exception:
            return False

        return bool(recovered and browser.agent_focus_target_id is not None)

    async def _is_focus_lost_persistently(
        self, browser: Browser, state: _ShouldStopState
    ) -> bool:
        """检查 focus 是否持续丢失（包含宽限与恢复）"""
        if browser.agent_focus_target_id is not None:
            state.had_focus = True
            state.focus_lost_since = None
            return False

        if not state.had_focus:
            return False

        now = time.monotonic()
        if state.focus_lost_since is None:
            state.focus_lost_since = now
            return False

        elapsed = now - state.focus_lost_since
        if elapsed < self._FOCUS_LOSS_GRACE_SECONDS:
            return False

        recovered = await TaskRunner._try_recover_focus(
            browser, timeout_seconds=self._FOCUS_RECOVERY_TIMEOUT_SECONDS
        )
        if recovered:
            state.focus_lost_since = None
            return False

        return self._mark_browser_closed(
            "Browser lost agent focus for %.1fs - tab/window may be closed by user",
            elapsed,
        )

    def _make_should_stop_callback(self, browser: Browser):
        """构建 Agent should_stop 回调：检测浏览器是否仍可用

        检测两种场景：
        1. Chrome app 被关闭 → psutil 检测进程消失
        2. Tab/Window 被关闭但 Chrome 还在 → agent_focus_target_id 丢失

        使用闭包延迟获取 PID，因为浏览器进程在 Agent.run() 过程中才实际启动。
        """
        state = _ShouldStopState()

        async def should_stop() -> bool:
            state.browser_pid = TaskRunner._acquire_browser_pid(
                browser, state.browser_pid
            )

            if self._is_browser_process_closed(state.browser_pid):
                return True

            return await self._is_focus_lost_persistently(browser, state)

        return should_stop

    def stop_current_task(self) -> bool:
        """停止当前正在执行的 task。返回 True 表示已发送停止信号。"""
        agent = self._current_agent
        if agent is not None:
            agent.stop()
            return True
        return False

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
        """初始化浏览器实例"""
        chrome_executable_path = (
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        )
        chrome_user_data_dir = "~/Library/Application Support/Google/Chrome"
        profile_directory = "Default"
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
        self._browser_closed = False

        browser: Browser | None = None
        try:
            llm = self._init_llm()
            browser = await self._init_browser()

            # 构建 Agent 参数：只传递 config 中有值的参数，其余使用 Agent 默认值
            agent_kwargs = self._build_agent_kwargs()
            logger.info(
                f"Creating Agent with task={task!r}, agent_kwargs={agent_kwargs}"
            )

            agent = Agent(
                task=task,
                llm=llm,
                browser=browser,
                register_should_stop_callback=self._make_should_stop_callback(browser),
                **agent_kwargs,
            )
            self._current_agent = agent

            result = await agent.run(max_steps=self.config.max_steps)

            # 检查 agent 是否被外部 stop（且未自然完成）
            if agent.state.stopped and not (result and result.is_done()):
                task_result.status = TaskStatus.FAILED
                task_result.error = "Task stopped"
            else:
                task_result.status = TaskStatus.COMPLETED

            task_result.result = str(result) if result else None

            # 保存 agent history 用于生成云端 payload
            # result 是 AgentHistoryList 类型
            task_result._agent_history = result  # type: ignore[attr-defined]

        except Exception as e:
            task_result.status = TaskStatus.FAILED
            task_result.error = str(e)
        finally:
            self._current_agent = None
            await self._cleanup(browser)

        task_result.completed_at = datetime.now()
        return task_result
