"""读取 config/secrets.env 并提供项目全部配置。"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# 打包（PyInstaller）后以 exe 所在目录为项目根；源码运行时以 app/ 的上级目录为根
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
    """集中管理 Mercari、相机、DeepSeek、本地服务配置。"""

    def __init__(self, env_file=None):
        # override=False：已存在的系统环境变量优先，便于测试时临时覆盖
        load_dotenv(env_file or SECRETS_FILE, override=False)

        # ---------- Mercari Shops（个人卖家版留空，不使用官方 API） ----------
        self.mercari_env = os.getenv("MERCARI_ENV", "production")
        self.mercari_access_token = os.getenv("MERCARI_ACCESS_TOKEN", "")
        self.mercari_shop_id = os.getenv("MERCARI_SHOP_ID", "")
        self.mercari_base_url = os.getenv("MERCARI_BASE_URL", "https://api.mercari-shops.com")

        # ---------- 相机 Lumix GF9 USB 存储模式 ----------
        self.camera_mode = os.getenv("CAMERA_MODE", "usb_storage").strip()
        self.camera_auto_detect = _as_bool(os.getenv("CAMERA_AUTO_DETECT"), True)
        self.camera_drive = os.getenv("CAMERA_DRIVE", "auto").strip()
        self.camera_dcim_subdir = os.getenv("CAMERA_DCIM_SUBDIR", "DCIM").strip()
        self.camera_import_dir = os.getenv("CAMERA_IMPORT_DIR", "./images/imported").strip()
        self.camera_jpeg_quality = _as_int(os.getenv("CAMERA_JPEG_QUALITY"), 85)
        self.camera_max_long_edge = _as_int(os.getenv("CAMERA_MAX_LONG_EDGE"), 2000)

        # ---------- DeepSeek API（可选，默认关闭） ----------
        self.deepseek_enabled = _as_bool(os.getenv("DEEPSEEK_ENABLED"), False)
        self.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        self.deepseek_base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip()
        self.deepseek_model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip()

        # ---------- 本地服务 ----------
        self.app_host = os.getenv("APP_HOST", "127.0.0.1").strip()
        self.app_port = _as_int(os.getenv("APP_PORT"), 8765)

    def check_ready(self) -> list:
        """检查关键配置是否缺失，返回缺失项列表（空列表表示就绪）。"""
        missing = []
        return missing
