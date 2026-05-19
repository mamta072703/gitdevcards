"""FastAPI application entrypoint for GitHub Dev Card Generator.

This module constructs an app that binds the `github_card_agent` and exposes
endpoints to generate dev cards, serve saved cards, and a health check. It
uses simple in-memory session and memory services and a minimal Runner that
streams step events while the agent runs.
"""
from __future__ import annotations

import json
import os
from typing import Dict, Generator

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse

from pydantic import BaseModel

try:
    from .agent import github_card_agent
except Exception:
    # allow running from the backend folder directly
    from agent import github_card_agent


class GenerateRequest(BaseModel):
    username: str


class InMemorySessionService:
    def __init__(self):
        self._sessions: Dict[str, str] = {}

    def get_or_create(self, username: str) -> str:
        if username in self._sessions:
            return self._sessions[username]
        sid = f"session:{username}"
        self._sessions[username] = sid
        return sid


class InMemoryMemoryService:
    def __init__(self):
        self._mem: Dict[str, Dict] = {}

    def get(self, session_id: str) -> Dict:
        return self._mem.setdefault(session_id, {})

    def set(self, session_id: str, data: Dict) -> None:
        self._mem[session_id] = data


class Runner:
    """Minimal runner that streams events while executing the agent.

    If `github_card_agent` exposes `handle_username`, the runner will call it
    and synthesize step events. If the agent is a real ADK agent with a
    `.run()` method, the runner will try to call that instead.
    """

    def __init__(self, agent: object):
        self.agent = agent

    def run(self, username: str) -> Generator[bytes, None, None]:
        # Stream start
        yield (json.dumps({"event": "started", "username": username}) + "\n").encode()

        # If agent has `handle_username`, use fallback flow and emit step events
        if hasattr(self.agent, "handle_username"):
            yield (json.dumps({"event": "step", "message": "scraping github"}) + "\n").encode()
            # The fallback agent performs all steps internally
            result = self.agent.handle_username(username)
            yield (json.dumps({"event": "step", "message": "analysis complete"}) + "\n").encode()
            yield (json.dumps({"event": "step", "message": "html generated and saved"}) + "\n").encode()
            # Final result
            payload = {
                "event": "finished",
                "path": result.get("path"),
                "card_theme": result.get("card_theme"),
                "developer_vibe": result.get("developer_vibe"),
            }
            yield (json.dumps(payload) + "\n").encode()
            return

        # Otherwise try calling a generic `.run()` on the agent
        if hasattr(self.agent, "run"):
            # Attempt to run the ADK agent and stream any textual events
            try:
                run_result = self.agent.run(f"Generate a dev card for {username}")
                # If run_result is iterable, stream items; otherwise return single result
                if hasattr(run_result, "__iter__"):
                    for item in run_result:
                        yield (json.dumps({"event": "agent_event", "data": str(item)}) + "\n").encode()
                else:
                    yield (json.dumps({"event": "finished", "result": str(run_result)}) + "\n").encode()
            except Exception as e:
                yield (json.dumps({"event": "error", "message": str(e)}) + "\n").encode()
            return

        # Agent does not support expected interfaces
        yield (json.dumps({"event": "error", "message": "agent has no runnable interface"}) + "\n").encode()


app = FastAPI(title="GitHub Dev Card Generator")

# Allow all origins for the frontend during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Services and runner
session_service = InMemorySessionService()
memory_service = InMemoryMemoryService()
runner = Runner(github_card_agent)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/generate")
def generate(req: GenerateRequest):
    username = req.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="username required")

    session_id = session_service.get_or_create(username)

    def event_stream():
        for chunk in runner.run(username):
            yield chunk

    return StreamingResponse(event_stream(), media_type="application/json")


@app.get("/card/{username}")
def serve_card(username: str):
    # Serve the saved card HTML from static/cards/{username}.html
    safe = username.replace("/", "-")
    path = os.path.join(os.path.dirname(__file__), "static", "cards", f"{safe}.html")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="card not found")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    return HTMLResponse(content=content)


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
