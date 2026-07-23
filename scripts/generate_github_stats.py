#!/usr/bin/env python3
"""Generate static, dependency-free SVG cards from the official GitHub API."""

from __future__ import annotations

import html
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


API_ROOT = "https://api.github.com"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "assets"
COLORS = ["#58a6ff", "#a371f7", "#3fb950", "#d29922", "#f85149"]


def api_get(path: str):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "profile-static-card-generator",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(f"{API_ROOT}{path}", headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API returned {error.code} for {path}: {detail}") from error


def public_repositories(username: str) -> list[dict]:
    repositories: list[dict] = []
    page = 1
    while True:
        batch = api_get(
            f"/users/{username}/repos?type=owner&sort=updated&per_page=100&page={page}"
        )
        repositories.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return [repository for repository in repositories if not repository.get("fork")]


def svg_document(title: str, body: str, width: int = 410, height: int = 165) -> str:
    safe_title = html.escape(title)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
  <title id="title">{safe_title}</title>
  <desc id="desc">Automatically generated from the official GitHub API.</desc>
  <defs>
    <linearGradient id="accent" x1="0" y1="0" x2="1" y2="1">
      <stop stop-color="#a855f7"/><stop offset="1" stop-color="#22d3ee"/>
    </linearGradient>
  </defs>
  <style>
    text {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    .title {{ fill: #f0f6fc; font-size: 16px; font-weight: 650; }}
    .value {{ fill: #f0f6fc; font-size: 20px; font-weight: 700; }}
    .label {{ fill: #8b949e; font-size: 11px; }}
    .language {{ fill: #c9d1d9; font-size: 11px; }}
  </style>
  <rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="10" fill="#0d1117" stroke="#30363d"/>
  <rect x="1" y="1" width="5" height="{height - 2}" rx="3" fill="url(#accent)"/>
  <text x="22" y="27" class="title">{safe_title}</text>
{body}
</svg>
'''


def activity_card(profile: dict, repositories: list[dict]) -> str:
    values = [
        (len(repositories), "Public repositories"),
        (sum(repo.get("stargazers_count", 0) for repo in repositories), "Total stars"),
        (sum(repo.get("forks_count", 0) for repo in repositories), "Total forks"),
        (profile.get("followers", 0), "Followers"),
    ]
    positions = [(22, 61), (216, 61), (22, 118), (216, 118)]
    body = [
        '  <circle cx="384" cy="22" r="4" fill="#22d3ee" opacity=".9"/>',
        '  <circle cx="370" cy="22" r="4" fill="#a855f7" opacity=".9"/>',
    ]
    for (value, label), (x, y) in zip(values, positions):
        body.append(f'  <text x="{x}" y="{y}" class="value">{value:,}</text>')
        body.append(f'  <text x="{x}" y="{y + 18}" class="label">{html.escape(label)}</text>')
    return svg_document("GitHub Activity", "\n".join(body))


def language_totals(repositories: list[dict]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for repository in repositories:
        languages = api_get(f"/repos/{repository['full_name']}/languages")
        for language, byte_count in languages.items():
            totals[language] = totals.get(language, 0) + int(byte_count)
    return totals


def languages_card(totals: dict[str, int]) -> str:
    ranked = sorted(totals.items(), key=lambda item: (-item[1], item[0]))[:5]
    grand_total = sum(totals.values())
    body = []

    if not ranked or grand_total == 0:
        body.append('  <text x="18" y="72" class="label">No language data available</text>')
        return svg_document("Top Languages", "\n".join(body))

    for index, (language, byte_count) in enumerate(ranked):
        y = 51 + index * 22
        percentage = byte_count / grand_total * 100
        color = COLORS[index % len(COLORS)]
        bar_width = max(2.0, 142 * percentage / 100)
        body.extend(
            [
                f'  <circle cx="23" cy="{y - 4}" r="4" fill="{color}"/>',
                f'  <text x="34" y="{y}" class="language">{html.escape(language)}</text>',
                f'  <rect x="194" y="{y - 9}" width="142" height="6" rx="3" fill="#21262d"/>',
                f'  <rect x="194" y="{y - 9}" width="{bar_width:.1f}" height="6" rx="3" fill="{color}"/>',
                f'  <text x="390" y="{y}" text-anchor="end" class="label">{percentage:.1f}%</text>',
            ]
        )
    return svg_document("Top Languages", "\n".join(body))


def write_if_changed(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    path.write_text(content, encoding="utf-8")
    print(f"updated {path.relative_to(OUTPUT_DIR.parent)}")


def main() -> int:
    username = os.environ.get("GITHUB_REPOSITORY_OWNER", "shilongWang1107")
    profile = api_get(f"/users/{username}")
    repositories = public_repositories(username)
    languages = language_totals(repositories)

    write_if_changed(OUTPUT_DIR / "github-activity.svg", activity_card(profile, repositories))
    write_if_changed(OUTPUT_DIR / "top-languages.svg", languages_card(languages))
    return 0


if __name__ == "__main__":
    sys.exit(main())
