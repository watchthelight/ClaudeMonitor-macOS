#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Claude Code Usage Monitor v2.1 - SwiftBar Plugin
A beautiful, configurable menu bar widget for Claude Code usage.

Features:
- Real API data from Anthropic
- Multiple graph styles (bars, blocks, braille)
- All metrics visible in menu bar
- Smooth color gradients
- Configurable display
"""

import json
import subprocess
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List

# =============================================================================
# Configuration
# =============================================================================

CONFIG_DIR = Path.home() / ".config" / "claude-monitor"
CONFIG_FILE = CONFIG_DIR / "config.json"
CACHE_FILE = CONFIG_DIR / "cache.json"
HISTORY_FILE = CONFIG_DIR / "history.json"

DEFAULT_CONFIG = {
    "version": 2,
    "menubar": {
        "style": "full",           # minimal, compact, full, detailed
        "show_icons": True,        # Show SF Symbols
        "graph_style": "blocks",   # bars, blocks, braille, dots, none
        "graph_width": 8,
    },
    "display": {
        "show_sparkline": True,
        "show_session": True,
        "show_weekly": True,
        "show_models": True,
        "show_resets": True,
        "compact_mode": False
    },
    "thresholds": {
        "green_max": 50,
        "yellow_max": 75,
        "orange_max": 90
    },
    "advanced": {
        "cache_ttl": 3600,
        "retry_count": 3,
        "api_timeout": 10
    }
}

# Graph character sets
GRAPH_STYLES = {
    "bars": " ▁▂▃▄▅▆▇█",
    "blocks": " ▏▎▍▌▋▊▉█",
    "braille": "⠀⣀⣤⣶⣿",
    "dots": "⠀⠄⠆⠇⠏⠟⠿⡿⣿",
    "shades": " ░▒▓█",
}

# Colors (Tailwind-inspired)
COLORS = {
    "green": "#22c55e",
    "lime": "#84cc16",
    "yellow": "#eab308",
    "amber": "#f59e0b",
    "orange": "#f97316",
    "red": "#ef4444",
    "gray": "#6b7280",
    "white": "#f4f4f5",
    "blue": "#3b82f6",
    "purple": "#a855f7",
    "cyan": "#06b6d4",
}


# =============================================================================
# Exceptions
# =============================================================================

class ClaudeMonitorError(Exception):
    """Base exception for Claude Monitor."""
    pass


class KeychainError(ClaudeMonitorError):
    """Failed to access macOS Keychain."""
    pass


class APIError(ClaudeMonitorError):
    """API request failed."""
    pass


class AuthError(APIError):
    """Authentication failed - token expired or invalid."""
    pass


class NetworkError(APIError):
    """Network connectivity issue."""
    pass


# =============================================================================
# Configuration Management
# =============================================================================

def load_config() -> Dict[str, Any]:
    """Load configuration from file, creating defaults if needed."""
    try:
        if CONFIG_FILE.exists():
            config = json.loads(CONFIG_FILE.read_text())
            return deep_merge(DEFAULT_CONFIG, config)
    except (json.JSONDecodeError, IOError):
        pass
    save_config(DEFAULT_CONFIG)
    return DEFAULT_CONFIG.copy()


def save_config(config: Dict[str, Any]) -> None:
    """Save configuration to file."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(config, indent=2))
    except IOError:
        pass


def deep_merge(base: dict, override: dict) -> dict:
    """Deep merge two dictionaries."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


# =============================================================================
# Caching System
# =============================================================================

def load_cached_usage() -> Tuple[Optional[Dict], bool]:
    """Load cached usage data if still valid."""
    try:
        if CACHE_FILE.exists():
            data = json.loads(CACHE_FILE.read_text())
            config = load_config()
            ttl = config.get("advanced", {}).get("cache_ttl", 3600)
            if time.time() - data.get("timestamp", 0) < ttl:
                return data.get("usage"), True
    except (json.JSONDecodeError, IOError):
        pass
    return None, False


def save_usage_cache(usage: Dict) -> None:
    """Cache successful API response."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps({
            "timestamp": time.time(),
            "usage": usage
        }))
    except IOError:
        pass


# =============================================================================
# History Tracking
# =============================================================================

def load_history() -> List[Dict]:
    """Load usage history for graphs."""
    try:
        if HISTORY_FILE.exists():
            data = json.loads(HISTORY_FILE.read_text())
            return data.get("entries", [])
    except (json.JSONDecodeError, IOError):
        pass
    return []


