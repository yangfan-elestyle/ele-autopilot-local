"""
Patch: 给 browser-use 的 click action 加上 terminates_sequence=True

browser-use 的 multi_act() 顺序执行 LLM 返回的 action 列表，有两层守卫防止对过期 DOM 操作：
  Layer 1 (静态标记) — action 元数据声明 terminates_sequence=True，执行后立即 break。
                       已标记的: navigate, search, go_back, switch, evaluate。
  Layer 2 (运行时)  — 执行后比较 URL/focus，发生变化则 break。

click 默认未标记 terminates_sequence，因为并非所有 click 都改变页面（可能只是展开菜单、
勾选复选框等）。但 Layer 2 只能捕获 URL 级别的变化，无法覆盖 DOM 局部更新的场景。

此 patch 将 click 提升到 Layer 1：无论 click 是否真的导致页面变化，都一律终止序列。
这是更保守的策略，确保 click 后 LLM 能重新获取最新页面状态再决定下一步。
click 之前的 action（如 type、scroll）仍正常执行，不受影响。
"""

import logging

from browser_use import Agent

logger = logging.getLogger(__name__)

_patched = False


def patch_click_terminates_sequence():
	global _patched
	if _patched:
		return
	_patched = True

	_original_init = Agent.__init__

	def _patched_init(self, *args, **kwargs):
		_original_init(self, *args, **kwargs)
		click_action = self.tools.registry.registry.actions.get("click")
		if click_action:
			click_action.terminates_sequence = True

	Agent.__init__ = _patched_init  # type: ignore[method-assign]
	logger.info("patch applied: click.terminates_sequence = True")
