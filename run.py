""" 启动 AI NPC 后端服务 """
import os
import sys

# 项目根目录加入 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import create_app

app = create_app()

# http://localhost:5000/
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
