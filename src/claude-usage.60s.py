#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Claude Code Usage Monitor v2.0 - SwiftBar Plugin
A production-ready menu bar widget for tracking Claude Code usage.

Features:
- Real API data from Anthropic
- Sparkline usage history
- Smooth color gradients
- Configurable thresholds
- Offline caching
- Graceful error handling
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
    "version": 1,
    "display": {
        "show_sparkline": True,
        "show_session": True,
        "show_weekly": True,
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

# Sparkline characters (9 levels: empty to full)
SPARKLINE_CHARS = " ▁▂▃▄▅▆▇█"

# Colors (Tailwind-inspired)
COLORS = {
    "green": "#22c55e",
    "yellow": "#eab308",
    "orange": "#f97316",
    "red": "#ef4444",
    "gray": "#6b7280",
    "white": "#f4f4f5",
    "blue": "#3b82f6"
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
            # Merge with defaults for any missing keys
            return deep_merge(DEFAULT_CONFIG, config)
    except (json.JSONDecodeError, IOError):
        pass

    # Create default config
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
# History Tracking (for Sparklines)
# =============================================================================

def load_history() -> List[Dict]:
    """Load usage history for sparkline display."""
    try:
        if HISTORY_FILE.exists():
            data = json.loads(HISTORY_FILE.read_text())
            return data.get("entries", [])
    except (json.JSONDecodeError, IOError):
        pass
    return []


def save_history_entry(session_pct: float, weekly_pct: float) -> None:
    """Save a history entry (called on each successful fetch)."""
    try:
        history = load_history()
        now = time.time()

        # Only add entry if last entry is at least 5 minutes old
        if history and (now - history[-1].get("ts", 0)) < 300:
            return

        history.append({
            "ts": now,
            "session": session_pct,
            "weekly": weekly_pct
        })

        # Keep last 48 entries (4 hours at 5-min intervals)
        history = history[-48:]

        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        HISTORY_FILE.write_text(json.dumps({"entries": history}))
    except IOError:
        pass


def get_sparkline(values: List[float], width: int = 8) -> str:
    """Generate Unicode sparkline from values."""
    if not values:
        return SPARKLINE_CHARS[1] * width

    # Take last N values
    values = values[-width:]

    min_v = min(values)
    max_v = max(values)
    range_v = max_v - min_v if max_v > min_v else 1

    result = ""
    for v in values:
        # Map value to 0-8 index
        idx = min(8, max(0, int((v - min_v) / range_v * 8)))
        result += SPARKLINE_CHARS[idx]

    return result.ljust(width, SPARKLINE_CHARS[1])


def get_trend(history: List[Dict], key: str) -> Tuple[str, float]:
    """Calculate trend arrow and change percentage."""
    if len(history) < 2:
        return "→", 0.0

    recent = [h.get(key, 0) for h in history[-4:]]  # Last ~20 minutes
    older = [h.get(key, 0) for h in history[-8:-4]]  # Previous ~20 minutes

    if not recent or not older:
        return "→", 0.0

    avg_recent = sum(recent) / len(recent)
    avg_older = sum(older) / len(older)
    change = avg_recent - avg_older

    if change > 2:
        return "↑", change
    elif change < -2:
        return "↓", change
    return "→", change


# =============================================================================
# Color System
# =============================================================================

def interpolate_color(c1: str, c2: str, t: float) -> str:
    """Linear interpolation between two hex colors."""
    t = max(0, min(1, t))  # Clamp to [0, 1]
    r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
    r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
    r = int(r1 + (r2 - r1) * t)
    g = int(g1 + (g2 - g1) * t)
    b = int(b1 + (b2 - b1) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


def get_gradient_color(pct: float, config: Dict) -> str:
    """Get smooth gradient color based on percentage and thresholds."""
    thresholds = config.get("thresholds", {})
    green_max = thresholds.get("green_max", 50)
    yellow_max = thresholds.get("yellow_max", 75)
    orange_max = thresholds.get("orange_max", 90)

    if pct < green_max / 2:
        return COLORS["green"]
    elif pct < green_max:
        t = (pct - green_max / 2) / (green_max / 2)
        return interpolate_color(COLORS["green"], COLORS["yellow"], t * 0.5)
    elif pct < yellow_max:
        t = (pct - green_max) / (yellow_max - green_max)
        return interpolate_color(COLORS["yellow"], COLORS["orange"], t)
    elif pct < orange_max:
        t = (pct - yellow_max) / (orange_max - yellow_max)
        return interpolate_color(COLORS["orange"], COLORS["red"], t)
    else:
        return COLORS["red"]


def get_simple_color(pct: float, config: Dict) -> str:
    """Get simple threshold-based color."""
    thresholds = config.get("thresholds", {})
    if pct < thresholds.get("green_max", 50):
        return COLORS["green"]
    elif pct < thresholds.get("yellow_max", 75):
        return COLORS["yellow"]
    elif pct < thresholds.get("orange_max", 90):
        return COLORS["orange"]
    return COLORS["red"]


# =============================================================================
# Progress Bar
# =============================================================================

def get_progress_bar(pct: float, width: int = 10) -> str:
    """Generate a Unicode progress bar."""
    filled = int(pct / 100 * width)
    filled = max(0, min(width, filled))
    return "█" * filled + "░" * (width - filled)


# =============================================================================
# Time Formatting
# =============================================================================

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
                raise KeychainError("Claude Code credentials not found. Please log in to Claude Code first.")
            raise KeychainError(f"Keychain access failed: {result.stderr}")

        creds = json.loads(result.stdout.strip())
        token = creds.get("claudeAiOauth", {}).get("accessToken")

        if not token:
            raise AuthError("No OAuth token found in credentials. Please log in to Claude Code.")

        return token

    except subprocess.TimeoutExpired:
        raise KeychainError("Keychain access timed out")
    except json.JSONDecodeError:
        raise KeychainError("Invalid credentials format in Keychain")
    except FileNotFoundError:
        raise KeychainError("'security' command not found - are you on macOS?")


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
                "User-Agent": "claude-monitor/2.0.0"
            }
        )

        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())

    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise AuthError("Session expired. Please run Claude Code to refresh your login.")
        elif e.code == 403:
            raise AuthError("Access denied. Check your Claude subscription.")
        elif e.code == 429:
            raise APIError("Rate limited. Please wait a moment.")
        elif e.code >= 500:
            raise APIError(f"Anthropic API error ({e.code}). Try again later.")
        else:
            raise APIError(f"API request failed: HTTP {e.code}")
    except urllib.error.URLError as e:
        if "timed out" in str(e).lower():
            raise NetworkError("Request timed out. Check your connection.")
        raise NetworkError(f"Network error: {e.reason}")
    except json.JSONDecodeError:
        raise APIError("Invalid API response")


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
                time.sleep(1 * (2 ** attempt))  # Exponential backoff
        except (AuthError, KeychainError, APIError) as e:
            # Don't retry auth/API errors
            return None, e

    return None, last_error


