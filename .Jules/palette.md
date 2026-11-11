## 2024-05-24 - PyQt6 Interactive Control Accessibility
**Learning:** PyQt6 UI components (like QPushButton, QComboBox, QCheckBox) lack hand cursor and screen reader accessibility names/tooltips by default, requiring explicit `setCursor`, `setAccessibleName`, and `setToolTip` to align with the project's micro-UX standards.
**Action:** Always verify that every interactive PyQt6 component has explicitly defined accessibility names, tooltips, and appropriate cursor shapes (like PointingHandCursor) during component creation.
