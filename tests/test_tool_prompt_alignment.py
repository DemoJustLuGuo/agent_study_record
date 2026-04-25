from pathlib import Path

from agent.tools.registry import get_registered_tool_names


PROMPT_FILES = [
    Path("agent/prompts/main_prompt.txt"),
    Path("agent/prompts/report_prompt.txt"),
]


def test_registered_tools_are_documented_in_prompts() -> None:
    for prompt_file in PROMPT_FILES:
        prompt_text = prompt_file.read_text(encoding="utf-8")

        for tool_name in get_registered_tool_names():
            assert tool_name in prompt_text, f"{tool_name} missing from {prompt_file}"
