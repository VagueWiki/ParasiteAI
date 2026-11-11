## 2025-01-20 - Memoize PyQT Render Targets
**Learning:** PyQT's paintEvent can fire extremely frequently (e.g. 144Hz) when animating components. If you dynamically format text, instantiate QColors, or calculate QFontMetrics in a for loop of elements within the paintEvent, you will severely degrade performance.
**Action:** Always shift text computation, object instantiation, and sizing calculations out of the paintEvent onto an initialization step or property caching when data structures are passed in.