# =============================================================================
# Display Functions
# =============================================================================

def show_error(icon: str, title: str, message: str, details: str = "") -> None:
    """Display error state in menu bar."""
    print(f"{icon} | sfSymbol=exclamationmark.triangle sfcolor={COLORS['red']}")
    print("---")
    print(f"{title} | color={COLORS['red']}")
    print(f"--{message} | color={COLORS['gray']}")
    if details:
        print(f"--{details} | color={COLORS['gray']} size=11")
    print("---")
    print("Refresh | refresh=true sfSymbol=arrow.clockwise")


def render_menu(usage: Dict, config: Dict, is_cached: bool = False) -> None:
    """Render the full menu bar display."""
    display = config.get("display", {})

    # Extract usage data with safe defaults
    session_data = usage.get("five_hour") or {}
    session_pct = session_data.get("utilization") or 0
    session_reset = session_data.get("resets_at", "")

    weekly_data = usage.get("seven_day") or {}
    weekly_pct = weekly_data.get("utilization") or 0
    weekly_reset = weekly_data.get("resets_at", "")

    sonnet_data = usage.get("seven_day_sonnet") or {}
    sonnet_pct = sonnet_data.get("utilization") or 0

    opus_data = usage.get("seven_day_opus") or {}
    opus_pct = opus_data.get("utilization") or 0

    # Clamp percentages to valid range
    session_pct = max(0, min(100, session_pct))
    weekly_pct = max(0, min(100, weekly_pct))
    sonnet_pct = max(0, min(100, sonnet_pct))
    opus_pct = max(0, min(100, opus_pct))

    # Save to history
    save_history_entry(session_pct, weekly_pct)

    # Calculate overall status
    overall_pct = max(session_pct, weekly_pct)

    # Get colors
    overall_color = get_gradient_color(overall_pct, config)
    session_color = get_gradient_color(session_pct, config)
    weekly_color = get_gradient_color(weekly_pct, config)

    # Choose icon based on severity
    if overall_pct >= 90:
        icon = "exclamationmark.triangle.fill"
    elif overall_pct >= 75:
        icon = "exclamationmark.circle.fill"
    else:
        icon = "chart.bar.fill"

    # Build menu bar title
    title_parts = [f"{overall_pct:.0f}%"]

    if display.get("show_sparkline", True):
        history = load_history()
        if history:
            session_values = [h.get("session", 0) for h in history]
            sparkline = get_sparkline(session_values, 6)
            title_parts.append(sparkline)

    title = " ".join(title_parts)

    # Menu bar line
    print(f"{title} | sfSymbol={icon} sfcolor={overall_color}")
    print("---")

    # Cached data warning
    if is_cached:
        print(f"Offline Mode | color={COLORS['gray']} sfSymbol=wifi.slash")
        print("---")

    # Session section
    if display.get("show_session", True):
        progress = get_progress_bar(session_pct)
        print(f"Session | color={COLORS['white']}")
        print(f"--{session_pct:.0f}% {progress} | color={session_color}")

        if session_reset:
            print(f"--Resets in {fmt_time_until(session_reset)} | color={COLORS['gray']}")

        # Show trend
        history = load_history()
        if len(history) >= 2:
            arrow, change = get_trend(history, "session")
            if abs(change) > 0.5:
                sign = "+" if change > 0 else ""
                print(f"--Trend: {arrow} {sign}{change:.0f}% | color={COLORS['gray']}")

        print("---")

    # Weekly section
    if display.get("show_weekly", True):
        progress = get_progress_bar(weekly_pct)
        print(f"Weekly | color={COLORS['white']}")
        print(f"--{weekly_pct:.0f}% {progress} | color={weekly_color}")

        # Model breakdown
        if opus_pct > 0:
            print(f"--Opus: {opus_pct:.0f}% | color={get_simple_color(opus_pct, config)}")
        if sonnet_pct > 0:
            print(f"--Sonnet: {sonnet_pct:.0f}% | color={get_simple_color(sonnet_pct, config)}")

        if weekly_reset:
            print(f"--Resets in {fmt_time_until(weekly_reset)} | color={COLORS['gray']}")

        print("---")

    # Settings submenu
    if not display.get("compact_mode", False):
        script_path = os.path.abspath(__file__)
        print(f"Settings | sfSymbol=gear")

        sparkline_checked = "checked=true" if display.get("show_sparkline", True) else ""
        print(f"--Show Sparkline | {sparkline_checked} bash={script_path} param1=--toggle param2=sparkline terminal=false refresh=true")

        compact_checked = "checked=true" if display.get("compact_mode", False) else ""
        print(f"--Compact Mode | {compact_checked} bash={script_path} param1=--toggle param2=compact terminal=false refresh=true")

        print(f"--Open Config | bash=open param1={CONFIG_FILE} terminal=false")
        print("---")

    # Refresh button
    print("Refresh | refresh=true sfSymbol=arrow.clockwise")


