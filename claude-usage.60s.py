#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Claude Code Usage Monitor - SwiftBar Plugin
Fetches plan type from API and calculates usage from local session data.
"""

import json
import glob
import subprocess
import os
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path

CLAUDE_DIR = Path.home() / ".claude"
PROJECTS_DIR = CLAUDE_DIR / "projects"

# Calibrated limits per plan tier (based on real /status observations)
# These are rough estimates - adjust based on your experience
PLAN_LIMITS = {
    "default_claude_max_20x": {
        "name": "Max 20x",
        "session_prompts": 800,      # ~200-800 range
        "weekly_opus_tokens": 1_400_000_000,
        "weekly_sonnet_tokens": 4_000_000_000,
    },
    "default_claude_max_5x": {
        "name": "Max 5x",
        "session_prompts": 372,      # ~93 prompts = 25%
        "weekly_opus_tokens": 1_400_000_000,
        "weekly_sonnet_tokens": 4_000_000_000,
    },
    "default_claude_pro": {
        "name": "Pro",
        "session_prompts": 150,      # ~10-40 range, being generous
        "weekly_opus_tokens": 500_000_000,
        "weekly_sonnet_tokens": 2_000_000_000,
    },
}

DEFAULT_LIMITS = PLAN_LIMITS["default_claude_max_5x"]

WEEKLY_RESET_WEEKDAY = 3  # Thursday
WEEKLY_RESET_HOUR = 3     # 3:00 AM

# Colors
GREEN = "#22c55e"
YELLOW = "#eab308"
ORANGE = "#f97316"
RED = "#ef4444"
GRAY = "#6b7280"


def get_color(pct: float) -> str:
    if pct < 50: return GREEN
    if pct < 75: return YELLOW
    if pct < 90: return ORANGE
    return RED


def get_oauth_token():
    """Extract OAuth token from macOS Keychain."""
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-a", os.environ.get("USER", ""),
             "-s", "Claude Code-credentials", "-w"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            creds = json.loads(result.stdout.strip())
            return creds.get("claudeAiOauth", {}).get("accessToken")
    except:
        pass
    return None


def fetch_plan_info():
    """Fetch plan type from Anthropic API."""
    token = get_oauth_token()
    if not token:
        return None

    try:
        req = urllib.request.Request(
            "https://api.anthropic.com/api/oauth/profile",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "anthropic-beta": "oauth-2025-04-20",
                "User-Agent": "claude-cli/2.0.76"
            }
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            return {
                "rate_limit_tier": data.get("organization", {}).get("rate_limit_tier"),
                "org_type": data.get("organization", {}).get("organization_type"),
                "display_name": data.get("account", {}).get("display_name"),
            }
    except:
        return None


def get_limits_for_tier(tier: str) -> dict:
    """Get calibrated limits based on plan tier."""
    return PLAN_LIMITS.get(tier, DEFAULT_LIMITS)


def get_weekly_start() -> datetime:
    """Calculate when the current weekly window started (last Thursday 3AM)."""
    now = datetime.now(timezone.utc)
    days_since_thursday = (now.weekday() - WEEKLY_RESET_WEEKDAY) % 7
    if days_since_thursday == 0 and now.hour < WEEKLY_RESET_HOUR:
        days_since_thursday = 7
    last_thursday = now - timedelta(days=days_since_thursday)
    return last_thursday.replace(hour=WEEKLY_RESET_HOUR, minute=0, second=0, microsecond=0)


def get_session_start() -> datetime:
    """Find when the current 5-hour session started."""
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
    """Parse usage from local session files."""
    data = {
        "prompts": 0,
        "opus_tokens": 0,
        "sonnet_tokens": 0,
        "haiku_tokens": 0,
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

                        # Count user prompts
                        if e.get("type") == "user":
                            msg = e.get("message", {})
                            content = msg.get("content", "")
                            if isinstance(content, str) and content.strip():
                                data["prompts"] += 1
                            elif isinstance(content, list):
                                if any(c.get("type") == "text" for c in content if isinstance(c, dict)):
                                    data["prompts"] += 1

                        # Count token usage
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

    # Fetch plan info from API
    plan_info = fetch_plan_info()
    tier = plan_info.get("rate_limit_tier") if plan_info else None
    limits = get_limits_for_tier(tier) if tier else DEFAULT_LIMITS
    plan_name = limits["name"]

    # Calculate time windows
    session_start = get_session_start()
    weekly_start = get_weekly_start()

    # Calculate reset times
    session_elapsed = now - session_start
    session_remaining = timedelta(hours=5) - session_elapsed
    if session_remaining.total_seconds() < 0:
        session_remaining = timedelta(0)

    days_until_thursday = (WEEKLY_RESET_WEEKDAY - now.weekday()) % 7
    if days_until_thursday == 0 and now.hour >= WEEKLY_RESET_HOUR:
        days_until_thursday = 7
    next_reset = now.replace(hour=WEEKLY_RESET_HOUR, minute=0, second=0, microsecond=0) + timedelta(days=days_until_thursday)
    weekly_remaining = next_reset - now

    # Parse usage
    session = parse_usage(session_start)
    weekly = parse_usage(weekly_start)

    # Calculate percentages
    session_pct = min(100, (session["prompts"] / limits["session_prompts"]) * 100) if limits["session_prompts"] > 0 else 0

    opus_pct = min(100, (weekly["opus_tokens"] / limits["weekly_opus_tokens"]) * 100) if limits["weekly_opus_tokens"] > 0 else 0
    sonnet_pct = min(100, (weekly["sonnet_tokens"] / limits["weekly_sonnet_tokens"]) * 100) if limits["weekly_sonnet_tokens"] > 0 else 0

    # Use highest as "all models" estimate
    weekly_pct = max(opus_pct, sonnet_pct)

    # Overall = worse of session or weekly
    overall_pct = max(session_pct, weekly_pct)

    # Menu bar display
    color = get_color(overall_pct)
    if overall_pct >= 90:
        icon = "exclamationmark.triangle.fill"
    elif overall_pct >= 75:
        icon = "exclamationmark.circle.fill"
    else:
        icon = "chart.bar.fill"

    print(f"{overall_pct:.0f}% | sfSymbol={icon} sfcolor={color}")
    print("---")

    # Plan info
    api_status = "API" if plan_info else "cached"
    print(f"Claude Code ({plan_name}) | color={GRAY}")
    print(f"--Source: {api_status} | color={GRAY}")

    # Session
    print("---")
    session_color = get_color(session_pct)
    print(f"Session: {session_pct:.0f}% | color={session_color}")
    print(f"--{session['prompts']}/{limits['session_prompts']} prompts | color={GRAY}")
    print(f"--Resets in {fmt_time(session_remaining)} | color={GRAY}")

    # Weekly
    print("---")
    print(f"Weekly: {weekly_pct:.0f}% | color={get_color(weekly_pct)}")

    if weekly["opus_tokens"] > 0 or opus_pct > 0:
        print(f"--Opus: {opus_pct:.0f}% ({fmt_tokens(weekly['opus_tokens'])}) | color={get_color(opus_pct)}")

    if weekly["sonnet_tokens"] > 0 or sonnet_pct > 0:
        print(f"--Sonnet: {sonnet_pct:.0f}% ({fmt_tokens(weekly['sonnet_tokens'])}) | color={get_color(sonnet_pct)}")

    if weekly["haiku_tokens"] > 0:
        print(f"--Haiku: {fmt_tokens(weekly['haiku_tokens'])} | color={GRAY}")

    print(f"--Resets in {fmt_time(weekly_remaining)} | color={GRAY}")

    # Actions
    print("---")
    print("Refresh | refresh=true sfSymbol=arrow.clockwise")
    print(f"Run /status for exact numbers | color={GRAY} size=11")


if __name__ == "__main__":
    main()
