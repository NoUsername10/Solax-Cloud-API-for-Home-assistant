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
PLACEHOLDER_RE = re.compile(r"{([a-zA-Z0-9_]+)}")

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
    "estimatedBatteryChargeEnergyToday",
    "estimatedBatteryChargeEnergyTotal",
    "estimatedBatteryDischargeEnergyToday",
    "estimatedBatteryDischargeEnergyTotal",
    "estimatedSystemBatteryChargeEnergyToday",
    "estimatedSystemBatteryChargeEnergyTotal",
    "estimatedSystemBatteryDischargeEnergyToday",
    "estimatedSystemBatteryDischargeEnergyTotal",
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


def collect_structure(node, prefix: str = "") -> tuple[dict[str, str], dict[str, str]]:
    """Return structure map and string leaf values for placeholder checks."""
    structure: dict[str, str] = {}
    strings: dict[str, str] = {}

    if isinstance(node, dict):
        if prefix:
            structure[prefix] = "dict"
        for key, value in node.items():
            child = f"{prefix}.{key}" if prefix else key
            child_structure, child_strings = collect_structure(value, child)
            structure.update(child_structure)
            strings.update(child_strings)
        return structure, strings

    if isinstance(node, list):
        structure[prefix] = "list"
        return structure, strings

    if isinstance(node, str):
        structure[prefix] = "str"
        strings[prefix] = node
        return structure, strings

    structure[prefix] = type(node).__name__
    return structure, strings


def extract_placeholders(value: str) -> set[str]:
    return set(PLACEHOLDER_RE.findall(value))


def discover_translation_paths() -> list[Path]:
    return sorted(path for path in TRANSLATIONS_DIR.glob("*.json") if path.is_file())


def main() -> int:
    expected = expected_sensor_keys()
    all_issues: list[str] = []
    key_sets: dict[str, set[str]] = {}
    structures: dict[str, dict[str, str]] = {}
    strings_by_lang: dict[str, dict[str, str]] = {}

    translation_paths = discover_translation_paths()
    if not translation_paths:
        print(f"Translation key guard failed: no translation files found in {TRANSLATIONS_DIR}")
        return 1

    parsed_files: dict[str, dict] = {}
    for path in translation_paths:
        parsed_files[path.name] = json.loads(path.read_text(encoding="utf-8"))

    for path in translation_paths:
        data = parsed_files[path.name]
        issues, sensor_keys = check_translation_file(path, expected)
        all_issues.extend(issues)
        key_sets[path.name] = sensor_keys
        structure, strings = collect_structure(data)
        structures[path.name] = structure
        strings_by_lang[path.name] = strings

    if "en.json" not in key_sets:
        all_issues.append("Missing required baseline translation file: en.json")
        en_keys: set[str] = set()
    else:
        en_keys = key_sets["en.json"]

    en_structure = structures.get("en.json", {})
    en_strings = strings_by_lang.get("en.json", {})

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

        lang_structure = structures.get(filename, {})
        lang_strings = strings_by_lang.get(filename, {})

        missing_paths = sorted(set(en_structure) - set(lang_structure))
        extra_paths = sorted(set(lang_structure) - set(en_structure))
        if missing_paths:
            all_issues.append(
                f"{filename} missing translation paths from en.json: {', '.join(missing_paths)}"
            )
        if extra_paths:
            all_issues.append(
                f"{filename} has extra translation paths not in en.json: {', '.join(extra_paths)}"
            )

        common_paths = sorted(set(en_structure) & set(lang_structure))
        type_mismatch = [
            path for path in common_paths if en_structure[path] != lang_structure[path]
        ]
        if type_mismatch:
            all_issues.append(
                f"{filename} has type mismatches vs en.json: "
                + ", ".join(
                    f"{path}({en_structure[path]}!={lang_structure[path]})"
                    for path in type_mismatch
                )
            )

        common_string_paths = sorted(set(en_strings) & set(lang_strings))
        placeholder_mismatch = []
        for path in common_string_paths:
            en_placeholders = extract_placeholders(en_strings[path])
            lang_placeholders = extract_placeholders(lang_strings[path])
            if en_placeholders != lang_placeholders:
                placeholder_mismatch.append(
                    f"{path}(en={sorted(en_placeholders)}, {filename}={sorted(lang_placeholders)})"
                )
        if placeholder_mismatch:
            all_issues.append(
                f"{filename} has placeholder mismatches vs en.json: "
                + ", ".join(placeholder_mismatch)
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