def save_history_entry(session_pct: float, weekly_pct: float) -> None:
    """Save a history entry."""
    try:
        history = load_history()
        now = time.time()

        # Add entry every minute (for better resolution)
        if history and (now - history[-1].get("ts", 0)) < 55:
            return

        history.append({
            "ts": now,
            "session": session_pct,
            "weekly": weekly_pct
        })

        # Keep last 120 entries (2 hours at 1-min intervals)
        history = history[-120:]

        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        HISTORY_FILE.write_text(json.dumps({"entries": history}))
    except IOError:
        pass


# =============================================================================
# Graph Rendering
# =============================================================================

def get_graph(values: List[float], width: int = 8, style: str = "blocks") -> str:
    """Generate a graph from values using specified style."""
    chars = GRAPH_STYLES.get(style, GRAPH_STYLES["blocks"])
    levels = len(chars) - 1

    if not values:
        return chars[0] * width

    values = values[-width:]

    # For absolute percentage display (0-100 scale)
    result = ""
    for v in values:
        v = max(0, min(100, v))
        idx = int(v / 100 * levels)
        result += chars[idx]

    return result.ljust(width, chars[0])


def get_dual_bar(pct1: float, pct2: float, width: int = 10, style: str = "blocks") -> str:
    """Create a dual-colored bar showing two metrics."""
    chars = GRAPH_STYLES.get(style, GRAPH_STYLES["blocks"])
    levels = len(chars) - 1

    pct1 = max(0, min(100, pct1))
    pct2 = max(0, min(100, pct2))

    # Session portion
    session_width = int(pct1 / 100 * width)
    # Weekly portion (shown after session)
    weekly_width = int(pct2 / 100 * width)

    # Build combined bar
    bar = chars[-1] * session_width
    bar = bar.ljust(width, chars[1] if weekly_width > session_width else chars[0])

    return bar


def get_meter(pct: float, width: int = 10, filled: str = "█", empty: str = "░") -> str:
    """Generate a meter/progress bar."""
    pct = max(0, min(100, pct))
    filled_width = int(pct / 100 * width)
    return filled * filled_width + empty * (width - filled_width)


def get_circular_indicator(pct: float) -> str:
    """Get a circular progress indicator character."""
    pct = max(0, min(100, pct))
    # Use pie chart characters
    if pct < 12.5:
        return "○"
    elif pct < 25:
        return "◔"
    elif pct < 50:
        return "◑"
    elif pct < 75:
        return "◕"
    else:
        return "●"


def get_trend(history: List[Dict], key: str) -> Tuple[str, float]:
    """Calculate trend arrow and change percentage."""
    if len(history) < 5:
        return "→", 0.0

    recent = [h.get(key, 0) for h in history[-5:]]
    older = [h.get(key, 0) for h in history[-15:-5]]

    if not recent or not older:
        return "→", 0.0

    avg_recent = sum(recent) / len(recent)
    avg_older = sum(older) / len(older)
    change = avg_recent - avg_older

    if change > 1:
        return "↑", change
    elif change < -1:
        return "↓", change
    return "→", change


# =============================================================================
# Color System
# =============================================================================

