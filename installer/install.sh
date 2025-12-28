#!/bin/bash
# =============================================================================
# Claude Monitor Installer
# Installs the SwiftBar plugin and creates default configuration
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Paths
SWIFTBAR_PLUGINS="$HOME/Library/Application Support/SwiftBar/Plugins"
CONFIG_DIR="$HOME/.config/claude-monitor"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "╔═══════════════════════════════════════════╗"
echo "║     Claude Monitor Installer v2.0.0       ║"
echo "╚═══════════════════════════════════════════╝"
echo ""

# Check if running on macOS
if [[ "$(uname)" != "Darwin" ]]; then
    echo -e "${RED}Error: Claude Monitor requires macOS${NC}"
    exit 1
fi

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is required but not installed${NC}"
    echo "Install with: brew install python3"
    exit 1
fi

echo -e "${GREEN}✓${NC} Python 3 found: $(python3 --version)"

# Check if SwiftBar is installed
if [ -d "/Applications/SwiftBar.app" ]; then
    echo -e "${GREEN}✓${NC} SwiftBar found"
elif command -v swiftbar &> /dev/null; then
    echo -e "${GREEN}✓${NC} SwiftBar found (CLI)"
else
    echo -e "${YELLOW}!${NC} SwiftBar not found"
    echo ""
    echo "Would you like to install SwiftBar? (recommended)"
    echo "  1) Install via Homebrew (brew install swiftbar)"
    echo "  2) Skip - I'll install it manually from https://swiftbar.app"
    echo ""
    read -p "Choice [1/2]: " choice

    if [ "$choice" = "1" ]; then
        if command -v brew &> /dev/null; then
            echo "Installing SwiftBar..."
            brew install swiftbar
        else
            echo -e "${RED}Homebrew not found. Please install SwiftBar manually:${NC}"
            echo "  https://swiftbar.app"
            exit 1
        fi
    else
        echo ""
        echo "Please install SwiftBar from https://swiftbar.app"
        echo "Then run this installer again."
        exit 0
    fi
fi

# Create SwiftBar plugins directory
echo ""
echo "Installing plugin..."
mkdir -p "$SWIFTBAR_PLUGINS"

# Find the plugin file
if [ -f "$SCRIPT_DIR/claude-usage.60s.py" ]; then
    PLUGIN_SRC="$SCRIPT_DIR/claude-usage.60s.py"
elif [ -f "$SCRIPT_DIR/../src/claude-usage.60s.py" ]; then
    PLUGIN_SRC="$SCRIPT_DIR/../src/claude-usage.60s.py"
else
    echo -e "${RED}Error: Could not find claude-usage.60s.py${NC}"
    exit 1
fi

# Copy plugin
cp "$PLUGIN_SRC" "$SWIFTBAR_PLUGINS/claude-usage.60s.py"
chmod +x "$SWIFTBAR_PLUGINS/claude-usage.60s.py"
echo -e "${GREEN}✓${NC} Plugin installed to $SWIFTBAR_PLUGINS/"

# Create config directory and default config
mkdir -p "$CONFIG_DIR"

if [ ! -f "$CONFIG_DIR/config.json" ]; then
    cat > "$CONFIG_DIR/config.json" << 'EOF'
{
  "version": 1,
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
EOF
    echo -e "${GREEN}✓${NC} Created default config at $CONFIG_DIR/config.json"
else
    echo -e "${GREEN}✓${NC} Existing config preserved at $CONFIG_DIR/config.json"
fi

# Check if Claude Code credentials exist
if security find-generic-password -s "Claude Code-credentials" &> /dev/null; then
    echo -e "${GREEN}✓${NC} Claude Code credentials found"
else
    echo -e "${YELLOW}!${NC} Claude Code credentials not found"
    echo "  Please log in to Claude Code first, then restart SwiftBar"
fi

# Start or restart SwiftBar
echo ""
echo "Starting SwiftBar..."
if pgrep -x "SwiftBar" > /dev/null; then
    # SwiftBar is running, trigger a refresh
    osascript -e 'tell application "SwiftBar" to refresh all' 2>/dev/null || true
    echo -e "${GREEN}✓${NC} SwiftBar refreshed"
else
    # Start SwiftBar
    open -a SwiftBar 2>/dev/null || true
    echo -e "${GREEN}✓${NC} SwiftBar started"
fi

echo ""
echo "═══════════════════════════════════════════"
echo -e "${GREEN}Installation complete!${NC}"
echo ""
echo "The Claude Monitor widget should now appear in your menu bar."
echo ""
echo "Tips:"
echo "  • Click the widget to see detailed usage stats"
echo "  • Use Settings menu to customize the display"
echo "  • Edit config at: $CONFIG_DIR/config.json"
echo ""
echo "Troubleshooting:"
echo "  • If widget shows '⚙️', log in to Claude Code first"
echo "  • If widget shows '🌐', check your internet connection"
echo "  • Run: python3 '$SWIFTBAR_PLUGINS/claude-usage.60s.py'"
echo ""
