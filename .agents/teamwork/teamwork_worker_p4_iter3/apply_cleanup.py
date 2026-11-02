"""
apply_cleanup.py - Surgical Text Cleanup for phase_4_master_plan.md (Iter 3)
"""
from pathlib import Path
import sys

TARGET_PATH = Path(r"c:\Users\Suici\.gemini\antigravity\brain\464b4ef0-398b-45b1-94dc-857256a38046\phase_4_master_plan.md")
MIRROR_PATH = Path(r"c:\Users\Suici\.gemini\antigravity\brain\c0750c5c-4354-4aa0-b198-17e98f598cf7\phase_4_master_plan.md")

def main():
    if not TARGET_PATH.exists():
        print(f"Error: {TARGET_PATH} not found")
        sys.exit(1)
        
    content = TARGET_PATH.read_text(encoding="utf-8")
    original_len = len(content)
    print(f"Read target file: {original_len} characters")
    
    # 1. Clean Section 5.2 (lines 578-584):
    # Remove the stray duplicate block:
    # ```json[\s\S]*?```", "", text)
    #         text = re.sub(r"[{}\[\]\"]", "", text)
    #         text = re.sub(r"\b\d+x\d+\b", "", text)
    #         text = re.sub(r"\(\d+,\s*\d+\)", "", text)
    #         return " ".join(text.split()).strip()
    stray_block = (
        '```json[\\s\\S]*?```", "", text)\n'
        '        text = re.sub(r"[{}\\[\\]\\"]", "", text)\n'
        '        text = re.sub(r"\\b\\d+x\\d+\\b", "", text)\n'
        '        text = re.sub(r"\\(\\d+,\\s*\\d+\\)", "", text)\n'
        '        return " ".join(text.split()).strip()\n'
    )
    if stray_block not in content:
        stray_block_crlf = stray_block.replace('\n', '\r\n')
        if stray_block_crlf in content:
            stray_block = stray_block_crlf
        else:
            print("ERROR: stray_block not found in content!")
            sys.exit(1)
            
    content = content.replace(stray_block, "")
    print("Cleanup 1 applied: removed stray block in Section 5.2")
    
    # 2. Clean Docstrings Across Master Plan:
    # Replace all 12 occurrences of literal escaped \"\"\" with unescaped """
    escaped_docstring = chr(92) + chr(34) + chr(92) + chr(34) + chr(92) + chr(34)
    esc_count = content.count(escaped_docstring)
    print(f"Found {esc_count} occurrences of literal escaped docstring")
    if esc_count != 12:
        print(f"ERROR: Expected 12 occurrences, found {esc_count}")
        sys.exit(1)
        
    content = content.replace(escaped_docstring, '"""')
    print("Cleanup 2 applied: replaced 12 escaped docstrings with unescaped triple quotes")
    
    # 3. Seal CLI Sandbox Web Scraping Loophole (Section 6.4):
    # In CLIExecutionSandbox.FORBIDDEN_PATTERNS, append:
    #         r"\b(?:Invoke-WebRequest|iwr|Invoke-RestMethod|irm)\b",
    #         r"\brequests\b",
    target_forbidden_old = (
        '        r"\\bshutdown\\b",\n'
        '        r"\\bstop-computer\\b",\n'
        '    ]'
    )
    target_forbidden_new = (
        '        r"\\bshutdown\\b",\n'
        '        r"\\bstop-computer\\b",\n'
        '        r"\\b(?:Invoke-WebRequest|iwr|Invoke-RestMethod|irm)\\b",\n'
        '        r"\\brequests\\b",\n'
        '    ]'
    )
    if target_forbidden_old not in content:
        target_forbidden_old_crlf = target_forbidden_old.replace('\n', '\r\n')
        target_forbidden_new = target_forbidden_new.replace('\n', '\r\n')
        if target_forbidden_old_crlf in content:
            target_forbidden_old = target_forbidden_old_crlf
        else:
            print("ERROR: target_forbidden_old not found in content!")
            sys.exit(1)
            
    content = content.replace(target_forbidden_old, target_forbidden_new, 1)
    print("Cleanup 3 applied: sealed CLI sandbox web scraping loophole")
    
    # Write back to target
    TARGET_PATH.write_text(content, encoding="utf-8")
    print(f"Successfully wrote {TARGET_PATH}")
    
    # Write back to mirror
    MIRROR_PATH.write_text(content, encoding="utf-8")
    print(f"Successfully synchronized {MIRROR_PATH}")
    print("All cleanups complete.")

if __name__ == "__main__":
    main()
