"""加载本地环境配置，并提供服务和 AI 客户端所需的参数。"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# 源码运行时以仓库根目录为基准；打包运行时以可执行文件所在目录为基准。
if getattr(sys, "frozen", False):
    PROJECT_ROOT = Path(sys.executable).resolve().parent
else:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent

CONFIG_DIR = PROJECT_ROOT / "config"
SECRETS_FILE = CONFIG_DIR / "secrets.env"
EXAMPLE_FILE = CONFIG_DIR / "secrets.env.example"


def _as_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _as_int(value: str, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class Config:
    """集中管理 DeepSeek 和本地服务配置。"""

    def __init__(self, env_file=None):
        # 不覆盖已存在的系统环境变量，让部署环境变量优先于 env 文件。
        load_dotenv(env_file or SECRETS_FILE, override=False)

        # DeepSeek API：默认关闭；启用后需配置 API Key。
        self.deepseek_enabled = _as_bool(os.getenv("DEEPSEEK_ENABLED"), False)
        self.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        self.deepseek_base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip()
        self.deepseek_model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip()

        # 本地 Flask 服务监听地址与端口。
        self.app_host = os.getenv("APP_HOST", "127.0.0.1").strip()
        self.app_port = _as_int(os.getenv("APP_PORT"), 8765)
        # 仅允许明确列出的网页/扩展跨域访问本地 API，避免任意网站读取或调用本地数据。
        origins = os.getenv("APP_ALLOWED_ORIGINS", "http://127.0.0.1:8765,http://localhost:8765")
        self.app_allowed_origins = {origin.strip().rstrip("/") for origin in origins.split(",") if origin.strip()}

    def check_ready(self) -> list:
        """返回已启用功能所缺少的必要配置项。"""
        missing = []
        if self.deepseek_enabled and not self.deepseek_api_key:
            missing.append("DEEPSEEK_API_KEY（启用 DeepSeek 时必填）")
        return missing
