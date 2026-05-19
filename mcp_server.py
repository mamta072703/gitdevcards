"""FastMCP-style tools server implemented with FastAPI.

This file exposes four tools as Python functions and HTTP endpoints:

1. scrape_github(username: str) -> dict
2. analyze_profile(github_data: dict) -> dict
3. generate_card_html(username: str, github_data: dict, analysis: dict) -> str
4. save_card(username: str, html: str) -> str

Run locally with: `python mcp_server.py` or `uv run python mcp_server.py`.
"""
from __future__ import annotations

import os
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, HTTPException


app = FastAPI(title="FastMCP Tools - GitHub Dev Card")


def _parse_github_error(response: httpx.Response) -> str:
    try:
        payload = response.json()
        return payload.get("message", "")
    except Exception:
        return response.text or ""


def _check_github_response(response: httpx.Response, subject: str) -> None:
    if response.status_code == 404:
        raise HTTPException(status_code=404, detail=f"GitHub {subject} not found")

    if response.status_code == 403:
        message = _parse_github_error(response)
        if "rate limit exceeded" in message.lower():
            raise HTTPException(
                status_code=429,
                detail=("GitHub API rate limit exceeded. "
                        "Set GITHUB_TOKEN in your environment or wait a few minutes."),
            )
        raise HTTPException(status_code=403, detail=f"GitHub API forbidden: {message or response.status_code}")

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=(f"GitHub request failed for {subject}: {response.status_code} "
                    f"{_parse_github_error(response)}"),
        ) from exc


def _get_github_url(client: httpx.Client, url: str, headers: dict[str, str], subject: str) -> httpx.Response:
    retries = 2
    for attempt in range(retries + 1):
        try:
            response = client.get(url, headers=headers)
        except httpx.RequestError as exc:
            if attempt < retries:
                time.sleep(1)
                continue
            raise HTTPException(status_code=502, detail=f"Unable to reach GitHub: {exc}") from exc

        if response.status_code >= 500 and attempt < retries:
            time.sleep(1)
            continue

        _check_github_response(response, subject)
        return response

    raise HTTPException(status_code=502, detail=f"GitHub request failed for {subject}")


def scrape_github(username: str) -> Dict[str, Any]:
    """Scrape public GitHub profile data using the REST API.

    Returns selected user fields and top repositories and language aggregates.
    """
    base = "https://api.github.com"
    user_url = f"{base}/users/{username}"
    repos_url = f"{base}/users/{username}/repos?per_page=100&sort=updated"

    # Use optional GitHub token to increase rate limits if provided via env
    gh_token = os.environ.get("GITHUB_TOKEN")
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "GitHub-Dev-Card-Generator",
    }
    if gh_token:
        headers["Authorization"] = f"token {gh_token}"

    with httpx.Client(timeout=20.0) as client:
        r_user = _get_github_url(client, user_url, headers, "user")
        user = r_user.json()

        r_repos = _get_github_url(client, repos_url, headers, "repositories")
        repos = r_repos.json()

    # Top 6 repos by stars
    sorted_by_stars = sorted(repos, key=lambda r: r.get("stargazers_count", 0), reverse=True)
    top6 = []
    for r in sorted_by_stars[:6]:
        top6.append({
            "name": r.get("name"),
            "stars": r.get("stargazers_count", 0),
            "language": r.get("language"),
            "description": r.get("description"),
            "html_url": r.get("html_url"),
        })

    # Aggregate languages
    languages = [r.get("language") for r in repos if r.get("language")]
    lang_counts = Counter(languages)
    most_used_languages = [{"language": k, "count": v} for k, v in lang_counts.most_common()]

    result = {
        "login": user.get("login"),
        "name": user.get("name"),
        "bio": user.get("bio"),
        "location": user.get("location"),
        "public_repos": user.get("public_repos", 0),
        "followers": user.get("followers", 0),
        "avatar_url": user.get("avatar_url"),
        "top_repos": top6,
        "most_used_languages": most_used_languages,
        "raw_repos": repos,
    }

    return result


