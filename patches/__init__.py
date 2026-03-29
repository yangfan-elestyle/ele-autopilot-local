"""
第三方库 monkey-patch 集中管理。

应用启动时调用 apply_all() 一次性加载所有 patch。
新增 patch 时在此模块注册即可。
"""

from .browser_use_click import patch_click_terminates_sequence


def apply_all():
	"""应用所有 patch"""
	patch_click_terminates_sequence()
