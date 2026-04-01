from pathlib import Path


def resolve_bundled_asset_path(file_name: str) -> str:
    """返回 autopilot/assets 下文件的绝对路径。"""
    path = Path(__file__).resolve().parent / "assets" / file_name
    if not path.is_file():
        raise FileNotFoundError(f"Asset not found: {path}")
    return str(path)
