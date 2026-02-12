#!/usr/bin/env python3
"""Guard translation sensor keys against regressions."""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONST_PATH = ROOT / "custom_components" / "solax_cloud_api" / "const.py"
TRANSLATIONS_DIR = ROOT / "custom_components" / "solax_cloud_api" / "translations"

VALID_KEY = re.compile(r"^[a-z0-9-_]+$")

# These are created in sensor.py but not part of RESULT_FIELDS in const.py.
EXTRA_SENSOR_KEYS = (
    "inverterEfficiency",
    "dc_total_inverter",
    "ac_total",
    "dc_total",
    "systemEfficiency",
    "systemHealth",
    "rateLimitStatus",
    "lastPollAttempt",
    "nextScheduledPoll",
    "apiAccessStatus",
    "yieldtoday_total",
    "yieldtotal_total",
)


def normalize_sensor_key(sensor_key: str) -> str:
    key = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(sensor_key))
    key = re.sub(r"[^a-zA-Z0-9_-]+", "_", key)
    return key.lower().strip("_-")


def extract_assignment_literal(module_ast: ast.Module, assignment_name: str):
    for node in module_ast.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == assignment_name:
                return ast.literal_eval(node.value)
    raise ValueError(f"Assignment '{assignment_name}' not found in {CONST_PATH}")


def expected_sensor_keys() -> set[str]:
    module_ast = ast.parse(CONST_PATH.read_text(encoding="utf-8"))
    result_fields = extract_assignment_literal(module_ast, "RESULT_FIELDS")
    if not isinstance(result_fields, list):
        raise TypeError("RESULT_FIELDS must be a list")
    keys = {normalize_sensor_key(k) for k in result_fields}
    keys.update(normalize_sensor_key(k) for k in EXTRA_SENSOR_KEYS)
    return keys


def check_translation_file(path: Path, expected_keys: set[str]) -> tuple[list[str], set[str]]:
    issues: list[str] = []
    data = json.loads(path.read_text(encoding="utf-8"))
    sensors = data.get("entity", {}).get("sensor")

    if not isinstance(sensors, dict):
        return [f"{path}: entity.sensor is missing or not an object"], set()

    sensor_keys = set(sensors.keys())
    invalid_format = sorted(
        key
        for key in sensor_keys
        if not VALID_KEY.fullmatch(key)
        or key.startswith(("-", "_"))
        or key.endswith(("-", "_"))
    )
    if invalid_format:
        issues.append(f"{path}: invalid key format: {', '.join(invalid_format)}")

    missing = sorted(expected_keys - sensor_keys)
    if missing:
        issues.append(f"{path}: missing expected sensor keys: {', '.join(missing)}")

    switch_name = (
        data.get("entity", {})
        .get("switch", {})
        .get("rate_limit_notifications", {})
        .get("name")
    )
    if not switch_name:
        issues.append(f"{path}: missing entity.switch.rate_limit_notifications.name")

    return issues, sensor_keys


def discover_translation_paths() -> list[Path]:
    return sorted(path for path in TRANSLATIONS_DIR.glob("*.json") if path.is_file())


def main() -> int:
    expected = expected_sensor_keys()
    all_issues: list[str] = []
    key_sets: dict[str, set[str]] = {}

    translation_paths = discover_translation_paths()
    if not translation_paths:
        print(f"Translation key guard failed: no translation files found in {TRANSLATIONS_DIR}")
        return 1

    for path in translation_paths:
        issues, sensor_keys = check_translation_file(path, expected)
        all_issues.extend(issues)
        key_sets[path.name] = sensor_keys

    if "en.json" not in key_sets:
        all_issues.append("Missing required baseline translation file: en.json")
        en_keys: set[str] = set()
    else:
        en_keys = key_sets["en.json"]

    for filename, keys in key_sets.items():
        if filename == "en.json":
            continue

        missing_in_lang = sorted(en_keys - keys)
        extra_in_lang = sorted(keys - en_keys)
        if missing_in_lang:
            all_issues.append(
                f"{filename} missing keys present in en.json: {', '.join(missing_in_lang)}"
            )
        if extra_in_lang:
            all_issues.append(
                f"{filename} has extra keys not in en.json: {', '.join(extra_in_lang)}"
            )

    if all_issues:
        print("Translation key guard failed:")
        for issue in all_issues:
            print(f" - {issue}")
        return 1

    print(
        f"Translation key guard passed ({len(expected)} expected sensor keys, "
        f"{len(translation_paths)} language file(s))."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
