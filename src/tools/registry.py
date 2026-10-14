from .ITools import ToolResult, ToolContext, ToolsInterface

class ToolRegistry:
    def __init__(self, tools: list[ToolsInterface]) -> None:
        self._tools = {tool.name: tool for tool in tools}

    def definition(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in self._tools.values()
        ]

    def execute(self, name: str, context: ToolContext, arguments: dict) -> ToolResult:
        tool = self._tools.get(name)

        if tool is None:
            raise ValueError(f"Unknow tool: {name}")
        return tool.execute(context, arguments)