def _call_gemini_mock(github_data: Dict[str, Any]) -> Dict[str, Any]:
    """Produce a lightweight mock analysis when no Gemini endpoint is configured."""
    langs = [l.get("language") for l in github_data.get("top_repos", []) if l.get("language")]
    lang_counts = Counter(langs)
    top_skills = [l for l, _ in lang_counts.most_common(3)]
    if not top_skills:
        # fallback to most_used_languages
        top_skills = [l["language"] for l in github_data.get("most_used_languages", [])[:3]]

    name = github_data.get("name") or github_data.get("login") or "Developer"
    developer_vibe = f"{name} is an engaged developer who shows strong interest in {', '.join(top_skills) if top_skills else 'software engineering'}."
    fun_fact = "This developer has several repositories with active stars — they likely maintain polished, shareable projects."
    themes = ["hacker", "builder", "researcher", "designer", "open-source-hero"]
    card_theme = themes[0] if top_skills and "C" in top_skills else (themes[1] if top_skills else themes[3])

    return {
        "developer_vibe": developer_vibe,
        "top_skills": top_skills[:3],
        "fun_fact": fun_fact,
        "card_theme": card_theme,
    }


def analyze_profile(github_data: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze GitHub data using Gemini 2.5 Flash (or a mock).

    If `GEMINI_API_URL` is set in the environment the function will attempt to POST the
    profile JSON to that endpoint. Otherwise it returns a deterministic mock analysis.
    """
    gemini_url = os.environ.get("GEMINI_API_URL")
    api_key = os.environ.get("GEMINI_API_KEY")

    if gemini_url:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        payload = {"input": github_data, "model": "gemini-2.5-flash"}
        try:
            with httpx.Client(timeout=30.0) as client:
                r = client.post(gemini_url, json=payload, headers=headers)
                r.raise_for_status()
                return r.json()
        except Exception:
            # fallback to mock on error
            return _call_gemini_mock(github_data)

    return _call_gemini_mock(github_data)


def generate_card_html(username: str, github_data: Dict[str, Any], analysis: Dict[str, Any]) -> str:
    """Generate a self-contained HTML dev card string.

    The returned HTML includes inline CSS and images referenced by URL.
    """
    avatar = github_data.get("avatar_url", "")
    name = github_data.get("name") or github_data.get("login") or username
    vibe = analysis.get("developer_vibe", "")
    top_skills = analysis.get("top_skills", [])
    repo_count = github_data.get("public_repos", 0)
    followers = github_data.get("followers", 0)
    top3 = github_data.get("top_repos", [])[:3]
    theme = analysis.get("card_theme", "builder")

    theme_css = {
        "hacker": {"bg": "#0f172a", "fg": "#e6f0ff", "accent": "#06b6d4"},
        "builder": {"bg": "#ffffff", "fg": "#0f172a", "accent": "#0ea5e9"},
        "researcher": {"bg": "#f8fafc", "fg": "#0f172a", "accent": "#7c3aed"},
        "designer": {"bg": "#fffaf0", "fg": "#1f2937", "accent": "#f97316"},
        "open-source-hero": {"bg": "#0f172a", "fg": "#d1fae5", "accent": "#10b981"},
    }
    css = theme_css.get(theme, theme_css["builder"])

    badges_html = "".join([f"<span class=\"badge\">{s}</span>" for s in top_skills])

    repos_html = ""
    for r in top3:
        repo_name = r.get('name') or ''
        repo_url = r.get('html_url') or '#'
        stars = r.get('stars', 0)
        language = r.get('language')
        description = (r.get('description') or '').replace('\n', ' ')

        parts = f"<a href=\"{repo_url}\">{repo_name}</a> — ⭐ {stars}"
        if language:
            parts += f" — {language}"

        repos_html += f"<li>{parts}<div class=\"desc\">{description}</div></li>"

    html = f"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>{name} — Dev Card</title>
  <style>
    :root{{--bg:{css['bg']};--fg:{css['fg']};--accent:{css['accent']}}}
    body{{background:var(--bg);color:var(--fg);font-family:Inter,Arial,Helvetica,sans-serif;padding:24px}}
    .card{{max-width:760px;margin:0 auto;background:rgba(255,255,255,0.02);border-radius:12px;padding:20px;box-shadow:0 6px 24px rgba(0,0,0,0.25)}}
    img.avatar{{width:56px;height:56px;border-radius:50%;border:2px solid var(--accent);flex-shrink:0}}
    .header{{display:flex;gap:12px;align-items:flex-start;margin-bottom:8px}}
    h1{{margin:0;font-size:22px}}
    .vibe{{margin-top:8px;font-style:italic;color:var(--fg)}}
    .badges{{margin-top:12px}}
    .badge{{display:inline-block;background:var(--accent);color:#fff;padding:6px 10px;border-radius:999px;margin-right:8px;font-size:12px}}
    .meta{{margin-top:12px;color:rgba(255,255,255,0.75)}}
    ul.repos{{margin-top:12px}}
    li{{margin-bottom:8px}}
    .desc{{font-size:13px;color:rgba(255,255,255,0.7)}}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <img class="avatar" src="{avatar}" alt="avatar" />
      <div>
        <h1>{name}</h1>
        <div class="vibe">{vibe}</div>
        <div class="badges">{badges_html}</div>
        <div class="meta">{repo_count} repos • {followers} followers</div>
      </div>
    </div>
    <h3 style="margin-top:16px">Top repositories</h3>
    <ul class="repos">{repos_html}</ul>
    <div style="margin-top:18px;color:var(--fg);opacity:0.9"><strong>Fun fact:</strong> {analysis.get('fun_fact','')}</div>
  </div>
</body>
</html>
"""
    return html


def save_card(username: str, html: str) -> str:
    """Save the generated HTML to `static/cards/{username}.html` and return the relative path."""
    base_dir = Path(__file__).resolve().parent
    out_dir = base_dir / "static" / "cards"
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_name = username.replace("/", "-")
    dest = out_dir / f"{safe_name}.html"
    dest.write_text(html, encoding="utf-8")
    # Return path relative to backend folder
    rel = Path("static") / "cards" / f"{safe_name}.html"
    return str(rel.as_posix())


@app.get("/tools")
def list_tools():
    return {
        "tools": [
            "scrape_github",
            "analyze_profile",
            "generate_card_html",
            "save_card",
        ]
    }


@app.post("/tools/scrape_github")
def http_scrape(payload: Dict[str, Any]):
    username = payload.get("username")
    if not username:
        raise HTTPException(status_code=400, detail="username required")
    return scrape_github(username)


@app.post("/tools/analyze_profile")
def http_analyze(payload: Dict[str, Any]):
    github_data = payload.get("github_data")
    if not github_data:
        raise HTTPException(status_code=400, detail="github_data required")
    return analyze_profile(github_data)


@app.post("/tools/generate_card_html")
def http_generate(payload: Dict[str, Any]):
    username = payload.get("username")
    github_data = payload.get("github_data")
    analysis = payload.get("analysis")
    if not username or not github_data or not analysis:
        raise HTTPException(status_code=400, detail="username, github_data and analysis required")
    return {"html": generate_card_html(username, github_data, analysis)}


@app.post("/tools/save_card")
def http_save(payload: Dict[str, Any]):
    username = payload.get("username")
    html = payload.get("html")
    if not username or not html:
        raise HTTPException(status_code=400, detail="username and html required")
    path = save_card(username, html)
    return {"path": path}


def create_mcp_tools() -> List[Any]:
    """Return the list of tool function references (for programmatic registration)."""
    return [scrape_github, analyze_profile, generate_card_html, save_card]


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8081"))
    uvicorn.run(app, host="0.0.0.0", port=port)
