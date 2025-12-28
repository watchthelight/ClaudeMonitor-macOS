#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Claude Code Usage Monitor - SwiftBar Plugin
Fetches real usage percentages directly from the Anthropic API.
"""

import json
import subprocess
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone

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


def fetch_usage():
    """Fetch real usage data from Anthropic API."""
    token = get_oauth_token()
    if not token:
        return None

    try:
        req = urllib.request.Request(
            "https://api.anthropic.com/api/oauth/usage",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "anthropic-beta": "oauth-2025-04-20",
                "User-Agent": "claude-cli/2.0.76"
            }
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except:
        return None


def fmt_time_until(iso_str: str) -> str:
    """Format time remaining until reset."""
    try:
        reset_time = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        delta = reset_time - now
        secs = int(delta.total_seconds())
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
    except:
        return "?"


def main():
    usage = fetch_usage()

    if not usage:
        print("? | sfSymbol=exclamationmark.triangle sfcolor=#ef4444")
        print("---")
        print("Failed to fetch usage | color=#ef4444")
        print("--Check Claude Code login | color=#6b7280")
        print("---")
        print("Refresh | refresh=true sfSymbol=arrow.clockwise")
        return

    # Extract data from API response
    session_pct = usage.get("five_hour", {}).get("utilization", 0) or 0
    session_reset = usage.get("five_hour", {}).get("resets_at", "")

    weekly_pct = usage.get("seven_day", {}).get("utilization", 0) or 0
    weekly_reset = usage.get("seven_day", {}).get("resets_at", "")

    sonnet_data = usage.get("seven_day_sonnet") or {}
    sonnet_pct = sonnet_data.get("utilization", 0) or 0

    opus_data = usage.get("seven_day_opus") or {}
    opus_pct = opus_data.get("utilization", 0) or 0

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

    # Session (5-hour)
    session_color = get_color(session_pct)
    print(f"Session: {session_pct:.0f}% | color={session_color}")
    if session_reset:
        print(f"--Resets in {fmt_time_until(session_reset)} | color={GRAY}")

    # Weekly (7-day)
    print("---")
    weekly_color = get_color(weekly_pct)
    print(f"Weekly: {weekly_pct:.0f}% | color={weekly_color}")

    if opus_pct > 0:
        print(f"--Opus: {opus_pct:.0f}% | color={get_color(opus_pct)}")

    if sonnet_pct > 0:
        print(f"--Sonnet: {sonnet_pct:.0f}% | color={get_color(sonnet_pct)}")

    if weekly_reset:
        print(f"--Resets in {fmt_time_until(weekly_reset)} | color={GRAY}")

    # Actions
    print("---")
    print("Refresh | refresh=true sfSymbol=arrow.clockwise")


if __name__ == "__main__":
    main()
