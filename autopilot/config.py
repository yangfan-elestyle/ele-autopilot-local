"""
Job 执行配置：用于控制 autopilot 运行参数

通过 HTTP API 传入，未配置的参数使用 Agent 默认值。
"""

from typing import Literal

from pydantic import BaseModel


class JobConfig(BaseModel):
    """Job 执行配置（会被 Job/TaskRunner 读取）

    所有 Agent 相关参数默认为 None，表示使用 browser-use Agent 的默认值。
    """

    # 基础配置
    gemini_model: str = "gemini-3-flash-preview"  # Gemini 模型名称
    max_steps: int = 1000  # 最大执行步骤数
    headless: bool = False  # 浏览器是否无头模式

    # Agent 行为配置
    use_vision: bool | Literal["auto"] | None = None  # 是否使用视觉，默认 True
    max_failures: int | None = None  # 最大连续失败次数，默认 3
    max_actions_per_step: int | None = None  # 每步最大动作数，默认 3
    use_thinking: bool | None = None  # 是否启用思考，默认 True
    flash_mode: bool | None = None  # 快速模式，默认 False

    # 超时配置
    llm_timeout: int | None = None  # LLM 调用超时（秒），默认根据模型自动设置
    step_timeout: int | None = None  # 单步执行超时（秒），默认 120

    # 提示词配置
    override_system_message: str | None = None  # 完全覆盖系统提示词
    extend_system_message: str | None = None  # 追加到系统提示词末尾
