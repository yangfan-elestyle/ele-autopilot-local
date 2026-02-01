import logging
import os
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


def is_system_chrome_user_data_dir(user_data_dir: Path) -> bool:
    s = str(user_data_dir).lower()
    return any(
        token in s
        for token in (
            "library/application support/google/chrome",  # macOS
            "appdata/local/google/chrome/user data",  # Windows
            "appdata/roaming/google/chrome/user data",  # Windows
            ".config/google-chrome",  # Linux
        )
    )


def seed_persistent_profile_if_needed(
    *,
    src_user_data_dir: Path,
    dst_user_data_dir: Path,
    profile_directory: str,
    log: logging.Logger | None = None,
) -> bool:
    """
    将系统 Chrome profile “种子复制”到一个可持久化的自动化目录（仅首次执行）。

    背景：browser-use==0.11.3 会把传入的 Chrome user_data_dir 复制到临时目录运行，
    以避免系统 profile 锁冲突/损坏；但这会导致登录态无法持久化。
    """
    log = log or logger
    dst_profile_dir = dst_user_data_dir / profile_directory
    dst_local_state = dst_user_data_dir / "Local State"
    if dst_profile_dir.exists() and dst_local_state.exists():
        return False

    dst_user_data_dir.mkdir(parents=True, exist_ok=True)
    src_profile_dir = src_user_data_dir / profile_directory

    try:
        if src_profile_dir.exists():
            shutil.copytree(src_profile_dir, dst_profile_dir, dirs_exist_ok=True)
        else:
            dst_profile_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        log.warning("复制 Chrome profile 失败：%s", e)
        dst_profile_dir.mkdir(parents=True, exist_ok=True)
    else:
        log.info("已准备持久化 Chrome profile：%s", dst_profile_dir)

    src_local_state = src_user_data_dir / "Local State"
    if src_local_state.exists() and not dst_local_state.exists():
        try:
            shutil.copy(src_local_state, dst_local_state)
        except Exception:
            pass
    return True


def resolve_chrome_user_data_dir(
    *,
    chrome_executable_path: str | None,
    chrome_user_data_dir: str | None,
    profile_directory: str,
    log: logging.Logger | None = None,
) -> str | None:
    if not chrome_user_data_dir:
        return None

    log = log or logger
    expanded = Path(os.path.expanduser(chrome_user_data_dir))

    # browser-use 的“避免损坏系统 profile”逻辑依赖路径名：
    # - 不包含 `browser-use-user-data-dir-` => 复制到临时目录 => 每次启动都是新 profile（登录态不持久）
    # - 包含该前缀 => 认为已是隔离目录 => 不再复制 => 可持久化
    if "browser-use-user-data-dir-" in str(expanded).lower():
        return str(expanded)

    if (
        chrome_executable_path
        and "chrome" in chrome_executable_path.lower()
        and is_system_chrome_user_data_dir(expanded)
    ):
        project_root = Path(__file__).resolve().parents[1]
        persistent_dir = project_root / "browser-use-user-data-dir-persist"
        did_seed = seed_persistent_profile_if_needed(
            src_user_data_dir=expanded,
            dst_user_data_dir=persistent_dir,
            profile_directory=profile_directory,
            log=log,
        )

        if did_seed:
            log.info(
                "browser-use 会临时复制系统 Chrome profile 导致登录态不持久；已种子复制并改用持久化自动化 profile：%s",
                persistent_dir,
            )
        return str(persistent_dir)

    return str(expanded)
