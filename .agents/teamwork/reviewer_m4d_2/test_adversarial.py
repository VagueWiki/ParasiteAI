import sys
import os
import re
import threading
import time

from parasite_ai.mind.affordance import (
    ActionAffordance,
    AffordanceAssessment,
    AffordanceEvaluator,
    CLIExecutionResult,
    CLIExecutionSandbox,
)

def test_adversarial_patterns():
    # 1. Del/rmdir variations
    del_variations = [
        "del/s file.txt",
        "del/q file.txt",
        "del/f file.txt",
        "rmdir/s dir",
        "rmdir/q dir",
        "del /s/q/f file.txt",
        "rmdir /s/q dir",
    ]
    for cmd in del_variations:
        try:
            CLIExecutionSandbox.sanitize_and_tokenize(f"cmd /c {cmd}")
            print(f"FAILED to catch: {cmd}")
        except PermissionError:
            pass

    # 2. Case variations and scraping tool variations
    scraping_variations = [
        "CURL http://example.com",
        "Wget http://example.com",
        "python -c 'import Requests'",
        "python -c 'import REQUESTS'",
        "python -c 'import PlayWright'",
        "python -c 'import Selenium'",
        "powershell -Command IWR http://example.com",
        "powershell -Command IRM http://example.com",
        "powershell -Command INVOKE-WEBREQUEST http://example.com",
        "powershell -Command INVOKE-RESTMETHOD http://example.com",
        "cmd.exe /c curl.exe",
        "python -m scrapy.crawler",
    ]
    for cmd in scraping_variations:
        try:
            CLIExecutionSandbox.sanitize_and_tokenize(cmd)
            print(f"FAILED to catch scraping: {cmd}")
        except PermissionError:
            pass

    # 3. Path variations in tokenization
    path_cmds = [
        r'python "C:\Users\Suici\test file.py" --opt="val with spaces"',
        r'pytest "C:\Path With Spaces\test_something.py"',
        r'git commit -m "feat: added new feature with backslashes \n and quotes"',
        r'"C:\Program Files\Git\bin\git.exe" status',
    ]
    for cmd in path_cmds:
        tokens = CLIExecutionSandbox.sanitize_and_tokenize(cmd)
        print(f"Parsed tokens for '{cmd}': {tokens}")

    # 4. Binary whitelist checks
    unpermitted = [
        "powershell_fake.exe",
        "python3.exe",  # wait, is python3 permitted? Let's check!
        "sh.exe",
        "wscript.exe",
        "cscript.exe",
        "mshta.exe",
        "rundll32.exe",
    ]
    for binary in unpermitted:
        try:
            CLIExecutionSandbox.sanitize_and_tokenize(binary)
            print(f"FAILED to reject unpermitted binary: {binary}")
        except PermissionError:
            pass

    print("ALL ADVERSARIAL PATTERN TESTS COMPLETED.")

if __name__ == "__main__":
    test_adversarial_patterns()
