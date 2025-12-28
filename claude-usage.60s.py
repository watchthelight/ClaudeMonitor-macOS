#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Claude Code Usage Monitor - SwiftBar Plugin
Shows usage percentages based on calibrated limits.
"""

import json
import glob
from datetime import datetime, timedelta, timezone
from pathlib import Path
from collections import defaultdict

CLAUDE_DIR = Path.home() / ".claude"
PROJECTS_DIR = CLAUDE_DIR / "projects"

# =============================================================================
# CALIBRATION - Adjust these based on your /status readings
# =============================================================================
# Session limit (5-hour rolling window) - in prompts
SESSION_PROMPT_LIMIT = 372  # ~93 prompts = 25%

# Weekly limits - in tokens (input + output + cache_write)
WEEKLY_OPUS_LIMIT = 1_400_000_000    # ~263M = 19%
WEEKLY_SONNET_LIMIT = 4_000_000_000  # ~40M = 1%
WEEKLY_HAIKU_LIMIT = 10_000_000_000  # Haiku has very high limits

# Weekly reset: Thursday 3:00 AM local time
WEEKLY_RESET_WEEKDAY = 3  # Thursday (0=Monday)
WEEKLY_RESET_HOUR = 3

# =============================================================================

# Colors
GREEN = "#22c55e"
YELLOW = "#eab308"
ORANGE = "#f97316"
RED = "#ef4444"
BLUE = "#3b82f6"
GRAY = "#6b7280"
WHITE = "#f4f4f5"


def get_color(pct: float) -> str:
    if pct < 50:
        return GREEN
    elif pct < 75:
        return YELLOW
    elif pct < 90:
        return ORANGE
    return RED


def get_weekly_start() -> datetime:
    """Calculate when the current weekly window started (last Thursday 3AM)."""
    now = datetime.now(timezone.utc)
    days_since_thursday = (now.weekday() - WEEKLY_RESET_WEEKDAY) % 7
    if days_since_thursday == 0 and now.hour < WEEKLY_RESET_HOUR:
        days_since_thursday = 7

    last_thursday = now - timedelta(days=days_since_thursday)
    return last_thursday.replace(hour=WEEKLY_RESET_HOUR, minute=0, second=0, microsecond=0)


def get_session_start() -> datetime:
    """Estimate session start by finding oldest message in last 5 hours."""
    now = datetime.now(timezone.utc)
    five_hours_ago = now - timedelta(hours=5)
    oldest = None

    for fp in glob.glob(str(PROJECTS_DIR / "*" / "*.jsonl")):
        try:
            with open(fp, 'r') as f:
                for line in f:
                    try:
                        e = json.loads(line)
                        ts_str = e.get("timestamp")
                        if not ts_str:
                            continue
                        ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                        if ts >= five_hours_ago:
                            if oldest is None or ts < oldest:
                                oldest = ts
                    except:
                        continue
        except:
            continue

    return oldest or five_hours_ago


def parse_usage(since: datetime) -> dict:
    """Parse usage since given time."""
    data = {
        "prompts": 0,
        "opus_tokens": 0,
        "sonnet_tokens": 0,
        "haiku_tokens": 0,
        "other_tokens": 0,
    }

    for fp in glob.glob(str(PROJECTS_DIR / "*" / "*.jsonl")):
        try:
            with open(fp, 'r') as f:
                for line in f:
                    try:
                        e = json.loads(line)
                        ts_str = e.get("timestamp")
                        if not ts_str:
                            continue
                        ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                        if ts < since:
                            continue

                        if e.get("type") == "user":
                            msg = e.get("message", {})
                            content = msg.get("content", "")
                            if isinstance(content, str) and content.strip():
                                data["prompts"] += 1
                            elif isinstance(content, list):
                                if any(c.get("type") == "text" for c in content if isinstance(c, dict)):
                                    data["prompts"] += 1

                        if e.get("type") == "assistant":
                            u = e.get("message", {}).get("usage", {})
                            model = e.get("message", {}).get("model", "").lower()
                            if u:
                                tokens = (u.get("input_tokens", 0) +
                                         u.get("output_tokens", 0) +
                                         u.get("cache_creation_input_tokens", 0))

                                if "opus" in model:
                                    data["opus_tokens"] += tokens
                                elif "sonnet" in model:
                                    data["sonnet_tokens"] += tokens
                                elif "haiku" in model:
                                    data["haiku_tokens"] += tokens
                                else:
                                    data["other_tokens"] += tokens
                    except:
                        continue
        except:
            continue

    return data


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


def fmt_tokens(n: int) -> str:
    if n >= 1_000_000_000:
        return f"{n/1_000_000_000:.1f}B"
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.0f}K"
    return str(n)


def main():
    now = datetime.now(timezone.utc)

    # Get time boundaries
    session_start = get_session_start()
    weekly_start = get_weekly_start()

    # Calculate resets
    session_elapsed = now - session_start
    session_remaining = timedelta(hours=5) - session_elapsed
    if session_remaining.total_seconds() < 0:
        session_remaining = timedelta(0)

    # Next Thursday 3AM
    days_until_thursday = (WEEKLY_RESET_WEEKDAY - now.weekday()) % 7
    if days_until_thursday == 0 and now.hour >= WEEKLY_RESET_HOUR:
        days_until_thursday = 7
    next_reset = now.replace(hour=WEEKLY_RESET_HOUR, minute=0, second=0, microsecond=0) + timedelta(days=days_until_thursday)
    weekly_remaining = next_reset - now

    # Get usage
    session = parse_usage(session_start)
    weekly = parse_usage(weekly_start)

    # Calculate percentages
    session_pct = min(100, (session["prompts"] / SESSION_PROMPT_LIMIT) * 100) if SESSION_PROMPT_LIMIT > 0 else 0

    weekly_opus_pct = min(100, (weekly["opus_tokens"] / WEEKLY_OPUS_LIMIT) * 100) if WEEKLY_OPUS_LIMIT > 0 else 0
    weekly_sonnet_pct = min(100, (weekly["sonnet_tokens"] / WEEKLY_SONNET_LIMIT) * 100) if WEEKLY_SONNET_LIMIT > 0 else 0

    # Combined weekly (weighted by actual limit proportions)
    total_weekly_tokens = weekly["opus_tokens"] + weekly["sonnet_tokens"] + weekly["haiku_tokens"]
    # Use opus percentage as primary since it's usually the constraint
    weekly_pct = max(weekly_opus_pct, weekly_sonnet_pct)

    # Overall status (worse of session or weekly)
    overall_pct = max(session_pct, weekly_pct)

    # Menu bar - show percentage
    color = get_color(overall_pct)
    if overall_pct >= 90:
        icon = "exclamationmark.triangle.fill"
    elif overall_pct >= 75:
        icon = "exclamationmark.circle.fill"
    else:
        icon = "chart.bar.fill"

    print(f"{overall_pct:.0f}% | sfSymbol={icon} sfcolor={color}")
    print("---")

    # Session
    session_color = get_color(session_pct)
    print(f"Session: {session_pct:.0f}% | color={session_color}")
    print(f"--{session['prompts']}/{SESSION_PROMPT_LIMIT} prompts | color={GRAY}")
    print(f"--Resets in {fmt_time(session_remaining)} | color={GRAY}")

    # Weekly
    print("---")
    print(f"Weekly: {weekly_pct:.0f}% | color={get_color(weekly_pct)}")

    opus_color = get_color(weekly_opus_pct)
    print(f"--Opus: {weekly_opus_pct:.0f}% ({fmt_tokens(weekly['opus_tokens'])}) | color={opus_color}")

    sonnet_color = get_color(weekly_sonnet_pct)
    print(f"--Sonnet: {weekly_sonnet_pct:.0f}% ({fmt_tokens(weekly['sonnet_tokens'])}) | color={sonnet_color}")

    if weekly["haiku_tokens"] > 0:
        print(f"--Haiku: {fmt_tokens(weekly['haiku_tokens'])} | color={GRAY}")

    print(f"--Resets {fmt_time(weekly_remaining)} | color={GRAY}")

    # Actions
    print("---")
    print(f"Refresh | refresh=true sfSymbol=arrow.clockwise")
    print(f"Run /status for exact numbers | color={GRAY} size=11")


if __name__ == "__main__":
    main()
