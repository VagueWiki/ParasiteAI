## 2024-11-06 - AABB pre-checks for dense bounding box IoU
**Learning:** In dense UI screens where OCR and UIA trees return hundreds of bounding boxes, O(N²) collision checks using full IoU and containment algorithms become a measurable bottleneck during screen grounding.
**Action:** Always consider adding fast AABB (Axis-Aligned Bounding Box) intersection pre-checks before running expensive collision or overlap algorithms in nested loops to short-circuit non-overlapping pairs and avoid unnecessary floating-point operations.
