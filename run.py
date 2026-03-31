""" 启动 AI NPC 后端服务 """
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

# 项目根目录加入 path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)


def setup_logging() -> None:
    """初始化日志：控制台 + logs/app.log 文件滚动保存。"""
    log_dir = os.path.join(PROJECT_ROOT, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "app.log")

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # 避免 Flask debug 重载导致重复 handler
    if root.handlers:
        root.handlers.clear()

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(fmt)

    root.addHandler(file_handler)
    logging.getLogger(__name__).info("Logging initialized. file=%s", log_file)


setup_logging()

from app.main import create_app

app = create_app()

# http://localhost:5000/
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
