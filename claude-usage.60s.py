#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Claude Code Usage Monitor - SwiftBar Plugin
============================================
Displays Claude Code usage statistics from local session data.

NOTE: This shows LOCAL usage data only. Actual subscription limits
are tracked server-side by Anthropic. Use /status in Claude Code
for official quota information.
"""

import json
import os
import glob
from datetime import datetime, timedelta, timezone
from pathlib import Path
from collections import defaultdict

CLAUDE_DIR = Path.home() / ".claude"
PROJECTS_DIR = CLAUDE_DIR / "projects"

# Colors
GREEN = "#22c55e"
YELLOW = "#eab308"
ORANGE = "#f97316"
RED = "#ef4444"
BLUE = "#3b82f6"
GRAY = "#6b7280"
WHITE = "#f4f4f5"


def parse_session_files(since_time: datetime) -> dict:
    """Parse session JSONL files and extract usage data."""
    usage = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read": 0,
        "cache_write": 0,
        "api_calls": 0,
        "user_turns": 0,
        "sessions": set(),
        "models": defaultdict(lambda: {"input": 0, "output": 0, "calls": 0}),
        "last_activity": None,
        "first_activity": None,
    }

    if not PROJECTS_DIR.exists():
        return usage

    for filepath in glob.glob(str(PROJECTS_DIR / "*" / "*.jsonl")):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    ts_str = entry.get("timestamp")
                    if not ts_str:
                        continue

                    try:
                        ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                    except:
                        continue

                    if ts < since_time:
                        continue

                    entry_type = entry.get("type")

                    # Count user turns (your actual prompts)
                    if entry_type == "user":
                        msg = entry.get("message", {})
                        content = msg.get("content", "")
                        # Only count real user messages, not tool results
                        if isinstance(content, str) and content.strip():
                            usage["user_turns"] += 1
                        elif isinstance(content, list):
                            if any(c.get("type") == "text" for c in content if isinstance(c, dict)):
                                usage["user_turns"] += 1

                    # Count API usage
                    if entry_type == "assistant":
                        msg = entry.get("message", {})
                        u = msg.get("usage", {})
                        model = msg.get("model", "unknown")

                        if u:
                            inp = u.get("input_tokens", 0)
                            out = u.get("output_tokens", 0)
                            cr = u.get("cache_read_input_tokens", 0)
                            cw = u.get("cache_creation_input_tokens", 0)

                            usage["input_tokens"] += inp
                            usage["output_tokens"] += out
                            usage["cache_read"] += cr
                            usage["cache_write"] += cw
                            usage["api_calls"] += 1

                            usage["models"][model]["input"] += inp + cw
                            usage["models"][model]["output"] += out
                            usage["models"][model]["calls"] += 1

                            sid = entry.get("sessionId")
                            if sid:
                                usage["sessions"].add(sid)

                            if not usage["first_activity"] or ts < usage["first_activity"]:
                                usage["first_activity"] = ts
                            if not usage["last_activity"] or ts > usage["last_activity"]:
                                usage["last_activity"] = ts

        except (IOError, PermissionError):
            continue

    return usage


def fmt_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.0f}K"
    return str(n)


def fmt_time(td: timedelta) -> str:
    secs = int(td.total_seconds())
    if secs < 0:
        return "now"
    h, r = divmod(secs, 3600)
    m, _ = divmod(r, 60)
    if h > 24:
        d = h // 24
        h = h % 24
        return f"{d}d {h}h"
    if h > 0:
        return f"{h}h {m}m"
    return f"{m}m"


def main():
    now = datetime.now(timezone.utc)

    # Time windows
    h5_ago = now - timedelta(hours=5)
    h24_ago = now - timedelta(hours=24)
    d7_ago = now - timedelta(days=7)

    # Get usage for different periods
    h5 = parse_session_files(h5_ago)
    h24 = parse_session_files(h24_ago)
    d7 = parse_session_files(d7_ago)

    # Calculate totals
    h5_total = h5["input_tokens"] + h5["output_tokens"] + h5["cache_write"]
    h24_total = h24["input_tokens"] + h24["output_tokens"] + h24["cache_write"]
    d7_total = d7["input_tokens"] + d7["output_tokens"] + d7["cache_write"]

    # Menu bar title - just show recent activity indicator
    if h5["api_calls"] > 0:
        icon = "bolt.fill"
        color = BLUE
    else:
        icon = "moon.fill"
        color = GRAY

    print(f"CC | sfSymbol={icon} sfcolor={color}")
    print("---")

    # Header
    print(f"Claude Code Usage | color={WHITE}")
    print(f"Local data only • /status for limits | size=11 color={GRAY}")
    print("---")

    # 5-Hour Window
    print(f"Last 5 Hours | sfSymbol=clock color={GRAY}")
    print(f"--Prompts: {h5['user_turns']} | color={WHITE}")
    print(f"--API Calls: {h5['api_calls']} | color={GRAY}")
    print(f"--Tokens: {fmt_tokens(h5_total)} (in: {fmt_tokens(h5['input_tokens'])}, out: {fmt_tokens(h5['output_tokens'])}) | color={GRAY}")
    print(f"--Cache: {fmt_tokens(h5['cache_read'])} read, {fmt_tokens(h5['cache_write'])} written | color={GRAY}")

    # 24-Hour Window
    print("---")
    print(f"Last 24 Hours | sfSymbol=calendar color={GRAY}")
    print(f"--Prompts: {h24['user_turns']} | color={WHITE}")
    print(f"--API Calls: {h24['api_calls']} | color={GRAY}")
    print(f"--Tokens: {fmt_tokens(h24_total)} | color={GRAY}")
    print(f"--Sessions: {len(h24['sessions'])} | color={GRAY}")

    # 7-Day Window
    print("---")
    print(f"Last 7 Days | sfSymbol=calendar.badge.clock color={GRAY}")
    print(f"--Prompts: {d7['user_turns']} | color={WHITE}")
    print(f"--Tokens: {fmt_tokens(d7_total)} | color={GRAY}")
    print(f"--Sessions: {len(d7['sessions'])} | color={GRAY}")

    # Model breakdown (7d)
    if d7["models"]:
        print("---")
        print(f"By Model (7d) | sfSymbol=cpu color={GRAY}")
        for model, data in sorted(d7["models"].items(), key=lambda x: x[1]["output"], reverse=True):
            if model == "unknown" or data["calls"] == 0:
                continue
            short = model.replace("claude-", "").replace("-20251101", "").replace("-20250929", "").replace("-20251001", "")
            total = data["input"] + data["output"]
            print(f"--{short}: {fmt_tokens(total)} ({data['calls']} calls) | color={GRAY}")

    # Last activity
    print("---")
    if d7["last_activity"]:
        ago = now - d7["last_activity"]
        print(f"Last active: {fmt_time(ago)} ago | color={GRAY}")
    else:
        print(f"No recent activity | color={GRAY}")

    # Actions
    print("---")
    print(f"Refresh | refresh=true sfSymbol=arrow.clockwise")
    print(f"Open ~/.claude | bash=open param1={CLAUDE_DIR} terminal=false")

    # Footer
    print("---")
    print(f"Tip: Run /status in Claude Code | size=11 color={GRAY}")
    print(f"for official limit info | size=11 color={GRAY}")


if __name__ == "__main__":
    main()
