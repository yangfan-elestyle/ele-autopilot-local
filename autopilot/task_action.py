"""
Task Action Handler - 处理 browser-use Agent.run() 的结果

====================================================================
                   browser-use Result 深度分析
====================================================================

Agent.run() 返回类型: AgentHistoryList[AgentStructuredOutput]

这是一个包含完整执行历史的数据结构，提供了丰富的信息用于分析、
调试和云端备份。

====================================================================
                     核心数据结构层级
====================================================================

AgentHistoryList
├── history: list[AgentHistory]          # 每个步骤的执行记录
│   ├── model_output: AgentOutput | None # LLM 的输出（思考过程、动作）
│   │   ├── thinking: str | None         # LLM 的思考过程
│   │   ├── evaluation_previous_goal: str | None  # 对上一步目标的评估
│   │   ├── memory: str | None           # Agent 的记忆/上下文
│   │   ├── next_goal: str | None        # 下一步目标
│   │   └── action: list[ActionModel]    # 执行的动作列表
│   │       └── 动态字段(如 navigate, search, click, input, done 等)
│   │           ├── index: int           # DOM 元素索引
│   │           ├── text/input: str      # 输入文本
│   │           └── ...其他参数
│   │
│   ├── result: list[ActionResult]       # 动作执行结果
│   │   ├── is_done: bool | None         # 任务是否完成
│   │   ├── success: bool | None         # 是否成功(仅 done 时有效)
│   │   ├── judgement: JudgementResult | None  # Judge 评判结果
│   │   │   ├── reasoning: str | None    # 评判推理过程
│   │   │   ├── verdict: bool            # 最终判定
│   │   │   ├── failure_reason: str | None  # 失败原因
│   │   │   ├── impossible_task: bool    # 任务是否不可能完成
│   │   │   └── reached_captcha: bool    # 是否遇到验证码
│   │   ├── error: str | None            # 错误信息
│   │   ├── attachments: list[str] | None    # 附件文件路径
│   │   ├── images: list[dict] | None    # 图片(base64)
│   │   ├── long_term_memory: str | None # 长期记忆
│   │   ├── extracted_content: str | None    # 提取的内容
│   │   ├── include_extracted_content_only_once: bool  # 仅用于下一步 read_state（不写入长期记忆）
│   │   ├── include_in_memory: bool (Deprecated)       # 旧字段：是否把 extracted_content 放入 long_term_memory
│   │   └── metadata: dict | None        # 元数据(如点击坐标)
│   │
│   ├── state: BrowserStateHistory       # 浏览器状态快照
│   │   ├── url: str                     # 页面 URL
│   │   ├── title: str                   # 页面标题
│   │   ├── tabs: list[TabInfo]          # 所有标签页信息
│   │   │   ├── url: str
│   │   │   ├── title: str
│   │   │   ├── target_id: str
│   │   │   └── parent_target_id: str | None   # 弹窗/iframe 等来源 tab（序列化别名 parent_tab_id）
│   │   ├── interacted_element: list[DOMInteractedElement | None]
│   │   │   ├── node_id: int             # DOM 节点 ID
│   │   │   ├── backend_node_id: int     # 后端节点 ID
│   │   │   ├── frame_id: str | None      # 所在 frame（可能为空）
│   │   │   ├── node_type: str            # 节点类型（枚举值序列化）
│   │   │   ├── node_value: str           # 节点值（如文本节点内容）
│   │   │   ├── node_name: str           # 标签名
│   │   │   ├── attributes: dict         # 属性
│   │   │   ├── bounds: DOMRect | None   # 元素边界
│   │   │   ├── x_path: str              # XPath
│   │   │   ├── element_hash: int         # 交互元素 hash（不稳定）
│   │   │   ├── stable_hash: int | None   # 稳定 hash（过滤动态 class，便于匹配）
│   │   │   └── ax_name: str | None      # 无障碍名称
│   │   └── screenshot_path: str | None  # 截图路径
│   │
│   ├── metadata: StepMetadata | None    # 步骤元数据
│   │   ├── step_start_time: float       # 开始时间戳
│   │   ├── step_end_time: float         # 结束时间戳
│   │   ├── step_number: int             # 步骤编号
│   │   ├── step_interval: float | None  # 可选：步进间隔/采样间隔（版本相关）
│   │   └── duration_seconds: float      # 持续时间(秒)
│   │
│   └── state_message: str | None        # 状态消息

====================================================================
                    AgentHistoryList 核心方法
====================================================================

结果获取方法:
- final_result() -> str | None           # 获取最终提取的内容
- structured_output -> AgentStructuredOutput | None  # 结构化输出（依赖 output_model_schema；序列化后通常丢失）
- get_structured_output(output_model) -> AgentStructuredOutput | None  # 从 final_result 解析结构化输出（适用于反序列化后）
- is_done() -> bool                      # 任务是否完成
- is_successful() -> bool | None         # 任务是否成功
- judgement() -> dict | None             # 获取 Judge 评判结果
- is_judged() -> bool                    # 是否已进行 Judge 评判
- is_validated() -> bool | None          # Judge 是否验证通过

历史信息方法:
- errors() -> list[str | None]           # 获取所有错误
- has_errors() -> bool                   # 是否有错误
- urls() -> list[str | None]             # 所有访问过的 URL
- screenshots(n_last=None, return_none_if_not_screenshot=True) -> list[str | None]  # 截图(base64)
- screenshot_paths(n_last=None, return_none_if_not_screenshot=True) -> list[str | None]  # 截图路径

动作分析方法:
- action_names() -> list[str]            # 所有动作名称
- last_action() -> dict | None           # 最后一个动作（单条）
- model_actions() -> list[dict]          # 所有动作详情（每条会附带 interacted_element）
- model_actions_filtered(include=...) -> list[dict]  # 仅保留指定 action 名称
- action_history() -> list[list[dict]]   # 截断版历史（每 step 一组 action + result 摘要）
- model_thoughts() -> list[AgentBrain]   # 所有思考过程
- model_outputs() -> list[AgentOutput]   # 所有 model_output（原始结构）
- extracted_content() -> list[str]       # 所有提取的内容
- action_results() -> list[ActionResult] # 所有动作结果
- agent_steps() -> list[str]             # 面向 Judge 的可读 step 文本（含 actions/result/error）

统计方法:
- number_of_steps() -> int               # 总步骤数
- total_duration_seconds() -> float      # 总执行时间
- __len__() -> int                       # 历史条目数

序列化方法:
- model_dump() -> dict                   # 转为字典（仅包含 history；不含 usage 等统计字段）
- save_to_file(filepath, ...)            # 保存到 JSON 文件
- load_from_dict(data, output_model) -> AgentHistoryList  # 从 dict 反序列化
- load_from_file(filepath, output_model) -> AgentHistoryList  # 从 JSON 反序列化

辅助方法:
- add_item(history_item) -> None         # 追加一条 history
- __str__() -> str                       # 便于调试的字符串表示
- __repr__() -> str                      # 同 __str__()

====================================================================
                    可用于云端备份的关键信息
====================================================================

1. 任务执行概要
   - 任务描述、状态、是否成功
   - 开始/结束时间、总耗时
   - 总步骤数

2. 执行过程详情
   - 每一步的动作、目标、思考过程
   - 每一步访问的 URL 和页面标题
   - 每一步的截图路径或 base64

3. 交互元素记录
   - 点击/输入的 DOM 元素信息
   - 元素的 XPath、属性、边界框

4. 结果与错误
   - 最终结果 (final_result)
   - 错误列表
   - Judge 评判(如果启用)

====================================================================
                    关键注意事项（与云端备份强相关）
====================================================================

1) 关于 action 名称
   - 本项目依赖的 browser-use(>=0.11.9) 内置动作名称以实际注册为准，
     常见为: navigate/search/click/input/scroll/done/read_file/write_file/...；
     不是 click_element / input_text 这类名字。

2) 关于 screenshot_path 的语义
   - browser-use 每个 step 都会先抓取“当时用于 LLM 决策的浏览器状态截图”，
     然后才执行动作；因此 screenshot_path 更像“动作前看到的画面”，不是动作后。

====================================================================
"""

