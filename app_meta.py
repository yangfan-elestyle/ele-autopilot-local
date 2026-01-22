from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import tomllib


@lru_cache(maxsize=1)
def get_project_info() -> dict[str, str]:
    """
    读取 pyproject.toml 的 [project] 元信息。

    说明：
    - 统一从 pyproject.toml 读取，避免多处硬编码版本号/名称。
    - 读取失败时回退到安全默认值，避免启动时报错。
    """
    pyproject_path = Path(__file__).resolve().parent / "pyproject.toml"
    try:
        data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
        project = data.get("project") or {}
        name = str(project.get("name") or "app")
        version = str(project.get("version") or "0.0.0")
        return {"name": name, "version": version}
    except Exception:
        return {"name": "app", "version": "0.0.0"}


def project_name() -> str:
    return get_project_info()["name"]


def project_version() -> str:
    return get_project_info()["version"]
