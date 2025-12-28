# Claude Code Usage Monitor for macOS

<p align="center">
  <img src="https://img.shields.io/badge/Platform-macOS-blue" alt="macOS">
  <img src="https://img.shields.io/badge/SwiftBar-Compatible-green" alt="SwiftBar">
  <img src="https://img.shields.io/badge/Python-3.8+-yellow" alt="Python 3.8+">
  <img src="https://img.shields.io/badge/License-MIT-lightgrey" alt="MIT License">
</p>

A lightweight SwiftBar menu bar widget that displays your Claude Code usage stats in real-time, helping you track your Pro/Max subscription limits.

## Preview

```
CC ⚡ ▾
────────────────────────────────
Claude Code Usage
Local data only • /status for limits
────────────────────────────────
Last 5 Hours
  └─ Prompts: 94
  └─ API Calls: 2,783
  └─ Tokens: 11.1M (in: 258K, out: 396K)
  └─ Cache: 189.5M read, 10.5M written
────────────────────────────────
Last 24 Hours
  └─ Prompts: 203
  └─ API Calls: 5,831
  └─ Tokens: 22.2M
  └─ Sessions: 22
────────────────────────────────
Last 7 Days
  └─ Prompts: 728
  └─ Tokens: 74.0M
  └─ Sessions: 43
────────────────────────────────
By Model (7d)
  └─ opus-4-5: 63.9M (15,399 calls)
  └─ haiku-4-5: 10.1M (2,181 calls)
```

## Features

- **Raw Usage Data**: Actual prompts, API calls, and token counts
- **Multiple Time Windows**: 5-hour, 24-hour, and 7-day views
- **Cache Stats**: See cache read vs write tokens
- **Model Breakdown**: Usage per model (Opus, Sonnet, Haiku)
- **SF Symbols**: Native macOS icons (⚡ active, 🌙 idle)
- **Auto-Refresh**: Updates every 60 seconds

## Quick Install

### 1. Install SwiftBar

```bash
brew install swiftbar
```

Or download from [swiftbar.app](https://swiftbar.app)

### 2. Download & Install Plugin

```bash
# Download the plugin
curl -fsSL https://raw.githubusercontent.com/watchthelight/ClaudeMonitor-macOS/main/claude-usage.60s.py \
  -o ~/Library/Application\ Support/SwiftBar/Plugins/claude-usage.60s.py

# Make it executable
chmod +x ~/Library/Application\ Support/SwiftBar/Plugins/claude-usage.60s.py
```

That's it! The widget will appear in your menu bar.

## How It Works

The plugin reads your local Claude Code session data:

```
~/.claude/projects/*/[session-id].jsonl
```

Each session file contains message metadata including:
- Token counts (input, output, cache)
- Model used
- Timestamps

The widget estimates your usage by:
1. Counting user prompts in the last 5 hours
2. Summing tokens over the last 7 days
3. Comparing against known plan limits

### Important Limitations

⚠️ **This provides estimates only.** The actual Claude Pro/Max quotas are managed server-side by Anthropic and are not exposed via API.

For official usage status, use the `/status` command within Claude Code.

## Customization

### Change Refresh Rate

Rename the file to adjust update frequency:
- `claude-usage.30s.py` - every 30 seconds
- `claude-usage.60s.py` - every 60 seconds (default)
- `claude-usage.5m.py` - every 5 minutes

## Technical Details

### Data Sources

| Location | Content |
|----------|---------|
| `~/.claude/projects/*/` | Session JSONL files with usage data |
| `~/.claude/stats-cache.json` | Historical daily statistics |
| `~/.claude/debug/` | Debug logs (rate limit errors) |

### Claude Code Rate Limits

Claude Code uses a dual-limit system:
1. **5-hour rolling window** - Limits burst usage
2. **Weekly cap** - Total usage per week

Both limits must be satisfied. Hitting either blocks new requests.

### API Rate Limit Headers

The Anthropic API returns headers like:
- `anthropic-ratelimit-tokens-remaining`
- `anthropic-ratelimit-requests-reset`

However, these are for per-minute API limits, not subscription quotas.

## Troubleshooting

### Plugin not showing?
1. Check SwiftBar is running
2. Verify plugin is executable: `chmod +x claude-usage.60s.py`
3. Check for Python errors: Run manually in terminal

### Wrong usage numbers?
- The plugin counts user prompts, not API calls
- Estimates may differ from Anthropic's actual tracking
- Use `/status` in Claude Code for official numbers

### SwiftBar plugins folder location
```
~/Library/Application Support/SwiftBar/Plugins/
```

## Contributing

Issues and PRs welcome! This is a community tool and improvements are appreciated.

## License

MIT License - See [LICENSE](LICENSE) file.

## Acknowledgments

- Built with [SwiftBar](https://github.com/swiftbar/SwiftBar)
- Data from Claude Code by [Anthropic](https://www.anthropic.com)

## Related Resources

- [Anthropic Rate Limits Documentation](https://platform.claude.com/docs/en/api/rate-limits)
- [Claude Code Pro/Max Usage Guide](https://support.claude.com/en/articles/11145838-using-claude-code-with-your-pro-or-max-plan)