# =============================================================================
# CLI Commands (for settings menu)
# =============================================================================

def handle_cli_args() -> bool:
    """Handle command line arguments for settings changes. Returns True if handled."""
    if len(sys.argv) < 2:
        return False

    if sys.argv[1] == "--toggle" and len(sys.argv) >= 3:
        config = load_config()
        setting = sys.argv[2]

        if setting == "sparkline":
            config["display"]["show_sparkline"] = not config["display"].get("show_sparkline", True)
        elif setting == "compact":
            config["display"]["compact_mode"] = not config["display"].get("compact_mode", False)

        save_config(config)
        return True

    return False


# =============================================================================
# Main
# =============================================================================

def main():
    # Handle CLI commands first
    if handle_cli_args():
        return

    # Ensure config directory exists
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # Load configuration
    config = load_config()

    # Try to fetch fresh data
    usage, error = fetch_with_retry(config)

    if usage:
        render_menu(usage, config, is_cached=False)
        return

    # Try cached data on error
    if error:
        cached_usage, _ = load_cached_usage()
        if cached_usage:
            render_menu(cached_usage, config, is_cached=True)
            return

        # Show specific error
        if isinstance(error, KeychainError):
            show_error("⚙️", "Setup Required", "Claude Code not found", str(error))
        elif isinstance(error, AuthError):
            show_error("🔐", "Auth Required", "Session expired", str(error))
        elif isinstance(error, NetworkError):
            show_error("🌐", "Offline", "Network unavailable", str(error))
        else:
            show_error("⚠️", "Error", "Failed to fetch usage", str(error))
        return

    # Fallback error
    show_error("?", "Unknown Error", "Could not fetch usage data")


if __name__ == "__main__":
    main()
