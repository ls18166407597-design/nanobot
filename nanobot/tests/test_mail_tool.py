from nanobot.agent.tools.base import ToolResult
from nanobot.agent.tools.mail import MailTool


class _ToolStub:
    def __init__(self, out: str):
        self.out = out

    async def execute(self, **kwargs):
        return ToolResult(success=True, output=self.out)


class _RegistryStub:
    def __init__(self, mapping):
        self.mapping = mapping

    def get(self, name: str):
        return self.mapping.get(name)


async def _run(coro):
    return await coro


def test_mail_tool_auto_prefers_gmail():
    reg = _RegistryStub({"gmail": _ToolStub("gmail-ok"), "qq_mail": _ToolStub("qq-ok")})
    tool = MailTool(reg)
    import asyncio
    res = asyncio.run(_run(tool.execute(action="status", provider="auto")))
    assert res.success
    assert res.output == "gmail-ok"


def test_mail_tool_select_qq_mail():
    reg = _RegistryStub({"qq_mail": _ToolStub("qq-ok")})
    tool = MailTool(reg)
    import asyncio
    res = asyncio.run(_run(tool.execute(action="list", provider="qq_mail")))
    assert res.success
    assert res.output == "qq-ok"
