"""QA 测试统一入口：注册 learning_service 别名（算法工程师提供的导入方式）。"""

import importlib
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

importlib.import_module("learning-service")

KNOWN_KP = frozenset({"kp_present_simple", "kp_present_continuous"})
