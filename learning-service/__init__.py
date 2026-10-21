"""learning-service：算法工程师可写目录的顶层包（目录名含连字符）。

QA 导入方式：worktree 根在 sys.path 时
``importlib.import_module("learning-service")``，本模块会把
``learning_service`` 别名注册进 sys.modules，之后即可
``from learning_service.mastery import judge_mastery``。
"""

import importlib as _importlib
import sys as _sys

_sub = _importlib.import_module(".learning_service", __name__)
_sub_mod = _importlib.import_module(".learning_service.mastery", __name__)

# 别名：注册后 `import learning_service` / `from learning_service.mastery import ...`
# 与 importlib 的 "learning-service..." 路径指向同一模块对象（类型身份一致）。
_sys.modules.setdefault("learning_service", _sub)
_sys.modules.setdefault("learning_service.mastery", _sub_mod)


def __getattr__(name: str):
    return getattr(_sub, name)
