# Changelog

All notable changes to Claude Monitor will be documented in this file.

## [2.0.0] - 2025-12-28

### Added
- **Sparkline History**: Visual usage trend in menu bar (`30% ▁▂▃▄▅▆▇`)
- **Smooth Color Gradients**: Colors transition smoothly from green→yellow→orange→red
- **Progress Bars**: Visual progress indicators (`███░░░░░░░`)
- **Trend Indicators**: Shows usage trend with arrows (↑↓→)
- **Configuration System**: Customizable thresholds and display options
- **Offline Caching**: Shows cached data when network unavailable
- **Retry Logic**: Automatic retry with exponential backoff
- **Graceful Error Handling**: Clear error messages for different failure modes
- **Settings Menu**: Toggle sparkline, compact mode, open config
- **DMG Installer**: Professional installer with setup wizard

### Changed
- Complete rewrite for robustness and reliability
- Specific exception handling (no more bare `except:`)
- Improved API response validation
- Better time formatting

### Fixed
- Handles missing/null API fields gracefully
- Validates percentage values (0-100 range)
- Recovers from network failures with cached data

## [1.4.0] - 2025-12-28

### Added
- Real API data from `/api/oauth/usage` endpoint
- Exact usage percentages matching `/status` command

### Changed
- Removed local file parsing
- Simplified implementation (~60% less code)

## [1.3.0] - 2025-12-28

### Added
- OAuth token extraction from macOS Keychain
- Plan tier detection via `/api/oauth/profile`
- Per-plan calibrated limits (Max 20x, Max 5x, Pro)

## [1.2.0] - 2025-12-28

### Added
- Calibrated usage percentages based on real `/status` data
- Plan-specific limits

## [1.1.0] - 2025-12-28

### Changed
- Show raw usage data instead of estimated percentages

## [1.0.0] - 2025-12-28

### Added
- Initial release
- SwiftBar plugin for macOS menu bar
- Usage tracking from local session files
- Color-coded status indicators
