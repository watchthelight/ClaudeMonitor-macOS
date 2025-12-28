#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Claude Code Usage Monitor - SwiftBar Plugin
============================================
Displays Claude Code usage stats in the macOS menu bar.

Installation:
1. Install SwiftBar: brew install swiftbar
2. Copy this file to your SwiftBar plugins folder
3. Make executable: chmod +x claude-usage.60s.py

The .60s in the filename means it refreshes every 60 seconds.
"""

import json
import os
import glob
from datetime import datetime, timedelta, timezone
from pathlib import Path
from collections import defaultdict

# Configuration
CLAUDE_DIR = Path.home() / ".claude"
PROJECTS_DIR = CLAUDE_DIR / "projects"

# Estimated limits (adjust based on your plan)
# These are rough estimates - actual limits vary by usage patterns
PLANS = {
    "pro": {
        "name": "Pro",
        "weekly_sonnet_hours": 60,  # Middle estimate: 40-80
        "five_hour_messages": 25,   # Middle estimate: 10-40
    },
    "max5x": {
        "name": "Max 5x",
        "weekly_sonnet_hours": 210,  # Middle estimate: 140-280
        "five_hour_messages": 125,   # Middle estimate: 50-200
    },
    "max20x": {
        "name": "Max 20x",
        "weekly_sonnet_hours": 360,  # Middle estimate: 240-480
        "five_hour_messages": 500,   # Middle estimate: 200-800
    },
}

# Default plan - change this to match your subscription
CURRENT_PLAN = "max5x"

# Token costs for time estimation (approximate)
# 1 "Sonnet hour" ≈ cost of running Sonnet continuously
# Rough estimate: 1M tokens/hour at full speed
TOKENS_PER_SONNET_HOUR = 1_000_000

# Colors for SwiftBar
COLORS = {
    "green": "#22c55e",
    "yellow": "#eab308",
    "orange": "#f97316",
    "red": "#ef4444",
    "blue": "#3b82f6",
    "gray": "#6b7280",
}

# SF Symbols for SwiftBar
ICONS = {
    "healthy": "checkmark.circle.fill",
    "warning": "exclamationmark.triangle.fill",
    "critical": "xmark.octagon.fill",
    "clock": "clock.fill",
    "chart": "chart.bar.fill",
}


def parse_session_files(since_time: datetime) -> dict:
    """Parse all session JSONL files and extract usage data since given time."""
    usage_data = {
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_cache_read_tokens": 0,
        "total_cache_creation_tokens": 0,
        "user_prompt_count": 0,  # Actual user prompts (what limits track)
        "api_call_count": 0,     # API calls (includes tool use, etc)
        "sessions": set(),
        "models": defaultdict(lambda: {"input": 0, "output": 0, "calls": 0}),
        "oldest_message": None,
        "newest_message": None,
    }

    if not PROJECTS_DIR.exists():
        return usage_data

    # Find all .jsonl files in projects subdirectories
    pattern = str(PROJECTS_DIR / "*" / "*.jsonl")
    session_files = glob.glob(pattern)

    for filepath in session_files:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    # Check timestamp first for efficiency
                    timestamp_str = entry.get("timestamp")
                    if not timestamp_str:
                        continue

                    try:
                        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    except (ValueError, AttributeError):
                        continue

                    # Skip if before our window
                    if timestamp < since_time:
                        continue

                    entry_type = entry.get("type")

                    # Count user prompts (this is what the 5-hour limit tracks)
                    if entry_type == "user":
                        message = entry.get("message", {})
                        content = message.get("content", "")
                        # Only count actual user messages, not tool results
                        if isinstance(content, str) and content.strip():
                            usage_data["user_prompt_count"] += 1
                        elif isinstance(content, list):
                            # Check if it's a user message (not tool_result)
                            has_user_text = any(
                                c.get("type") == "text" for c in content
                                if isinstance(c, dict)
                            )
                            if has_user_text:
                                usage_data["user_prompt_count"] += 1

                    # Count API usage from assistant responses
                    if entry_type == "assistant":
                        message = entry.get("message", {})
                        usage = message.get("usage", {})
                        model = message.get("model", "unknown")

                        if usage:
                            input_tokens = usage.get("input_tokens", 0)
                            output_tokens = usage.get("output_tokens", 0)
                            cache_read = usage.get("cache_read_input_tokens", 0)
                            cache_creation = usage.get("cache_creation_input_tokens", 0)

                            usage_data["total_input_tokens"] += input_tokens
                            usage_data["total_output_tokens"] += output_tokens
                            usage_data["total_cache_read_tokens"] += cache_read
                            usage_data["total_cache_creation_tokens"] += cache_creation
                            usage_data["api_call_count"] += 1
                            usage_data["models"][model]["input"] += input_tokens + cache_creation
                            usage_data["models"][model]["output"] += output_tokens
                            usage_data["models"][model]["calls"] += 1

                            session_id = entry.get("sessionId")
                            if session_id:
                                usage_data["sessions"].add(session_id)

                            # Track time range
                            if usage_data["oldest_message"] is None or timestamp < usage_data["oldest_message"]:
                                usage_data["oldest_message"] = timestamp
                            if usage_data["newest_message"] is None or timestamp > usage_data["newest_message"]:
                                usage_data["newest_message"] = timestamp

        except (IOError, PermissionError):
            continue

    return usage_data


def format_tokens(count: int) -> str:
    """Format token count in human-readable form."""
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    elif count >= 1_000:
        return f"{count / 1_000:.1f}K"
    return str(count)


def format_duration(td: timedelta) -> str:
    """Format timedelta as human-readable string."""
    total_seconds = int(td.total_seconds())
    if total_seconds < 0:
        return "now"

    hours, remainder = divmod(total_seconds, 3600)
    minutes, _ = divmod(remainder, 60)

    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def get_usage_color(percentage: float) -> str:
    """Get color based on usage percentage."""
    if percentage < 50:
        return COLORS["green"]
    elif percentage < 75:
        return COLORS["yellow"]
    elif percentage < 90:
        return COLORS["orange"]
    return COLORS["red"]


def get_status_icon(percentage: float) -> str:
    """Get SF Symbol based on usage percentage."""
    if percentage < 75:
        return ICONS["healthy"]
    elif percentage < 90:
        return ICONS["warning"]
    return ICONS["critical"]


def calculate_reset_times(now: datetime) -> dict:
    """Calculate when limits reset."""
    # 5-hour rolling window - we estimate based on oldest message in window
    # Weekly reset - typically Sunday midnight or 7 days from first usage

    # For simplicity, we'll show time remaining in current windows
    five_hour_ago = now - timedelta(hours=5)
    week_ago = now - timedelta(days=7)

    # The 5-hour window is rolling, so it's always "up to 5 hours"
    # The weekly window resets... we don't know exactly when without API data
    # We'll estimate based on common patterns (Sunday midnight)

    # Find next Sunday midnight
    days_until_sunday = (6 - now.weekday()) % 7
    if days_until_sunday == 0 and now.hour >= 0:
        days_until_sunday = 7
    next_sunday = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=days_until_sunday)

    return {
        "five_hour_window_resets_in": timedelta(hours=5),  # Rolling, always 5h max
        "weekly_resets_at": next_sunday,
        "weekly_resets_in": next_sunday - now,
    }


def main():
    now = datetime.now(timezone.utc)
    plan = PLANS[CURRENT_PLAN]

    # Calculate time windows
    five_hours_ago = now - timedelta(hours=5)
    week_ago = now - timedelta(days=7)

    # Get usage for both windows
    five_hour_usage = parse_session_files(five_hours_ago)
    weekly_usage = parse_session_files(week_ago)

    # Estimate usage as percentage of limits
    # Using output tokens as primary metric (most representative of cost)
    total_weekly_tokens = (
        weekly_usage["total_input_tokens"] +
        weekly_usage["total_output_tokens"] +
        weekly_usage["total_cache_creation_tokens"]
    )

    total_5h_tokens = (
        five_hour_usage["total_input_tokens"] +
        five_hour_usage["total_output_tokens"] +
        five_hour_usage["total_cache_creation_tokens"]
    )

    # Estimate percentage (rough - based on token to Sonnet-hour conversion)
    weekly_limit_tokens = plan["weekly_sonnet_hours"] * TOKENS_PER_SONNET_HOUR
    weekly_pct = min(100, (total_weekly_tokens / weekly_limit_tokens) * 100) if weekly_limit_tokens > 0 else 0

    # 5-hour is message-based estimate (user prompts only)
    five_hour_pct = min(100, (five_hour_usage["user_prompt_count"] / plan["five_hour_messages"]) * 100) if plan["five_hour_messages"] > 0 else 0

    # Get the worse of the two for overall status
    overall_pct = max(weekly_pct, five_hour_pct)

    # Reset times
    resets = calculate_reset_times(now)

    # ===== SwiftBar Output =====

    # Menu bar title
    status_color = get_usage_color(overall_pct)
    status_icon = get_status_icon(overall_pct)

    if overall_pct >= 90:
        title_text = f"CC: {overall_pct:.0f}%"
    elif overall_pct >= 50:
        title_text = f"CC: {overall_pct:.0f}%"
    else:
        title_text = "CC"

    print(f"{title_text} | sfSymbol={status_icon} sfcolor={status_color}")
    print("---")

    # Header
    print(f"Claude Code Usage ({plan['name']}) | size=14 color={COLORS['blue']}")
    print("---")

    # 5-Hour Rolling Window
    print(f"5-Hour Window | sfSymbol=clock color={COLORS['gray']}")
    five_hour_color = get_usage_color(five_hour_pct)
    print(f"-- {five_hour_usage['user_prompt_count']}/{plan['five_hour_messages']} prompts ({five_hour_pct:.0f}%) | color={five_hour_color}")
    print(f"-- API calls: {five_hour_usage['api_call_count']} | color={COLORS['gray']}")
    print(f"-- Tokens: {format_tokens(total_5h_tokens)} | color={COLORS['gray']}")
    print(f"-- Resets: Rolling (oldest prompt expires) | color={COLORS['gray']}")

    # Weekly Limit
    print("---")
    print(f"Weekly Usage | sfSymbol=calendar color={COLORS['gray']}")
    weekly_color = get_usage_color(weekly_pct)
    print(f"-- ~{weekly_pct:.0f}% of {plan['weekly_sonnet_hours']}h Sonnet limit | color={weekly_color}")
    print(f"-- Tokens: {format_tokens(total_weekly_tokens)} | color={COLORS['gray']}")
    print(f"-- Sessions: {len(weekly_usage['sessions'])} | color={COLORS['gray']}")
    print(f"-- Resets in: {format_duration(resets['weekly_resets_in'])} | color={COLORS['gray']}")

    # Model breakdown
    if weekly_usage["models"]:
        print("---")
        print(f"By Model (Weekly) | sfSymbol=cpu color={COLORS['gray']}")
        for model, tokens in sorted(weekly_usage["models"].items()):
            total = tokens["input"] + tokens["output"]
            model_short = model.replace("claude-", "").replace("-20251101", "").replace("-20250929", "")
            print(f"-- {model_short}: {format_tokens(total)} | color={COLORS['gray']}")

    # Quick stats
    print("---")
    if weekly_usage["newest_message"]:
        time_since = now - weekly_usage["newest_message"]
        print(f"Last activity: {format_duration(time_since)} ago | color={COLORS['gray']}")

    # Actions
    print("---")
    print(f"Refresh | refresh=true sfSymbol=arrow.clockwise")
    print(f"Open ~/.claude | bash='open' param1='{CLAUDE_DIR}' terminal=false")

    # Footer
    print("---")
    print(f"Note: Estimates based on local data | size=10 color={COLORS['gray']}")
    print(f"Actual limits may vary | size=10 color={COLORS['gray']}")


if __name__ == "__main__":
    main()
