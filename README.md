# Claude Code Usage Monitor for macOS

<p align="center">
  <img src="https://img.shields.io/badge/Version-2.0.0-blue" alt="Version 2.0.0">
  <img src="https://img.shields.io/badge/Platform-macOS-blue" alt="macOS">
  <img src="https://img.shields.io/badge/SwiftBar-Compatible-green" alt="SwiftBar">
  <img src="https://img.shields.io/badge/Python-3.8+-yellow" alt="Python 3.8+">
  <img src="https://img.shields.io/badge/License-MIT-lightgrey" alt="MIT License">
</p>

A beautiful SwiftBar menu bar widget that displays your Claude Code usage stats in real-time. Shows **real API data** matching the `/status` command, with sparkline graphs, smooth color gradients, and offline support.

## Preview

```
30% ▁▂▃▄▅▆ | sfSymbol=chart.bar.fill
─────────────────────────────────
Session
  └─ 30% ███░░░░░░░
  └─ Resets in 1h 13m
  └─ Trend: ↑ +5%
─────────────────────────────────
Weekly
  └─ 19% █░░░░░░░░░
  └─ Sonnet: 1%
  └─ Resets in 3d 9h
─────────────────────────────────
Settings ⚙️
Refresh ↻
```

## Features

### Real-Time Data
- **Exact percentages** from Anthropic API (same as `/status` command)
- **Session usage**: 5-hour rolling window
- **Weekly usage**: 7-day totals with per-model breakdown

### Visual Design
- **Sparkline graphs**: Mini bar chart showing usage trend (`▁▂▃▄▅▆▇█`)
- **Smooth color gradients**: Colors transition from green→yellow→orange→red
- **Progress bars**: Visual percentage indicators (`███░░░░░░░`)
- **Trend arrows**: Shows if usage is increasing (↑), decreasing (↓), or stable (→)
- **SF Symbols**: Native macOS icons that adapt to light/dark mode

### Reliability
- **Offline caching**: Shows cached data when network unavailable
- **Automatic retry**: Exponential backoff for network failures
- **Graceful errors**: Clear messages for different failure modes
- **Robust validation**: Handles edge cases and malformed API responses

### Configuration
- **Customizable thresholds**: Set when colors change (50%/75%/90%)
- **Display options**: Toggle sparkline, compact mode, sections
- **Settings menu**: Configure directly from the menu bar

## Installation

### Option 1: DMG Installer (Recommended)

1. Download the latest `.dmg` from [Releases](https://github.com/watchthelight/ClaudeMonitor-macOS/releases)
2. Open the DMG and double-click `install.sh`
3. Follow the on-screen instructions

### Option 2: Quick Install

```bash
# Install SwiftBar
brew install swiftbar

# Download and install plugin
curl -fsSL https://raw.githubusercontent.com/watchthelight/ClaudeMonitor-macOS/main/src/claude-usage.60s.py \
  -o ~/Library/Application\ Support/SwiftBar/Plugins/claude-usage.60s.py

chmod +x ~/Library/Application\ Support/SwiftBar/Plugins/claude-usage.60s.py
```

### Option 3: From Source

```bash
git clone https://github.com/watchthelight/ClaudeMonitor-macOS.git
cd ClaudeMonitor-macOS
make install
```

## Requirements

- **macOS 11 Big Sur** or later
- **Python 3.8+** (included with macOS)
- **SwiftBar** ([swiftbar.app](https://swiftbar.app))
- **Claude Code** (logged in with Pro/Max subscription)

## Configuration

Config file: `~/.config/claude-monitor/config.json`

```json
{
  "display": {
    "show_sparkline": true,
    "show_session": true,
    "show_weekly": true,
    "compact_mode": false
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
```

### Settings Menu

Click the widget and go to **Settings** to:
- Toggle sparkline display
- Enable compact mode
- Open config file for advanced editing

### Refresh Rate

Rename the plugin file to change update frequency:
- `claude-usage.30s.py` - every 30 seconds
- `claude-usage.60s.py` - every 60 seconds (default)
- `claude-usage.5m.py` - every 5 minutes

## How It Works

The plugin fetches real usage data from the Anthropic API:

```
https://api.anthropic.com/api/oauth/usage
```

Using OAuth tokens stored in your macOS Keychain (from Claude Code login), it retrieves:
- **5-hour session utilization** percentage
- **7-day weekly utilization** percentage
- Per-model breakdown (Opus, Sonnet)
- Reset timestamps

This is the same data displayed by the `/status` command in Claude Code.

## Troubleshooting

### Widget shows ⚙️ (Setup Required)
- Claude Code is not installed or not logged in
- Run `claude` and log in with your Anthropic account

### Widget shows 🔐 (Auth Required)
- Your session has expired
- Run Claude Code to refresh authentication

### Widget shows 🌐 (Offline)
- Network connection unavailable
- The widget will show cached data until connection is restored

### Widget shows ⚠️ (Error)
- API error or unexpected response
- Check for plugin updates

### Test the plugin manually

```bash
python3 ~/Library/Application\ Support/SwiftBar/Plugins/claude-usage.60s.py
```

## Development

```bash
# Clone the repo
git clone https://github.com/watchthelight/ClaudeMonitor-macOS.git
cd ClaudeMonitor-macOS

# Quick install for testing
make quick-install

# Run tests
make test

# Build DMG
make build

# See all commands
make help
```

## License

MIT License - See [LICENSE](LICENSE) file.

## Acknowledgments

- Built with [SwiftBar](https://github.com/swiftbar/SwiftBar)
- Uses the [Anthropic API](https://www.anthropic.com)
- Inspired by the Claude Code community

## Related

- [Claude Code Documentation](https://docs.anthropic.com/en/docs/claude-code)
- [Anthropic Rate Limits](https://docs.anthropic.com/en/api/rate-limits)
