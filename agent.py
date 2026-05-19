"""ADK agent wrapper for GitHub Dev Card generation.

This module exports `github_card_agent`. It attempts to construct a real
Google ADK agent wired to an MCP toolset. If the ADK/MCP libraries are not
available at runtime, a lightweight local fallback agent is provided that
directly calls the tools implemented in `mcp_server.py`.
"""
from __future__ import annotations

import os
import subprocess
from typing import Any, Callable, Dict


SYSTEM_INSTRUCTION = (
    "You are a GitHub profile analyst and dev card generator. When a user gives you a "
    "GitHub username, you ALWAYS follow this exact sequence: first call scrape_github, "
    "then analyze_profile with the result, then generate_card_html with all three inputs, "
    "then save_card. Never skip steps. Be enthusiastic about developers' work. "
    "If the profile is private or doesn't exist, say so clearly."
)


def _build_adk_agent_real() -> Any | None:
    """Try to build a real ADK agent wired to an McpToolset (stdio transport).

    The real ADK path is only enabled when the environment explicitly opts in
    via USE_REAL_ADK_AGENT=1. By default the service uses the local fallback
    implementation to avoid external agent failures and keep card generation
    stable.
    """
    if os.environ.get("USE_REAL_ADK_AGENT", "0").lower() not in {"1", "true", "yes"}:
        return None

    try:
        import google_adk as adk  # type: ignore
        from fastmcp import McpToolset, StdioTransport  # type: ignore
    except Exception:
        return None

    # Start the MCP server as a subprocess using stdio transport command.
    backend_dir = os.path.dirname(__file__)
    cmd = ["python", "mcp_server.py"]

    # Create a stdio transport pointing at a subprocess running the MCP server.
    transport = StdioTransport(cmd=cmd, cwd=backend_dir, env=os.environ.copy())
    toolset = McpToolset(transport=transport)

    # Construct ADK agent using Gemini 2.5 Flash
    agent = adk.Agent(
        model="gemini-2.5-flash",
        system_instruction=SYSTEM_INSTRUCTION,
        tools=toolset,
    )
    return agent


class _LocalFallbackAgent:
    """Simple local agent fallback that calls mcp_server functions directly."""

    def __init__(self):
        try:
            from . import mcp_server
        except Exception:
            # allow running from backend directory directly
            import mcp_server

        self._mcp = mcp_server

    def handle_username(self, username: str) -> Dict[str, str | Dict]:
        """Follow the exact sequence and return a summary dict.

        Keys: path, card_theme, developer_vibe
        """
        # 1. scrape_github
        github_data = self._mcp.scrape_github(username)

        # 2. analyze_profile
        analysis = self._mcp.analyze_profile(github_data)

        # 3. generate_card_html
        html = self._mcp.generate_card_html(username, github_data, analysis)

        # 4. save_card
        path = self._mcp.save_card(username, html)

        return {
            "path": path,
            "card_theme": analysis.get("card_theme"),
            "developer_vibe": analysis.get("developer_vibe"),
        }


# Try to instantiate a real ADK agent; otherwise provide the local fallback.
_real_agent = _build_adk_agent_real()

if _real_agent is not None:
    github_card_agent = _real_agent
else:
    github_card_agent = _LocalFallbackAgent()


__all__ = ["github_card_agent"]


if __name__ == "__main__":
    # quick manual test
    print("github_card_agent available:", type(github_card_agent))
