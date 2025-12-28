#!/bin/bash
# =============================================================================
# Claude Monitor DMG Builder
# Creates a distributable DMG installer
# =============================================================================

set -e

# Configuration
VERSION="${VERSION:-2.0.0}"
APP_NAME="Claude Monitor"
DMG_NAME="Claude-Monitor-${VERSION}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Paths
STAGING="/tmp/claude-monitor-dmg"
DIST_DIR="$PROJECT_ROOT/dist"

echo ""
echo "╔═══════════════════════════════════════════╗"
echo "║     Building Claude Monitor DMG           ║"
echo "║     Version: $VERSION                     ║"
echo "╚═══════════════════════════════════════════╝"
echo ""

# Clean up previous builds
rm -rf "$STAGING"
mkdir -p "$STAGING"
mkdir -p "$DIST_DIR"

echo "Preparing files..."

# Copy main plugin
cp "$PROJECT_ROOT/src/claude-usage.60s.py" "$STAGING/"

# Copy installer
cp "$SCRIPT_DIR/install.sh" "$STAGING/"
chmod +x "$STAGING/install.sh"

# Copy README
if [ -f "$PROJECT_ROOT/README.md" ]; then
    cp "$PROJECT_ROOT/README.md" "$STAGING/"
fi

# Create a simple "How to Install" file
cat > "$STAGING/HOW TO INSTALL.txt" << 'EOF'
╔═══════════════════════════════════════════════════════════════════╗
║                    Claude Monitor Installation                    ║
╚═══════════════════════════════════════════════════════════════════╝

QUICK INSTALL (Recommended):
────────────────────────────
1. Double-click "install.sh"
2. If prompted, right-click → Open → Open
3. Follow the on-screen instructions

MANUAL INSTALL:
───────────────
1. Install SwiftBar: brew install swiftbar
   Or download from: https://swiftbar.app

2. Copy claude-usage.60s.py to:
   ~/Library/Application Support/SwiftBar/Plugins/

3. Make it executable:
   chmod +x ~/Library/Application\ Support/SwiftBar/Plugins/claude-usage.60s.py

4. Restart SwiftBar

REQUIREMENTS:
─────────────
• macOS 11 Big Sur or later
• Python 3.8+
• SwiftBar
• Claude Code (logged in)

CONFIGURATION:
──────────────
Config file: ~/.config/claude-monitor/config.json

Customize thresholds, display options, and more.
See README.md for details.

TROUBLESHOOTING:
────────────────
• Widget shows ⚙️ → Log in to Claude Code first
• Widget shows 🌐 → Check internet connection
• Widget shows 🔐 → Re-authenticate Claude Code

For help: https://github.com/watchthelight/ClaudeMonitor-macOS

EOF

# Create the DMG
echo "Creating DMG..."

# Remove old DMG if exists
rm -f "$DIST_DIR/${DMG_NAME}.dmg"

# Create DMG using hdiutil
hdiutil create \
    -volname "$APP_NAME" \
    -srcfolder "$STAGING" \
    -ov \
    -format UDZO \
    "$DIST_DIR/${DMG_NAME}.dmg"

# Clean up staging
rm -rf "$STAGING"

echo ""
echo "═══════════════════════════════════════════"
echo "✓ DMG created: $DIST_DIR/${DMG_NAME}.dmg"
echo ""
echo "Size: $(du -h "$DIST_DIR/${DMG_NAME}.dmg" | cut -f1)"
echo ""

# Code signing instructions
echo "To sign the DMG (requires Apple Developer ID):"
echo "  codesign --force --sign \"Developer ID Application: YOUR NAME\" \\"
echo "    \"$DIST_DIR/${DMG_NAME}.dmg\""
echo ""
echo "To notarize (required for distribution):"
echo "  xcrun notarytool submit \"$DIST_DIR/${DMG_NAME}.dmg\" \\"
echo "    --apple-id YOUR_APPLE_ID \\"
echo "    --password YOUR_APP_PASSWORD \\"
echo "    --team-id YOUR_TEAM_ID \\"
echo "    --wait"
echo ""
echo "  xcrun stapler staple \"$DIST_DIR/${DMG_NAME}.dmg\""
echo ""
