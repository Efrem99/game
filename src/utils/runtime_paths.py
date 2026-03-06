"""Runtime path helpers for dev and installed builds."""

import os
from pathlib import Path


def project_root():
    env_root = str(os.environ.get("XBOT_PROJECT_ROOT", "") or "").strip()
    if env_root:
        return Path(env_root)
    return Path(__file__).resolve().parents[2]


def user_data_root():
    env_root = str(os.environ.get("XBOT_USER_DATA_DIR", "") or "").strip()
    if env_root:
        return Path(env_root)
    return project_root()


def is_user_data_mode():
    return bool(str(os.environ.get("XBOT_USER_DATA_DIR", "") or "").strip())


def runtime_dir(*parts):
    path = user_data_root().joinpath(*parts)
    path.mkdir(parents=True, exist_ok=True)
    return path


def runtime_file(*parts):
    path = user_data_root().joinpath(*parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
