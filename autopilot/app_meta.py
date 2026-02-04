"""项目元信息获取模块。"""

from importlib.metadata import version, PackageNotFoundError

_PACKAGE_NAME = "ele-autopilot-local"


def project_name() -> str:
    """获取项目名称。"""
    return _PACKAGE_NAME


def project_version() -> str:
    """获取项目版本号。"""
    try:
        return version(_PACKAGE_NAME)
    except PackageNotFoundError:
        return "0.0.0"