def interpolate_color(c1: str, c2: str, t: float) -> str:
    """Linear interpolation between two hex colors."""
    t = max(0, min(1, t))
    r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
    r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
    r = int(r1 + (r2 - r1) * t)
    g = int(g1 + (g2 - g1) * t)
    b = int(b1 + (b2 - b1) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


def get_gradient_color(pct: float, config: Dict) -> str:
    """Get smooth gradient color based on percentage."""
    thresholds = config.get("thresholds", {})
    green_max = thresholds.get("green_max", 50)
    yellow_max = thresholds.get("yellow_max", 75)
    orange_max = thresholds.get("orange_max", 90)

    if pct < green_max * 0.5:
        return COLORS["green"]
    elif pct < green_max:
        t = (pct - green_max * 0.5) / (green_max * 0.5)
        return interpolate_color(COLORS["green"], COLORS["lime"], t)
    elif pct < yellow_max:
        t = (pct - green_max) / (yellow_max - green_max)
        return interpolate_color(COLORS["yellow"], COLORS["amber"], t)
    elif pct < orange_max:
        t = (pct - yellow_max) / (orange_max - yellow_max)
        return interpolate_color(COLORS["orange"], COLORS["red"], t)
    else:
        return COLORS["red"]


# =============================================================================
# Time Formatting
# =============================================================================

def fmt_time_until(iso_str: str, short: bool = False) -> str:
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

        if short:
            if h > 24:
                return f"{h // 24}d"
            if h > 0:
                return f"{h}h"
            return f"{m}m"
        else:
            if h > 24:
                d = h // 24
                h = h % 24
                return f"{d}d {h}h"
            if h > 0:
                return f"{h}h {m}m"
            return f"{m}m"
    except (ValueError, TypeError):
        return "?"


# =============================================================================
# API Functions
# =============================================================================

def get_oauth_token() -> str:
    """Extract OAuth token from macOS Keychain."""
    try:
        result = subprocess.run(
            ["security", "find-generic-password",
             "-a", os.environ.get("USER", ""),
             "-s", "Claude Code-credentials", "-w"],
            capture_output=True, text=True, timeout=5
        )

        if result.returncode != 0:
            if "could not be found" in result.stderr.lower():
                raise KeychainError("Claude Code credentials not found.")
            raise KeychainError(f"Keychain access failed: {result.stderr}")

        creds = json.loads(result.stdout.strip())
        token = creds.get("claudeAiOauth", {}).get("accessToken")

        if not token:
            raise AuthError("No OAuth token found.")

        return token

    except subprocess.TimeoutExpired:
        raise KeychainError("Keychain access timed out")
    except json.JSONDecodeError:
        raise KeychainError("Invalid credentials format")
    except FileNotFoundError:
        raise KeychainError("Not running on macOS")


def fetch_usage(config: Dict) -> Dict:
    """Fetch real usage data from Anthropic API."""
    token = get_oauth_token()
    timeout = config.get("advanced", {}).get("api_timeout", 10)

    try:
        req = urllib.request.Request(
            "https://api.anthropic.com/api/oauth/usage",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "anthropic-beta": "oauth-2025-04-20",
                "User-Agent": "claude-monitor/2.1.0"
            }
        )

        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())

    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise AuthError("Session expired")
        elif e.code == 403:
            raise AuthError("Access denied")
        elif e.code == 429:
            raise APIError("Rate limited")
        elif e.code >= 500:
            raise APIError(f"API error ({e.code})")
        else:
            raise APIError(f"HTTP {e.code}")
    except urllib.error.URLError as e:
        raise NetworkError(f"Network error")
    except json.JSONDecodeError:
        raise APIError("Invalid response")


def fetch_with_retry(config: Dict) -> Tuple[Optional[Dict], Optional[Exception]]:
    """Fetch usage with retry logic."""
    max_retries = config.get("advanced", {}).get("retry_count", 3)
    last_error = None

    for attempt in range(max_retries):
        try:
            usage = fetch_usage(config)
            save_usage_cache(usage)
            return usage, None
        except NetworkError as e:
            last_error = e
            if attempt < max_retries - 1:
                time.sleep(1 * (2 ** attempt))
        except (AuthError, KeychainError, APIError) as e:
            return None, e

    return None, last_error


# =============================================================================
# Menu Bar Title Builder
# =============================================================================

def build_menubar_title(usage: Dict, config: Dict, history: List[Dict]) -> str:
    """Build the menu bar title based on configuration."""
    menubar = config.get("menubar", {})
    style = menubar.get("style", "full")
    graph_style = menubar.get("graph_style", "blocks")
    graph_width = menubar.get("graph_width", 8)

    # Extract data
    session_pct = (usage.get("five_hour") or {}).get("utilization") or 0
    weekly_pct = (usage.get("seven_day") or {}).get("utilization") or 0
    sonnet_pct = (usage.get("seven_day_sonnet") or {}).get("utilization") or 0
    opus_pct = (usage.get("seven_day_opus") or {}).get("utilization") or 0

    session_reset = (usage.get("five_hour") or {}).get("resets_at", "")
    weekly_reset = (usage.get("seven_day") or {}).get("resets_at", "")

    session_pct = max(0, min(100, session_pct))
    weekly_pct = max(0, min(100, weekly_pct))
    sonnet_pct = max(0, min(100, sonnet_pct))
    opus_pct = max(0, min(100, opus_pct))

    overall_pct = max(session_pct, weekly_pct)

    parts = []

    if style == "minimal":
        # Just the overall percentage
        parts.append(f"{overall_pct:.0f}%")

    elif style == "compact":
        # Session and Weekly percentages
        parts.append(f"S:{session_pct:.0f}%")
        parts.append(f"W:{weekly_pct:.0f}%")

    elif style == "full":
        # Full display with graph
        parts.append(f"S:{session_pct:.0f}%")
        parts.append(f"W:{weekly_pct:.0f}%")

        if graph_style != "none" and history:
            session_values = [h.get("session", 0) for h in history]
            graph = get_graph(session_values, graph_width, graph_style)
            parts.append(graph)

    elif style == "detailed":
        # Everything including models and reset times
        parts.append(f"S:{session_pct:.0f}%")
        if session_reset:
            parts.append(f"({fmt_time_until(session_reset, short=True)})")

        parts.append(f"W:{weekly_pct:.0f}%")

        # Model breakdown
        if opus_pct > 0:
            parts.append(f"O:{opus_pct:.0f}%")
        if sonnet_pct > 0:
            parts.append(f"Sn:{sonnet_pct:.0f}%")

        if graph_style != "none" and history:
            session_values = [h.get("session", 0) for h in history]
            graph = get_graph(session_values, graph_width, graph_style)
            parts.append(graph)

    return " ".join(parts)


