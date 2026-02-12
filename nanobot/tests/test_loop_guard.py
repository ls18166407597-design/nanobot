from nanobot.agent.loop_guard import RepeatWindow, tool_call_hash


def test_tool_call_hash_stable_for_same_payload():
    a = tool_call_hash("exec", {"command": "echo hi", "x": 1})
    b = tool_call_hash("exec", {"x": 1, "command": "echo hi"})
    assert a == b


def test_repeat_window_counts_and_resets():
    rw = RepeatWindow()
    assert rw.update("a") == 1
    assert rw.update("a") == 2
    assert rw.update("b") == 1
