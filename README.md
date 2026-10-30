# ParasiteAI

A 100% visible, desktop-native local AI assistant operating on the user's physical Windows desktop with zero headless browsers, zero invisible scrapers, and zero CLI-only interfaces.

## Quickstart

```bash
# Sync environment and dependencies
uv sync

# Run tests
uv run pytest

# Launch companion
uv run python main.py
```

## Features
- **Zero-Config Local Brain Management**: Seamlessly run with local GGUF models or instant Zero-VRAM Browser Offload mode.
- **Physical Hand Kinematics**: Human-like mouse trajectories using Cubic Bézier curves, min-jerk velocity profiles, micro-jitter, and overshoot.
- **Sub-2ms Hardware Interrupt**: Instant cancellation on physical mouse or keyboard touch via Win32 low-level hardware hooks.
- **Visible Desktop Companion Dock & Ghost-Hand HUD**: Real-time status display and transparent Set-of-Mark visual targeting overlay.
