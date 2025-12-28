# Claude Monitor Makefile
# ========================

VERSION := 2.0.0
PLUGIN := src/claude-usage.60s.py
SWIFTBAR_PLUGINS := $(HOME)/Library/Application Support/SwiftBar/Plugins

.PHONY: all build install test clean release help

# Default target
all: help

# Build DMG installer
build:
	@chmod +x installer/build-dmg.sh
	@VERSION=$(VERSION) ./installer/build-dmg.sh

# Install locally (for development)
install:
	@chmod +x installer/install.sh
	@./installer/install.sh

# Quick install (just copy plugin)
quick-install:
	@mkdir -p "$(SWIFTBAR_PLUGINS)"
	@cp $(PLUGIN) "$(SWIFTBAR_PLUGINS)/claude-usage.60s.py"
	@chmod +x "$(SWIFTBAR_PLUGINS)/claude-usage.60s.py"
	@echo "✓ Installed to $(SWIFTBAR_PLUGINS)"
	@osascript -e 'tell application "SwiftBar" to refresh all' 2>/dev/null || true

# Run plugin directly (for testing)
test:
	@python3 $(PLUGIN)

# Run plugin with debug output
debug:
	@python3 -u $(PLUGIN) 2>&1

# Clean build artifacts
clean:
	@rm -rf dist/
	@rm -rf /tmp/claude-monitor-dmg
	@rm -rf __pycache__
	@rm -rf src/__pycache__
	@find . -name "*.pyc" -delete
	@echo "✓ Cleaned"

# Create GitHub release
release: clean build
	@echo "Creating GitHub release v$(VERSION)..."
	@gh release create v$(VERSION) dist/*.dmg \
		--title "v$(VERSION)" \
		--notes-file CHANGELOG.md \
		--draft
	@echo "✓ Draft release created. Review and publish on GitHub."

# Lint Python code
lint:
	@python3 -m py_compile $(PLUGIN)
	@echo "✓ Syntax OK"

# Show help
help:
	@echo ""
	@echo "Claude Monitor v$(VERSION)"
	@echo "========================="
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@echo "  build         Build DMG installer"
	@echo "  install       Run full installer"
	@echo "  quick-install Copy plugin to SwiftBar (dev)"
	@echo "  test          Run plugin and show output"
	@echo "  debug         Run with debug output"
	@echo "  clean         Remove build artifacts"
	@echo "  release       Create GitHub release (draft)"
	@echo "  lint          Check Python syntax"
	@echo "  help          Show this help"
	@echo ""
