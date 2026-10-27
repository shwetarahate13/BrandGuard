#!/usr/bin/env python3
"""Check semantic light/dark theme token contrast against WCAG AA targets."""
from __future__ import annotations

import re
import sys
from pathlib import Path


CSS = Path(__file__).resolve().parents[1] / "frontend" / "src" / "index.css"
HEX = re.compile(r"^#([0-9a-fA-F]{6})$")


def parse_color(value: str) -> tuple[float, float, float]:
    match = HEX.fullmatch(value.strip())
    if not match:
        raise ValueError(f"Expected a six-digit hex token, got {value!r}")
    raw = match.group(1)
    return tuple(int(raw[i : i + 2], 16) / 255 for i in (0, 2, 4))


def luminance(color: tuple[float, float, float]) -> float:
    channels = [component / 12.92 if component <= 0.04045 else ((component + 0.055) / 1.055) ** 2.4 for component in color]
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast(first: tuple[float, float, float], second: tuple[float, float, float]) -> float:
    high, low = sorted((luminance(first), luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def token_blocks(text: str) -> dict[str, dict[str, str]]:
    blocks: dict[str, dict[str, str]] = {}
    for name, selector in (("light", ":root"), ("dark", "html.dark")):
        match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", text, re.S)
        if not match:
            raise ValueError(f"Missing {selector} token block")
        blocks[name] = {
            key.strip(): value.strip()
            for key, value in re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", match.group(1))
        }
    blocks["dark"] = {**blocks["light"], **blocks["dark"]}
    return blocks


def check_theme(name: str, tokens: dict[str, str]) -> list[str]:
    pairs = [
        ("--text-primary", "--surface-page", 4.5),
        ("--text-primary", "--surface-card", 4.5),
        ("--text-body", "--surface-card", 4.5),
        ("--text-secondary", "--surface-card", 4.5),
        ("--text-muted", "--surface-card", 4.5),
        ("--disabled-text", "--disabled-surface", 4.5),
        ("--status-warning-text", "--status-warning-surface", 4.5),
        ("--status-success-text", "--status-success-surface", 4.5),
        ("--status-danger-text", "--status-danger-surface", 4.5),
        ("--status-info-text", "--status-info-surface", 4.5),
        ("--status-purple-text", "--status-purple-surface", 4.5),
        ("--status-orange-text", "--status-orange-surface", 4.5),
        ("--text-inverse", "--action-primary-surface", 4.5),
        ("--text-inverse", "--button-warning-surface", 4.5),
        ("--text-inverse", "--button-success-surface", 4.5),
        ("--text-inverse", "--button-danger-surface", 4.5),
        ("--text-inverse", "--button-purple-surface", 4.5),
        ("--border-control", "--surface-card", 3.0),
        ("--focus-ring", "--surface-card", 3.0),
    ]
    failures = []
    for foreground, background, minimum in pairs:
        try:
            ratio = contrast(parse_color(tokens[foreground]), parse_color(tokens[background]))
        except KeyError as exc:
            failures.append(f"{name}: missing token {exc.args[0]}")
            continue
        if ratio < minimum:
            failures.append(f"{name}: {foreground} on {background} is {ratio:.2f}:1 (needs {minimum:.1f}:1)")
        else:
            print(f"{name}: {foreground} on {background} {ratio:.2f}:1")
    return failures


def main() -> int:
    try:
        themes = token_blocks(CSS.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"Theme contrast check failed: {exc}", file=sys.stderr)
        return 1
    failures = [failure for name, tokens in themes.items() for failure in check_theme(name, tokens)]
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print("Semantic light and dark theme token contrast passes WCAG AA text and UI thresholds.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