# =============================================================================
# Display Functions
# =============================================================================

def show_error(icon: str, title: str, message: str) -> None:
    """Display error state in menu bar."""
    print(f"{icon} | sfSymbol=exclamationmark.triangle sfcolor={COLORS['red']}")
    print("---")
    print(f"{title} | color={COLORS['red']}")
    print(f"--{message} | color={COLORS['gray']}")
    print("---")
    print("Refresh | refresh=true sfSymbol=arrow.clockwise")


def render_menu(usage: Dict, config: Dict, is_cached: bool = False) -> None:
    """Render the full menu bar display."""
    display = config.get("display", {})
    menubar = config.get("menubar", {})
    graph_style = menubar.get("graph_style", "blocks")

    # Extract usage data
    session_data = usage.get("five_hour") or {}
    session_pct = session_data.get("utilization") or 0
    session_reset = session_data.get("resets_at", "")

    weekly_data = usage.get("seven_day") or {}
    weekly_pct = weekly_data.get("utilization") or 0
    weekly_reset = weekly_data.get("resets_at", "")

    sonnet_pct = (usage.get("seven_day_sonnet") or {}).get("utilization") or 0
    opus_pct = (usage.get("seven_day_opus") or {}).get("utilization") or 0

    # Clamp values
    session_pct = max(0, min(100, session_pct))
    weekly_pct = max(0, min(100, weekly_pct))
    sonnet_pct = max(0, min(100, sonnet_pct))
    opus_pct = max(0, min(100, opus_pct))

    # Save to history
    save_history_entry(session_pct, weekly_pct)
    history = load_history()

    # Build menu bar title
    title = build_menubar_title(usage, config, history)

    # Determine overall status for icon/color
    overall_pct = max(session_pct, weekly_pct)
    overall_color = get_gradient_color(overall_pct, config)

    if overall_pct >= 90:
        icon = "exclamationmark.triangle.fill"
    elif overall_pct >= 75:
        icon = "exclamationmark.circle.fill"
    elif overall_pct >= 50:
        icon = "chart.bar.fill"
    else:
        icon = "checkmark.circle.fill"

    # Menu bar output
    if menubar.get("show_icons", True):
        print(f"{title} | sfSymbol={icon} sfcolor={overall_color}")
    else:
        print(f"{title} | color={overall_color}")
    print("---")

    # Offline indicator
    if is_cached:
        print(f"⚡ Cached Data | color={COLORS['gray']}")
        print("---")

    # Session section
    if display.get("show_session", True):
        session_color = get_gradient_color(session_pct, config)
        meter = get_meter(session_pct, 12)
        trend_arrow, trend_val = get_trend(history, "session")

        print(f"Session ({session_pct:.0f}%) | color={COLORS['white']}")
        print(f"--{meter} | color={session_color} font=Menlo")

        if display.get("show_resets", True) and session_reset:
            print(f"--⏱ Resets in {fmt_time_until(session_reset)} | color={COLORS['gray']}")

        if len(history) >= 5 and abs(trend_val) > 0.5:
            sign = "+" if trend_val > 0 else ""
            print(f"--{trend_arrow} {sign}{trend_val:.1f}% trend | color={COLORS['gray']}")

        # Mini sparkline in dropdown
        if history:
            session_vals = [h.get("session", 0) for h in history[-20:]]
            spark = get_graph(session_vals, 20, graph_style)
            print(f"--{spark} | font=Menlo size=10 color={COLORS['gray']}")

        print("---")

    # Weekly section
    if display.get("show_weekly", True):
        weekly_color = get_gradient_color(weekly_pct, config)
        meter = get_meter(weekly_pct, 12)

        print(f"Weekly ({weekly_pct:.0f}%) | color={COLORS['white']}")
        print(f"--{meter} | color={weekly_color} font=Menlo")

        # Model breakdown
        if display.get("show_models", True):
            if opus_pct > 0:
                opus_meter = get_meter(opus_pct, 8)
                opus_color = get_gradient_color(opus_pct, config)
                print(f"--Opus: {opus_pct:.0f}% {opus_meter} | color={opus_color} font=Menlo")

            if sonnet_pct > 0:
                sonnet_meter = get_meter(sonnet_pct, 8)
                sonnet_color = get_gradient_color(sonnet_pct, config)
                print(f"--Sonnet: {sonnet_pct:.0f}% {sonnet_meter} | color={sonnet_color} font=Menlo")

        if display.get("show_resets", True) and weekly_reset:
            print(f"--⏱ Resets in {fmt_time_until(weekly_reset)} | color={COLORS['gray']}")

        # Weekly sparkline
        if history:
            weekly_vals = [h.get("weekly", 0) for h in history[-20:]]
            spark = get_graph(weekly_vals, 20, graph_style)
            print(f"--{spark} | font=Menlo size=10 color={COLORS['gray']}")

        print("---")

    # Settings submenu
    script_path = os.path.abspath(__file__)
    print(f"Settings | sfSymbol=gear")

    # Menu bar style
    current_style = menubar.get("style", "full")
    print(f"--Menu Bar Style | sfSymbol=menubar.rectangle")
    for s in ["minimal", "compact", "full", "detailed"]:
        checked = "checked=true" if s == current_style else ""
        print(f"----{s.title()} | {checked} bash={script_path} param1=--set param2=style param3={s} terminal=false refresh=true")

    # Graph style
    current_graph = menubar.get("graph_style", "blocks")
    print(f"--Graph Style | sfSymbol=chart.bar.xaxis")
    for g in ["bars", "blocks", "braille", "dots", "shades", "none"]:
        checked = "checked=true" if g == current_graph else ""
        sample = get_graph([20, 40, 60, 80, 100], 5, g) if g != "none" else "(disabled)"
        print(f"----{g.title()} {sample} | {checked} bash={script_path} param1=--set param2=graph param3={g} terminal=false refresh=true font=Menlo")

    print("--")
    print(f"--Open Config File | bash=open param1={CONFIG_FILE} terminal=false sfSymbol=doc.text")

    print("---")
    print("Refresh | refresh=true sfSymbol=arrow.clockwise")


