#!/usr/bin/env python3
"""Offline Terraform naming planner and conservative literal-name editor."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


VERSION = "1.0.0"
DEFAULT_POLICY = Path(__file__).parent / "policies" / "example" / "policy.json"
BACKUP_DIR = ".naming-backup"
REPORT_NAME = "NAMING-CHANGELOG.md"


class NamingError(Exception):
    """Raised for invalid policy, request, or Terraform input."""


def load_json(path: Path) -> Any:
    try:
        with path.open(encoding="utf-8") as stream:
            return json.load(stream)
    except (OSError, ValueError, UnicodeError) as error:
        detail = (
            error.strerror
            if isinstance(error, OSError)
            else "invalid UTF-8 encoding"
            if isinstance(error, UnicodeError)
            else f"invalid JSON at line {error.lineno}, column {error.colno}"
            if isinstance(error, json.JSONDecodeError)
            else "invalid JSON value"
        )
        raise NamingError(f"Cannot read JSON file '{path.name}': {detail}") from error


def load_policy(path: Path) -> dict[str, Any]:
    policy = load_json(path)
    if not isinstance(policy, dict) or not isinstance(policy.get("rules"), dict):
        raise NamingError("Policy must be an object containing a 'rules' object.")
    normal_case = policy.get("normal_case", "lower")
    if not isinstance(normal_case, str) or normal_case not in {"lower", "upper", "preserve"}:
        raise NamingError("Policy normal_case must be lower, upper, or preserve.")
    code_sets = policy.get("code_sets", {})
    if not isinstance(code_sets, dict):
        raise NamingError("Policy code_sets must be an object.")
    for code_set_name, mapping in code_sets.items():
        if not isinstance(mapping, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in mapping.items()
        ):
            raise NamingError(f"Code set '{code_set_name}' must map strings to strings.")

    for name, rule in policy["rules"].items():
        if not isinstance(rule, dict):
            raise NamingError(f"Rule '{name}' must be an object.")
        status = rule.get("status")
        if not isinstance(status, str) or status not in {
            "approved",
            "draft",
            "conflict",
            "missing",
            "legacy",
        }:
            raise NamingError(f"Rule '{name}' has an unsupported status.")
        components = rule.get("components", [])
        if not isinstance(components, list):
            raise NamingError(f"Rule '{name}' components must be an array.")
        for component in components:
            if not isinstance(component, dict) or not isinstance(component.get("key"), str):
                raise NamingError(f"Rule '{name}' contains an invalid component.")
            code_set = component.get("code_set")
            if code_set is not None and not isinstance(code_set, str):
                raise NamingError(f"Rule '{name}' has an invalid code-set reference.")
            if code_set is not None and code_set not in policy.get("code_sets", {}):
                raise NamingError(f"Rule '{name}' references unknown code set '{code_set}'.")
            if not isinstance(component.get("required", True), bool):
                raise NamingError(f"Rule '{name}' component required flags must be boolean.")
            if "literal" in component and not isinstance(component["literal"], (str, int, float)):
                raise NamingError(f"Rule '{name}' component literals must be strings or numbers.")
        case = rule.get("case")
        if case is not None and (
            not isinstance(case, str) or case not in {"lower", "upper", "preserve"}
        ):
            raise NamingError(f"Rule '{name}' has an unsupported case setting.")
        separator = rule.get("separator", "-")
        if not isinstance(separator, str):
            raise NamingError(f"Rule '{name}' separator must be a string.")
        pattern = rule.get("pattern")
        if not isinstance(pattern, str):
            raise NamingError(f"Rule '{name}' must have a regex pattern string.")
        try:
            re.compile(pattern)
        except re.error as error:
            raise NamingError(f"Rule '{name}' has an invalid regex pattern: {error.msg}.") from error
        for length_key in ("min_length", "max_length"):
            length = rule.get(length_key)
            if length is not None and (type(length) is not int or length < 0):
                raise NamingError(f"Rule '{name}' {length_key} must be a non-negative integer.")
        if (
            rule.get("min_length") is not None
            and rule.get("max_length") is not None
            and rule["min_length"] > rule["max_length"]
        ):
            raise NamingError(f"Rule '{name}' min_length cannot exceed max_length.")
        resource_types = rule.get("terraform_resource_types", [])
        if not isinstance(resource_types, list) or not all(
            isinstance(resource_type, str) for resource_type in resource_types
        ):
            raise NamingError(f"Rule '{name}' terraform_resource_types must be an array of strings.")
    return policy


def generate_name(
    policy: dict[str, Any], rule_name: str, values: dict[str, Any]
) -> tuple[str, list[str]]:
    rules = policy["rules"]
    if rule_name not in rules:
        raise NamingError(f"No rule named '{rule_name}'.")
    rule = rules[rule_name]
    if rule["status"] == "missing":
        raise NamingError(f"Rule '{rule_name}' is marked missing and cannot generate a name.")
    components = rule.get("components", [])
    code_sets = policy.get("code_sets", {})
    selected_case = rule.get("case", policy.get("normal_case", "lower"))
    pieces: list[str] = []
    missing: list[str] = []

    for component in components:
        key = component["key"]
        if "literal" in component:
            value = str(component["literal"])
        else:
            raw_value = values.get(key)
            if raw_value is None or not str(raw_value).strip():
                if component.get("required", True):
                    missing.append(key)
                continue
            value = str(raw_value).strip()
            code_set = component.get("code_set")
            if code_set:
                mapping = code_sets[code_set]
                value = mapping.get(value.lower(), mapping.get(value, value))
        if selected_case == "lower":
            value = value.lower()
        elif selected_case == "upper":
            value = value.upper()
        if value:
            pieces.append(value)

    if missing:
        raise NamingError(f"Missing required components: {', '.join(missing)}.")

    name = str(rule.get("separator", "-")).join(pieces)
    pattern = rule.get("pattern")
    if pattern and re.fullmatch(pattern, name) is None:
        raise NamingError(f"Generated name does not match the pattern for rule '{rule_name}'.")
    if rule.get("min_length") is not None and len(name) < rule["min_length"]:
        raise NamingError(f"Generated name is shorter than {rule['min_length']} characters.")
    if rule.get("max_length") is not None and len(name) > rule["max_length"]:
        raise NamingError(f"Generated name exceeds {rule['max_length']} characters.")
    return name, []


def _read_string(text: str, position: int) -> tuple[str, int] | None:
    if position >= len(text) or text[position] != '"':
        return None
    index = position + 1
    escaped = False
    while index < len(text):
        char = text[index]
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == '"':
            token = text[position : index + 1]
            try:
                return json.loads(token), index + 1
            except json.JSONDecodeError:
                return token[1:-1], index + 1
        index += 1
    return None


def _mask_comments_and_heredocs(text: str) -> str:
    chars = list(text)
    index = 0
    in_string = False
    escaped = False
    heredoc_end: str | None = None

    while index < len(text):
        if heredoc_end is not None:
            line_end = text.find("\n", index)
            if line_end < 0:
                line_end = len(text)
            if text[index:line_end].strip().removesuffix("\r") == heredoc_end:
                heredoc_end = None
            for offset in range(index, line_end):
                if chars[offset] != "\r":
                    chars[offset] = " "
            index = line_end + 1 if line_end < len(text) else line_end
            continue

        char = text[index]
        next_char = text[index + 1] if index + 1 < len(text) else ""

        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue

        if char == '"':
            in_string = True
            index += 1
            continue
        if char == "<" and text[index : index + 2] == "<<":
            match = re.match(r"<<-?([A-Za-z_][A-Za-z0-9_]*)", text[index:])
            if match:
                heredoc_end = match.group(1)
                index += len(match.group(0))
                continue
        if char == "#" or (char == "/" and next_char == "/"):
            line_end = text.find("\n", index)
            if line_end < 0:
                line_end = len(text)
            for offset in range(index, line_end):
                if chars[offset] != "\r":
                    chars[offset] = " "
            index = line_end
            continue
        if char == "/" and next_char == "*":
            end = text.find("*/", index + 2)
            if end < 0:
                raise NamingError("Terraform file has an unterminated block comment.")
            for offset in range(index, end + 2):
                if chars[offset] not in "\r\n":
                    chars[offset] = " "
            index = end + 2
            continue
        index += 1

    return "".join(chars)


def _skip_space(text: str, position: int) -> int:
    while position < len(text) and text[position].isspace():
        position += 1
    return position


def _find_block_end(text: str, opening_brace: int) -> int | None:
    depth = 0
    index = opening_brace
    while index < len(text):
        char = text[index]
        if char == '"':
            parsed = _read_string(text, index)
            if parsed is None:
                return None
            _, index = parsed
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index + 1
        index += 1
    return None


def _iter_resource_blocks(text: str) -> list[dict[str, Any]]:
    masked = _mask_comments_and_heredocs(text)
    resources: list[dict[str, Any]] = []
    depth = 0
    index = 0

    while index < len(masked):
        char = masked[index]
        if char == '"':
            parsed = _read_string(masked, index)
            if parsed is None:
                raise NamingError("Terraform file contains an unterminated string.")
            _, index = parsed
            continue
        if char == "{":
            depth += 1
            index += 1
            continue
        if char == "}":
            depth -= 1
            if depth < 0:
                raise NamingError("Terraform file contains an unmatched closing brace.")
            index += 1
            continue

        if depth == 0 and masked.startswith("resource", index):
            before = masked[index - 1] if index else " "
            after_index = index + len("resource")
            after = masked[after_index] if after_index < len(masked) else " "
            if (before.isalnum() or before == "_") or (after.isalnum() or after == "_"):
                index += 1
                continue
            cursor = _skip_space(masked, after_index)
            resource_type = _read_string(masked, cursor)
            if resource_type is None:
                index += 1
                continue
            cursor = _skip_space(masked, resource_type[1])
            label = _read_string(masked, cursor)
            if label is None:
                index += 1
                continue
            cursor = _skip_space(masked, label[1])
            if cursor >= len(masked) or masked[cursor] != "{":
                index += 1
                continue
            end = _find_block_end(masked, cursor)
            if end is None:
                raise NamingError(f"Resource block {resource_type[0]}.{label[0]} is unclosed.")
            resources.append(
                {
                    "type": resource_type[0],
                    "label": label[0],
                    "address": f"{resource_type[0]}.{label[0]}",
                    "start": index,
                    "open": cursor,
                    "end": end,
                    "text": masked,
                }
            )
            index = end
            continue
        index += 1

    if depth != 0:
        raise NamingError("Terraform file contains unbalanced braces.")
    return resources


def _find_name_attribute(block: dict[str, Any]) -> dict[str, Any]:
    text = block["text"]
    depth = 1
    index = block["open"] + 1
    assignments: list[dict[str, Any]] = []

    while index < block["end"] - 1:
        char = text[index]
        if char == '"':
            parsed = _read_string(text, index)
            if parsed is None:
                return {"kind": "ambiguous"}
            index = parsed[1]
            continue
        if char == "{":
            depth += 1
            index += 1
            continue
        if char == "}":
            depth -= 1
            index += 1
            continue

        if depth == 1 and text.startswith("name", index):
            before = text[index - 1] if index else " "
            after_name = index + 4
            after = text[after_name] if after_name < len(text) else " "
            if (before.isalnum() or before in "_.") or (after.isalnum() or after == "_"):
                index += 1
                continue
            cursor = _skip_space(text, after_name)
            if cursor >= len(text) or text[cursor] != "=":
                index += 1
                continue
            cursor = _skip_space(text, cursor + 1)
            parsed = _read_string(text, cursor)
            if parsed is None:
                assignments.append({"kind": "expression"})
                index = cursor
                continue
            value, value_end = parsed
            token = text[cursor:value_end]
            if "${" in token or "%{" in token:
                assignments.append({"kind": "expression"})
                index = value_end
                continue
            line_end = text.find("\n", value_end, block["end"])
            if line_end < 0:
                line_end = block["end"] - 1
            trailing = text[value_end:line_end].strip()
            if trailing and not trailing.startswith("}"):
                assignments.append({"kind": "ambiguous"})
            else:
                assignments.append(
                    {
                        "kind": "literal",
                        "value": value,
                        "expected_token": token,
                        "value_start": cursor,
                        "value_end": value_end,
                    }
                )
            index = value_end
            continue
        index += 1

    if len(assignments) != 1:
        return {"kind": "missing" if not assignments else "ambiguous"}
    return assignments[0]


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def iter_terraform_files(root: Path) -> list[Path]:
    files: list[Path] = []
    ignored_directories = {".terraform", ".git", BACKUP_DIR, "__pycache__"}
    for current, directories, filenames in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        directories[:] = [
            name
            for name in directories
            if name not in ignored_directories
            and not is_link_or_junction(current_path / name)
        ]
        for name in filenames:
            path = current_path / name
            if name.endswith(".tf") and not is_link_or_junction(path):
                files.append(path)
    return sorted(files)


def scan_terraform(root: Path) -> list[dict[str, Any]]:
    resources: list[dict[str, Any]] = []
    for path in iter_terraform_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            detail = error.strerror if isinstance(error, OSError) else "invalid UTF-8 text"
            raise NamingError(f"Cannot read Terraform file '{path.name}': {detail}") from error
        for block in _iter_resource_blocks(text):
            name = _find_name_attribute(block)
            resources.append(
                {
                    **block,
                    "path": path,
                    "relative_path": path.relative_to(root),
                    "line": _line_number(text, block["start"]),
                    "name_attribute": name,
                }
            )
    return resources


def _resource_types(rule: dict[str, Any]) -> list[str]:
    return rule.get("terraform_resource_types", [])


def build_plan(
    root: Path, policy: dict[str, Any], requests: dict[str, Any], include_advisory: bool
) -> dict[str, Any]:
    resources = scan_terraform(root)
    by_address: dict[str, list[dict[str, Any]]] = {}
    for resource in resources:
        by_address.setdefault(resource["address"], []).append(resource)
    entries: list[dict[str, Any]] = []

    for address, request in requests.items():
        entry: dict[str, Any] = {"address": address, "status": "blocked"}
        if not isinstance(request, dict) or not isinstance(request.get("rule"), str):
            entry["message"] = "Request must contain a rule name and values object."
            entries.append(entry)
            continue
        matches = by_address.get(address, [])
        root_matches = [
            resource for resource in matches if resource["relative_path"].parent == Path(".")
        ]
        if not root_matches and matches:
            entry["message"] = "Child-module resources are inventory-only; the CLI edits root-module resources only."
            entries.append(entry)
            continue
        if not root_matches:
            entry["message"] = "Terraform resource address was not found in this directory."
            entries.append(entry)
            continue
        if len(root_matches) > 1:
            entry["message"] = "Resource address is ambiguous across files; no edit was planned."
            entries.append(entry)
            continue
        resource = root_matches[0]
        rule_name = request["rule"]
        rule = policy["rules"].get(rule_name)
        if rule is None:
            entry["message"] = f"No policy rule named '{rule_name}'."
            entries.append(entry)
            continue
        if resource["type"] not in _resource_types(rule):
            entry["message"] = f"Rule '{rule_name}' does not cover Terraform type '{resource['type']}'."
            entries.append(entry)
            continue
        if not isinstance(request.get("values", {}), dict):
            entry["message"] = "Request values must be a JSON object."
            entries.append(entry)
            continue
        try:
            proposed, _ = generate_name(policy, rule_name, request.get("values", {}))
        except (NamingError, AttributeError) as error:
            entry["message"] = str(error)
            entries.append(entry)
            continue

        status = rule["status"]
        if status == "missing":
            entry.update(
                {
                    "rule": rule_name,
                    "policy_status": status,
                    "status": "blocked",
                    "message": "Policy is marked missing; no automatic name can be generated.",
                }
            )
            entries.append(entry)
            continue
        if status != "approved" and not include_advisory:
            entry.update(
                {
                    "rule": rule_name,
                    "policy_status": status,
                    "status": "advisory",
                    "message": f"Rule status is '{status}'; use --include-advisory only after policy approval.",
                }
            )
            entries.append(entry)
            continue

        current = resource["name_attribute"]
        entry.update(
            {
                "rule": rule_name,
                "policy_status": status,
                "file": str(resource["relative_path"]),
                "line": resource["line"],
                "proposed": proposed,
                "status": "planned",
            }
        )
        if current["kind"] == "missing":
            entry.update(status="blocked", message="No unique top-level literal 'name' attribute was found.")
        elif current["kind"] == "expression":
            entry.update(status="blocked", message="The name is an expression; automatic edits are not supported.")
        elif current["kind"] == "ambiguous":
            entry.update(status="blocked", message="The name assignment is ambiguous; file left untouched.")
        else:
            entry["current"] = current["value"]
            entry["status"] = "unchanged" if current["value"] == proposed else "planned"
            entry["_edit"] = {
                "path": resource["path"],
                "address": resource["address"],
                "start": current["value_start"],
                "end": current["value_end"],
                "expected_token": current["expected_token"],
                "replacement": json.dumps(proposed, ensure_ascii=False),
            }
        entries.append(entry)

    return {
        "tool_version": VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project": root.name,
        "summary": {
            "resources_scanned": len(resources),
            "requests": len(entries),
            "planned": sum(item["status"] == "planned" for item in entries),
            "unchanged": sum(item["status"] == "unchanged" for item in entries),
            "advisory": sum(item["status"] == "advisory" for item in entries),
            "blocked": sum(item["status"] == "blocked" for item in entries),
        },
        "entries": entries,
    }


def render_report(plan: dict[str, Any]) -> str:
    lines = [
        "# Terraform Naming Changelog",
        "",
        f"Generated: {plan['generated_at']}",
        f"Project: `{plan['project']}`",
        "",
        "## Summary",
        "",
        "| Scanned resources | Requests | Planned | Unchanged | Advisory | Blocked |",
        "| ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    summary = plan["summary"]
    lines.append(
        "| {resources_scanned} | {requests} | {planned} | {unchanged} | {advisory} | {blocked} |".format(
            **summary
        )
    )
    lines.extend(["", "## Resource decisions", ""])
    for entry in plan["entries"]:
        address = entry["address"]
        state = entry["status"].upper()
        if "current" in entry:
            lines.append(
                f"- **{state}** `{address}` - `{entry['current']}` -> `{entry['proposed']}` "
                f"({entry.get('rule')}, {entry.get('file')}:{entry.get('line')})"
            )
        else:
            lines.append(f"- **{state}** `{address}` — {entry.get('message', '')}")
    lines.extend(
        [
            "",
            "Only explicit request values and approved policy rules are applied. "
            "Expressions, ambiguous HCL, and unresolved policy states are never guessed.",
            "",
        ]
    )
    return "\n".join(lines)


def public_plan(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in plan.items()
        if key != "entries"
    } | {
        "entries": [
            {key: value for key, value in entry.items() if not key.startswith("_")}
            for entry in plan["entries"]
        ]
    }


def write_plan(
    plan: dict[str, Any],
    report_path: Path | None,
    json_path: Path | None,
    source_root: Path,
    protected_paths: Sequence[Path] = (),
) -> None:
    if report_path:
        validate_report_destination(source_root, report_path, protected_paths)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(report_path, render_report(plan))
    if json_path:
        validate_report_destination(source_root, json_path, protected_paths)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            json_path,
            json.dumps(public_plan(plan), indent=2, ensure_ascii=False) + "\n",
        )


def apply_plan(
    root: Path,
    plan: dict[str, Any],
    output: Path | None,
    no_backup: bool,
    protected_paths: Sequence[Path] = (),
) -> Path:
    target_root = output.resolve() if output else root.resolve()
    if output:
        target_root = validate_output_directory(root, output)

        def ignore_non_project_files(directory: str, names: list[str]) -> set[str]:
            ignored: set[str] = set()
            for name in names:
                path = Path(directory) / name
                if is_link_or_junction(path):
                    ignored.add(name)
                    continue
                if path.is_dir():
                    if name in {".git", ".terraform", BACKUP_DIR, "__pycache__"}:
                        ignored.add(name)
                    continue
                if (
                    name.endswith(".tf")
                    or name.endswith(".tf.json")
                    or name == ".terraform.lock.hcl"
                    or name.endswith(".tfvars.example")
                ):
                    continue
                ignored.add(name)
            return ignored

        shutil.copytree(
            root,
            target_root,
            dirs_exist_ok=True,
            symlinks=True,
            ignore=ignore_non_project_files,
        )

    edits_by_path: dict[Path, list[dict[str, Any]]] = {}
    for entry in plan["entries"]:
        edit = entry.get("_edit")
        if entry["status"] == "planned" and edit:
            edits_by_path.setdefault(edit["path"], []).append(edit)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup_root = target_root / BACKUP_DIR / timestamp
    report = target_root / REPORT_NAME
    validate_report_destination(root, report, protected_paths)
    destinations: dict[Path, tuple[Path, Path]] = {}
    text_by_path: dict[Path, str] = {}
    for source_path in edits_by_path:
        relative = source_path.relative_to(root)
        destination = target_root / relative
        if is_link_or_junction(source_path):
            raise NamingError(f"Refusing to edit a symbolic link at {relative}.")
        ensure_safe_write_path(destination)
        source_text = source_path.read_text(encoding="utf-8")
        target_text = destination.read_text(encoding="utf-8")
        validate_current_edits(source_text, edits_by_path[source_path], relative)
        validate_current_edits(target_text, edits_by_path[source_path], relative)
        text_by_path[source_path] = target_text
        backup_path = backup_root / relative
        if not no_backup:
            ensure_safe_write_path(backup_path)
        destinations[source_path] = (relative, backup_path)
    if edits_by_path and not no_backup and backup_root.exists():
        raise NamingError("Refusing to overwrite an existing backup directory.")
    for source_path in edits_by_path:
        relative, backup_path = destinations[source_path]
        destination = target_root / relative
        if not no_backup:
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(destination, backup_path)
    for source_path, edits in edits_by_path.items():
        relative, _ = destinations[source_path]
        destination = target_root / relative
        original_text = text_by_path[source_path]
        updated = original_text
        for edit in sorted(edits, key=lambda value: value["apply_start"], reverse=True):
            start, end = edit["apply_start"], edit["apply_end"]
            updated = updated[:start] + edit["replacement"] + updated[end:]
        atomic_write_text(destination, updated)

    atomic_write_text(report, render_report(plan))
    return target_root


def is_link_or_junction(path: Path) -> bool:
    junction_check = getattr(path, "is_junction", None)
    if path.is_symlink() or (junction_check is not None and junction_check()):
        return True
    if os.name == "nt":
        try:
            attributes = getattr(path.lstat(), "st_file_attributes", 0)
        except OSError:
            return False
        is_directory = bool(attributes & 0x10)
        is_reparse_point = bool(attributes & 0x400)
        return is_directory and is_reparse_point
    return False


def ensure_safe_write_path(path: Path) -> None:
    absolute = Path(os.path.abspath(path))
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        if is_link_or_junction(current):
            raise NamingError("Refusing to write through a symbolic link.")
    if absolute.exists() and absolute.is_file() and absolute.stat().st_nlink > 1:
        raise NamingError("Refusing to overwrite a hard-linked file.")


def validate_current_edits(text: str, edits: list[dict[str, Any]], relative: Path) -> None:
    blocks_by_address: dict[str, list[dict[str, Any]]] = {}
    for block in _iter_resource_blocks(text):
        blocks_by_address.setdefault(block["address"], []).append(block)

    for edit in edits:
        matches = blocks_by_address.get(edit["address"], [])
        if len(matches) != 1:
            raise NamingError(f"Resource address changed since planning in {relative}.")
        current = _find_name_attribute(matches[0])
        if (
            current.get("kind") != "literal"
            or current.get("expected_token") != edit["expected_token"]
        ):
            raise NamingError(f"Resource name changed since planning in {relative}.")
        edit["apply_start"] = current["value_start"]
        edit["apply_end"] = current["value_end"]


def atomic_write_text(path: Path, content: str) -> None:
    ensure_safe_write_path(path)
    previous_mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else None
    descriptor, temporary_name = tempfile.mkstemp(prefix=".namingctl-", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if previous_mode is not None:
            os.chmod(temporary_path, previous_mode)
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def validate_output_directory(root: Path, output: Path) -> Path:
    ensure_safe_write_path(output)
    source_root = root.resolve()
    target_root = output.resolve()
    if (
        target_root == source_root
        or source_root in target_root.parents
        or target_root in source_root.parents
    ):
        raise NamingError("--out must be separate from and outside the source directory.")
    if target_root.exists() and any(target_root.iterdir()):
        raise NamingError("Output directory must be empty.")
    return target_root


def validate_report_destination(
    root: Path, path: Path, protected_paths: Sequence[Path] = ()
) -> None:
    ensure_safe_write_path(path)
    destination = path.resolve()
    lowered_name = path.name.casefold()
    terraform_input_suffixes = (
        ".tf",
        ".tf.json",
        ".tfvars",
        ".tfvars.json",
        ".tfbackend",
        ".tfstate",
        ".tfplan",
    )
    if (
        lowered_name == ".terraform.lock.hcl"
        or lowered_name.endswith(terraform_input_suffixes)
        or ".tfstate." in lowered_name
    ):
        raise NamingError("Report output cannot use a Terraform input or state-file name.")
    for source in iter_terraform_files(root):
        if destination == source.resolve():
            raise NamingError("Report output cannot overwrite a Terraform source file.")
    for protected in protected_paths:
        if destination == protected.resolve():
            raise NamingError("Report output cannot overwrite a policy or request input.")


def _add_policy_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY, help="Local customer policy JSON.")


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="namingctl.py",
        description="Offline-first Terraform naming planner; no network or third-party packages.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    commands = parser.add_subparsers(dest="command", required=True)

    for name in ("plan", "check", "apply"):
        command = commands.add_parser(name, help=f"{name.title()} policy-driven resource names.")
        command.add_argument("directory", type=Path, help="Terraform root directory.")
        _add_policy_arg(command)
        if name != "apply":
            command.add_argument("--requests", required=True, type=Path, help="Explicit JSON address-to-components manifest.")
            command.add_argument("--json", type=Path, help="Write machine-readable report.")
            command.add_argument("--report", type=Path, help="Markdown changelog path.")
        else:
            command.add_argument("--requests", required=True, type=Path, help="Explicit JSON address-to-components manifest.")
            command.add_argument("--include-advisory", action="store_true", help="Allow non-approved rules; use only after customer approval.")
            command.add_argument("--out", type=Path, help="Write changed copy here and leave source untouched.")
            command.add_argument("--no-backup", action="store_true", help="Do not save originals (not recommended).")

    listing = commands.add_parser("list", help="List policy rules and statuses.")
    _add_policy_arg(listing)

    explain = commands.add_parser("explain", help="Show one rule and its ordered components.")
    explain.add_argument("rule")
    _add_policy_arg(explain)

    generate = commands.add_parser("generate", help="Generate one name from explicit JSON values.")
    generate.add_argument("rule")
    generate.add_argument("--values", required=True, help='JSON object, e.g. \'{"workload":"payments"}\'.')
    _add_policy_arg(generate)
    return parser


def run(args: argparse.Namespace) -> int:
    policy = load_policy(args.policy)
    if args.command == "list":
        for name, rule in policy["rules"].items():
            print(f"{name:28} {rule['status']:10} {' '.join(_resource_types(rule))}")
        return 0
    if args.command == "explain":
        rule = policy["rules"].get(args.rule)
        if rule is None:
            raise NamingError(f"No rule named '{args.rule}'.")
        print(json.dumps({"name": args.rule, **rule}, indent=2, ensure_ascii=False))
        return 0
    if args.command == "generate":
        values = json.loads(args.values)
        if not isinstance(values, dict):
            raise NamingError("--values must decode to a JSON object.")
        name, _ = generate_name(policy, args.rule, values)
        print(name)
        return 0

    root = args.directory.resolve()
    if not root.is_dir():
        raise NamingError("Terraform directory does not exist; check the supplied local path.")
    request_data = load_json(args.requests)
    if not isinstance(request_data, dict):
        raise NamingError("Request manifest must be a JSON object keyed by Terraform resource address.")
    protected_paths = (args.policy, args.requests)
    plan = build_plan(root, policy, request_data, getattr(args, "include_advisory", False))

    if args.command == "apply":
        blockers = [item for item in plan["entries"] if item["status"] == "blocked"]
        if blockers:
            if args.out:
                report_root = validate_output_directory(root, args.out)
                report_root.mkdir(parents=True, exist_ok=True)
                write_plan(plan, report_root / REPORT_NAME, None, root, protected_paths)
            print(render_report(plan))
            return 1
        result_root = apply_plan(root, plan, args.out, args.no_backup, protected_paths)
        print(f"Applied {plan['summary']['planned']} name change(s).")
        print(f"Changelog written as {REPORT_NAME} in the target directory.")
        return 0

    report_path = args.report or (root / REPORT_NAME)
    write_plan(plan, report_path, args.json, root, protected_paths)
    print(render_report(plan))
    if plan["summary"]["blocked"]:
        return 1
    if plan["summary"]["planned"] and args.command == "check":
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = create_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except NamingError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    except OSError as error:
        detail = error.strerror or "filesystem operation failed"
        print(f"error: {detail}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as error:
        print(f"error: invalid JSON at line {error.lineno}, column {error.colno}", file=sys.stderr)
        return 2
    except ValueError:
        print("error: invalid input value", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
