"""
Unit tests for Foreground Window Guard & Privacy Shield.
Verifies fail-safe handling on null hwnd/inaccessible process, process and title blacklists,
and immutability of window snapshot data.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from parasite_ai.config import SafetyConfig
from parasite_ai.safety.window_guard import (
    DEFAULT_SENSITIVE_PROCESSES,
    DEFAULT_SENSITIVE_TITLES,
    WindowGuard,
    WindowGuardedException,
    WindowInfo,
)


class TestWindowGuardSensitivityEvaluator:
    """Tests pure deterministic sensitivity evaluator logic."""

    def test_null_hwnd_failsafe_protected(self):
        guard = WindowGuard()
        is_sens, reason = guard.evaluate_sensitivity(
            title="Desktop",
            process_name="explorer.exe",
            hwnd=0,
            can_open_process=True,
        )
        assert is_sens is True
        assert "hwnd == 0" in reason

    def test_access_denied_process_protected(self):
        guard = WindowGuard()
        is_sens, reason = guard.evaluate_sensitivity(
            title="Protected Process Window",
            process_name="protected.exe",
            hwnd=12345,
            can_open_process=False,
        )
        assert is_sens is True
        assert "access denied" in reason.lower()

    def test_blacklist_password_managers(self):
        guard = WindowGuard()

        # By process name
        for proc in ["bitwarden.exe", "1password.exe", "keepass.exe", "keepassxc.exe"]:
            is_sens, reason = guard.evaluate_sensitivity(
                title="Vault",
                process_name=proc,
                hwnd=100,
                can_open_process=True,
            )
            assert is_sens is True
            assert "Sensitive process" in reason

        # By title
        for title in ["Bitwarden - Master Vault", "1Password Unlocked", "KeePass Password Safe"]:
            is_sens, reason = guard.evaluate_sensitivity(
                title=title,
                process_name="browser.exe",
                hwnd=100,
                can_open_process=True,
            )
            assert is_sens is True
            assert "Sensitive window title" in reason

    def test_blacklist_system_tools(self):
        guard = WindowGuard()
        for proc in ["taskmgr.exe", "regedit.exe", "credentialui.exe", "consent.exe"]:
            is_sens, reason = guard.evaluate_sensitivity(
                title="Tool",
                process_name=proc,
                hwnd=100,
                can_open_process=True,
            )
            assert is_sens is True

    def test_blacklist_elevated_console(self):
        guard = WindowGuard()
        titles = [
            "Administrator: Command Prompt",
            "Administrator: Windows PowerShell",
            "administrator: cmd.exe",
        ]
        for title in titles:
            is_sens, reason = guard.evaluate_sensitivity(
                title=title,
                process_name="conhost.exe",
                hwnd=100,
                can_open_process=True,
            )
            assert is_sens is True
            assert ("elevated" in reason.lower() or "administrator" in reason.lower() or "sensitive window title" in reason.lower())

    def test_whitelisted_safe_window(self):
        guard = WindowGuard()
        safe_windows = [
            ("Google Chrome", "chrome.exe"),
            ("Visual Studio Code", "code.exe"),
            ("Spotify Free", "spotify.exe"),
            ("Notepad", "notepad.exe"),
        ]
        for title, proc in safe_windows:
            is_sens, reason = guard.evaluate_sensitivity(
                title=title,
                process_name=proc,
                hwnd=100,
                can_open_process=True,
            )
            assert is_sens is False
            assert reason == "Window is safe to operate"

    def test_custom_blacklist(self):
        guard = WindowGuard(
            custom_process_blacklist=["secret_app.exe"],
            custom_title_blacklist=["Confidential Internal Portal"],
        )
        is_sens, reason = guard.evaluate_sensitivity(
            title="My Screen",
            process_name="secret_app.exe",
            hwnd=100,
            can_open_process=True,
        )
        assert is_sens is True

        is_sens, reason = guard.evaluate_sensitivity(
            title="Confidential Internal Portal - Home",
            process_name="chrome.exe",
            hwnd=100,
            can_open_process=True,
        )
        assert is_sens is True

    def test_safety_config_integration(self):
        cfg = SafetyConfig(
            sensitive_process_names=["custom_pw.exe"],
            sensitive_window_titles=["Custom Safe Vault"],
        )
        guard = WindowGuard(config=cfg)

        is_sens, _ = guard.evaluate_sensitivity(
            title="Anything",
            process_name="custom_pw.exe",
            hwnd=100,
            can_open_process=True,
        )
        assert is_sens is True

        is_sens, _ = guard.evaluate_sensitivity(
            title="Custom Safe Vault - Account",
            process_name="other.exe",
            hwnd=100,
            can_open_process=True,
        )
        assert is_sens is True


class TestWindowGuardAPIAndDataModels:
    """Tests WindowInfo dataclass, WindowGuardedException, and API methods."""

    def test_window_info_dataclass_immutability(self):
        info = WindowInfo(
            hwnd=100,
            title="Test Window",
            class_name="TestClass",
            process_name="test.exe",
            process_path="C:\\test.exe",
            pid=1234,
            rect=(0, 0, 800, 600),
            is_sensitive=False,
            reason="Safe",
        )
        assert info.hwnd == 100
        assert info.title == "Test Window"

        with pytest.raises((AttributeError, TypeError)):
            info.title = "Modified Title"  # type: ignore

    def test_window_guarded_exception(self):
        exc = WindowGuardedException("Access blocked: Bitwarden vault is active")
        assert isinstance(exc, RuntimeError)
        assert "Bitwarden" in str(exc)

    def test_get_active_window_and_is_safe_to_operate(self):
        guard = WindowGuard()

        mock_info_safe = WindowInfo(
            hwnd=100,
            title="Google Chrome",
            class_name="Chrome_WidgetWin_1",
            process_name="chrome.exe",
            process_path="C:\\chrome.exe",
            pid=2000,
            rect=(0, 0, 1920, 1080),
            is_sensitive=False,
            reason="Window is safe to operate",
        )

        with patch.object(guard, "get_active_window_info", return_value=mock_info_safe):
            assert guard.is_safe_to_operate() is True
            assert guard.get_active_window() == mock_info_safe

        mock_info_sensitive = WindowInfo(
            hwnd=200,
            title="Bitwarden",
            class_name="Chrome_WidgetWin_1",
            process_name="bitwarden.exe",
            process_path="C:\\bitwarden.exe",
            pid=3000,
            rect=(100, 100, 500, 700),
            is_sensitive=True,
            reason="Sensitive process matched: 'bitwarden.exe'",
        )

        with patch.object(guard, "get_active_window_info", return_value=mock_info_sensitive):
            assert guard.is_safe_to_operate() is False
            assert guard.get_active_window() == mock_info_sensitive