# =============================================================================
# CLI Commands
# =============================================================================

def handle_cli_args() -> bool:
    """Handle command line arguments. Returns True if handled."""
    if len(sys.argv) < 2:
        return False

    if sys.argv[1] == "--set" and len(sys.argv) >= 4:
        config = load_config()
        setting = sys.argv[2]
        value = sys.argv[3]

        if setting == "style":
            config["menubar"]["style"] = value
        elif setting == "graph":
            config["menubar"]["graph_style"] = value

        save_config(config)
        return True

    if sys.argv[1] == "--toggle" and len(sys.argv) >= 3:
        config = load_config()
        setting = sys.argv[2]

        if setting == "sparkline":
            config["display"]["show_sparkline"] = not config["display"].get("show_sparkline", True)
        elif setting == "compact":
            config["display"]["compact_mode"] = not config["display"].get("compact_mode", False)
        elif setting == "icons":
            config["menubar"]["show_icons"] = not config["menubar"].get("show_icons", True)

        save_config(config)
        return True

    return False


# =============================================================================
# Main
# =============================================================================

def main():
    if handle_cli_args():
        return

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config = load_config()

    usage, error = fetch_with_retry(config)

    if usage:
        render_menu(usage, config, is_cached=False)
        return

    if error:
        cached_usage, _ = load_cached_usage()
        if cached_usage:
            render_menu(cached_usage, config, is_cached=True)
            return

        if isinstance(error, KeychainError):
            show_error("⚙️", "Setup Required", "Log in to Claude Code")
        elif isinstance(error, AuthError):
            show_error("🔐", "Auth Required", "Session expired")
        elif isinstance(error, NetworkError):
            show_error("🌐", "Offline", "Check connection")
        else:
            show_error("⚠️", "Error", str(error))
        return

    show_error("?", "Error", "Unknown error")


if __name__ == "__main__":
    main()