import json
import logging
import platform
import sys
from dataclasses import asdict, dataclass
from dataclasses import is_dataclass
from datetime import datetime
from importlib import metadata
from pathlib import Path
from typing import Any

from pydantic import BaseModel

# browser-use 类型导入（用于类型提示/IDE 补全）
from browser_use.agent.views import (
    ActionResult,
    AgentHistory,
    AgentHistoryList,
    AgentOutput,
    JudgementResult,
    StepMetadata,
)
from browser_use.browser.views import BrowserStateHistory, TabInfo

logger = logging.getLogger(__name__)

_EPOCH_MS_THRESHOLD = 10_000_000_000  # >= 1e10 认为是毫秒，否则按秒处理


def _coerce_epoch_ms(value: Any) -> int | None:
    """
    尽量把时间值转换为“毫秒时间戳”（epoch ms）。

    支持：
    - datetime
    - int/float（自动判断秒/毫秒）
    - ISO 字符串（尽力解析；失败返回 None）
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return int(value.timestamp() * 1000)
    if isinstance(value, (int, float)):
        v = float(value)
        if abs(v) >= _EPOCH_MS_THRESHOLD:
            return int(v)
        return int(v * 1000)
    if isinstance(value, str):
        try:
            # 兼容常见的 Z 结尾
            iso = value[:-1] + "+00:00" if value.endswith("Z") else value
            dt = datetime.fromisoformat(iso)
            return int(dt.timestamp() * 1000)
        except Exception:
            return None
    return None


def _coerce_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        try:
            v = float(value)
            # 兼容外部传入毫秒时间戳
            if abs(v) >= _EPOCH_MS_THRESHOLD:
                v = v / 1000.0
            return datetime.fromtimestamp(v)
        except Exception:
            return None
    return None


def _safe_dump(obj: Any) -> Any:
    """
    把对象尽可能转成 JSON 兼容结构（dict/list/str/int/float/bool/None）。

    目标：
    - 固定 pydantic v2（BaseModel.model_dump）
    - 兼容 dataclass（asdict）
    - 兼容 Path / datetime
    """
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj

    if isinstance(obj, datetime):
        return _coerce_epoch_ms(obj)

    if isinstance(obj, Path):
        return str(obj)

    if isinstance(obj, dict):
        converted: dict[str, Any] = {}
        for k, v in obj.items():
            key = str(k)
            if key in {
                "timestamp",
                "created_at",
                "started_at",
                "completed_at",
                "step_start_time",
                "step_end_time",
            }:
                ms = _coerce_epoch_ms(v)
                converted[key] = ms if ms is not None else _safe_dump(v)
                continue
            converted[key] = _safe_dump(v)
        return converted

    if isinstance(obj, (list, tuple, set)):
        return [_safe_dump(v) for v in obj]

    if is_dataclass(obj):
        try:
            return _safe_dump(asdict(obj))
        except Exception:
            pass

    if isinstance(obj, BaseModel):
        return _safe_dump(obj.model_dump(exclude_none=False, mode="json"))

    # 兜底：尽量不要抛异常，返回 string 表示
    try:
        return str(obj)
    except Exception:
        return repr(obj)


def _get_pkg_version(package: str) -> str | None:
    try:
        return metadata.version(package)
    except Exception:
        return None


def _build_runtime_info() -> dict[str, Any]:
    info: dict[str, Any] = {
        "python": {
            "version": sys.version,
            "implementation": platform.python_implementation(),
        },
        "platform": platform.platform(),
        "packages": {
            "browser-use": _get_pkg_version("browser-use"),
            "fastapi": _get_pkg_version("fastapi"),
            "langchain-openai": _get_pkg_version("langchain-openai"),
        },
    }

    try:
        from autopilot.app_meta import project_name, project_version

        info["app"] = {"name": project_name(), "version": project_version()}
    except Exception:
        pass

    return info


@dataclass
class TaskActionSummary:
    """任务执行摘要 - 用于云端上传"""

    # 基本信息
    status: str  # completed / failed / incomplete
    is_done: bool
    is_successful: bool | None
    started_at: int | None  # 毫秒时间戳(epoch ms)
    completed_at: int | None  # 毫秒时间戳(epoch ms)
    duration_seconds: float

    # 执行统计
    total_steps: int
    total_actions: int
    step_error_count: int
    action_error_count: int

    # 结果
    final_result: str | None
    judgement: dict | None
    is_validated: bool | None
    all_extracted_content: list[str]

    # URL 轨迹
    visited_urls: list[str]

    # 动作序列
    action_sequence: list[str]

    # 错误列表
    errors: list[str]
    action_errors: list[str]


@dataclass
class StepDetail:
    """单步执行详情"""

    step_number: int
    url: str | None
    page_title: str | None
    tabs: list[dict]
    state_message: str | None

    # LLM 输出
    thinking: str | None
    thinking_image: str | None
    evaluation: str | None
    memory: str | None
    next_goal: str | None
    model_output: dict | None

    # 结果
    results: list[dict]

    # 时间
    duration_seconds: float | None
    step_start_time: int | None  # 毫秒时间戳(epoch ms)
    step_end_time: int | None  # 毫秒时间戳(epoch ms)
    metadata: dict | None
    state: str | None


class TaskActionHandler:
    """处理 Agent.run() 结果的处理器"""

    def __init__(self, result: AgentHistoryList):
        """
        初始化处理器

        Args:
            result: Agent.run() 返回的 AgentHistoryList 对象
        """
        self.result = result

    def _derive_task_times(self) -> tuple[datetime | None, datetime | None]:
        """尽量从 StepMetadata 中推导任务开始/结束时间。"""
        if not self.result.history:
            return None, None

        starts: list[datetime] = []
        ends: list[datetime] = []

        for history_item in self.result.history:
            md = history_item.metadata
            if not md:
                continue
            st = _coerce_datetime(md.step_start_time)
            et = _coerce_datetime(md.step_end_time)
            if st:
                starts.append(st)
            if et:
                ends.append(et)

        return (min(starts) if starts else None, max(ends) if ends else None)

    def extract_summary(self) -> TaskActionSummary:
        """
        提取任务执行摘要

        Returns:
            TaskActionSummary 对象
        """

        # 错误（step 粒度）列表（过滤 None）
        step_errors = [e for e in self.result.errors() if e is not None]

        # 错误（action 粒度）列表
        action_errors = [r.error for r in self.result.action_results() if r.error]

        # 获取时间信息
        duration = self.result.total_duration_seconds()
        started_at, completed_at = self._derive_task_times()

        if started_at and completed_at:
            duration = max(0.0, (completed_at - started_at).total_seconds())

        is_done = self.result.is_done()
        is_successful = self.result.is_successful()
        if not is_done:
            status = "incomplete"
        else:
            status = "completed" if is_successful is True else "failed"

        return TaskActionSummary(
            status=status,
            is_done=is_done,
            is_successful=is_successful,
            started_at=_coerce_epoch_ms(started_at),
            completed_at=_coerce_epoch_ms(completed_at),
            duration_seconds=duration,
            total_steps=self.result.number_of_steps(),
            total_actions=len(self.result.model_actions()),
            step_error_count=len(step_errors),
            action_error_count=len(action_errors),
            final_result=self.result.final_result(),
            judgement=self.result.judgement(),
            is_validated=self.result.is_validated(),
            all_extracted_content=self.result.extracted_content(),
            visited_urls=[str(u) for u in self.result.urls() if u],
            action_sequence=self.result.action_names(),
            errors=step_errors,
            action_errors=action_errors,
        )

    def extract_step_details(self) -> list[StepDetail]:
        """
        提取每一步的详细信息

        Returns:
            StepDetail 对象列表
        """
        steps = []

        for idx, history_item in enumerate(self.result.history):
            state = history_item.state
            model_output_obj = history_item.model_output
            action_results = history_item.result
            md = history_item.metadata

            # 提取 LLM 输出
            thinking = None
            evaluation = None
            memory = None
            next_goal = None
            model_output_dump: dict | None = None

            if model_output_obj:
                thinking = model_output_obj.thinking
                evaluation = model_output_obj.evaluation_previous_goal
                memory = model_output_obj.memory
                next_goal = model_output_obj.next_goal
                model_output_dump = _safe_dump(model_output_obj)

            # 提取结果（step screen images 在 results 内）
            results = _safe_dump(action_results)

            # 提取时间
            duration = None
            step_start_time = None
            step_end_time = None
            metadata_dump: dict | None = None
            if md:
                duration = md.duration_seconds
                step_start_time = _coerce_epoch_ms(md.step_start_time)
                step_end_time = _coerce_epoch_ms(md.step_end_time)
                metadata_dump = _safe_dump(md)

            # tabs
            tabs = [_safe_dump(t) for t in state.tabs]
            # step screenshot
            thinking_image = state.get_screenshot()

            steps.append(
                StepDetail(
                    step_number=md.step_number if md else (idx + 1),
                    url=state.url,
                    page_title=state.title,
                    tabs=tabs,
                    state_message=history_item.state_message,
                    thinking=thinking,
                    thinking_image=thinking_image,
                    evaluation=evaluation,
                    memory=memory,
                    next_goal=next_goal,
                    model_output=model_output_dump,
                    results=results,
                    duration_seconds=duration,
                    step_start_time=step_start_time,
                    step_end_time=step_end_time,
                    metadata=metadata_dump,
                    state=json.dumps(_safe_dump(state.to_dict())),
                )
            )

        return steps

    def to_cloud_payload(self, config: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        生成用于云端上传的完整 payload

        Args:
            config: 可选的执行配置，将附加到 runtime 中

        Returns:
            可序列化的字典
        """
        summary = self.extract_summary()
        steps = self.extract_step_details()

        runtime = _build_runtime_info()
        if config:
            runtime["config"] = config

        payload: dict[str, Any] = {
            "timestamp": _coerce_epoch_ms(datetime.now()),
            "runtime": runtime,
            "summary": asdict(summary),
            "steps": [asdict(step) for step in steps],
        }

        payload["raw_history"] = json.dumps(_safe_dump(self.result.model_dump()))

        return _safe_dump(payload)
