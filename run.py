"""启动本地 Flask 服务：python run.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.main import app, cfg  # noqa: E402

if __name__ == "__main__":
    print(f"Secondhand EC Agent V3 本地服务启动中：http://{cfg.app_host}:{cfg.app_port}")
    app.run(host=cfg.app_host, port=cfg.app_port, debug=False)
