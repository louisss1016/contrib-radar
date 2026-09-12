"""测试包：把 scripts/ 目录加入 sys.path，使测试可以 import 脚本模块。"""
import os
import sys

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "contrib-radar", "scripts")
SCRIPTS_DIR = os.path.abspath(SCRIPTS_DIR)
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)
