from pathlib import Path
import re

TARGET_PATH = Path(r"c:\Users\Suici\.gemini\antigravity\brain\464b4ef0-398b-45b1-94dc-857256a38046\phase_4_master_plan.md")
content = TARGET_PATH.read_text(encoding="utf-8")

# Find all ```python blocks
pattern = re.compile(r"```python\s*\n(.*?)```", re.DOTALL)
matches = list(pattern.finditer(content))
print(f"Found {len(matches)} python blocks.")

for i, m in enumerate(matches, 1):
    block = m.group(1)
    # Check if block compiles
    try:
        compile(block, f"<block_{i}>", "exec")
        print(f"Block {i}: OK (lines {content[:m.start()].count('\n')+1} to {content[:m.end()].count('\n')+1})")
    except SyntaxError as e:
        print(f"Block {i}: SYNTAX ERROR at line {e.lineno} (doc line {content[:m.start()].count('\n')+1 + e.lineno}): {e.msg}")
        print("--- Problem snippet ---")
        lines = block.splitlines()
        start = max(0, e.lineno - 3)
        end = min(len(lines), e.lineno + 3)
        for idx in range(start, end):
            print(f"{idx+1}: {lines[idx]}")
        print("-----------------------")
