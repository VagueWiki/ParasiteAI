## 2024-11-07 - Discoverability of Hardware Interrupts
**Learning:** In desktop-native AI agents where safety mechanisms like Panic Aborts can be triggered globally via keyboard hooks (e.g. Esc, Ctrl+Alt+P), the UI needs to explicitly surface these shortcuts. Otherwise, users may only click the UI button instead of using the faster, safer hardware interrupt when necessary.
**Action:** Always add keyboard shortcut hints to tooltips and accessible names for critical safety/interrupt controls in desktop UI.
