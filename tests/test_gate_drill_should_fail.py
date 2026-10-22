"""门禁演练专用：这个用例必须失败，用来验证推送后 pytest 门禁真的会拦。

用途：docs/05 §5 演练 1。验证完立即关闭 PR 并删除本分支，禁止合并。
"""


def test_gate_drill_intentionally_fails():
    assert False, "演练专用失败用例（预期让 CI 变红）"
