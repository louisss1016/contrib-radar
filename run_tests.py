#!/usr/bin/env python3
"""运行 contrib-radar 全部测试（零依赖，仅用 Python 标准库 unittest）。

用法:
    python run_tests.py
    python run_tests.py -v    # 详细输出
"""
import os
import sys
import unittest

# 把 scripts/ 加入 path，使测试可以 import 脚本模块
SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "contrib-radar", "scripts")
SCRIPTS_DIR = os.path.abspath(SCRIPTS_DIR)
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

TESTS_DIR = os.path.join(os.path.dirname(__file__), "tests")

if __name__ == "__main__":
    verbosity = 2 if "-v" in sys.argv else 1
    loader = unittest.TestLoader()
    suite = loader.discover(TESTS_DIR, pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
