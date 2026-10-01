#!/usr/bin/env python3
"""Compile a naming-convention workbook (.xlsx) into an engine policy.json.

The Excel workbook is the human-maintained source of truth. This converter is
offline and uses only the Python standard library (zipfile + xml.etree); it
needs no openpyxl, pandas, network access, or Microsoft Office.

It reads the recognised sheets of a naming matrix and emits policy.json in the
schema consumed by the Terraform module and namingctl.py:

  * Region_Codes                  -> code_sets.region
  * Code_Reference                -> code_sets.environment / business_service / use
  * Comprehensive_Resource_Analysis (preferred) or Resource_List -> rules
  * MSFT_Constraint               -> per-rule min_length / max_length / uniqueness
  * Resource_List                 -> rule status enrichment

No customer values are embedded in this file. Point it at a local workbook; keep
the generated policy.json private to the customer environment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

VERSION = "1.0.0"

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

# --------------------------------------------------------------------------- #
# Minimal standard-library .xlsx reader
# --------------------------------------------------------------------------- #


class Workbook:
    """Read-only, standard-library .xlsx reader returning plain string cells."""

    def __init__(self, path: Path) -> None:
        self.zip = zipfile.ZipFile(path)
        self.shared = self._read_shared_strings()
        self.sheets = self._read_sheet_index()

    def _read_shared_strings(self) -> list[str]:
        name = "xl/sharedStrings.xml"
        if name not in self.zip.namelist():
            return []
        root = ET.fromstring(self.zip.read(name))
        out = []
        for si in root.findall(f"{NS}si"):
            out.append("".join(t.text or "" for t in si.iter(f"{NS}t")))
        return out

    def _read_sheet_index(self) -> dict[str, str]:
        wb = ET.fromstring(self.zip.read("xl/workbook.xml"))
        rels = ET.fromstring(self.zip.read("xl/_rels/workbook.xml.rels"))
        rid_target = {rel.get("Id"): rel.get("Target") for rel in rels}
        sheets: dict[str, str] = {}
        for s in wb.find(f"{NS}sheets"):
            target = rid_target[s.get(f"{REL}id")]
            part = "xl/" + target.lstrip("/")
            sheets[s.get("name")] = part
        return sheets

    @staticmethod
    def _col_index(cell_ref: str) -> int:
        letters = re.match(r"[A-Z]+", cell_ref).group(0)
        n = 0
        for c in letters:
            n = n * 26 + (ord(c) - 64)
        return n - 1

    def _cell_value(self, c: ET.Element) -> str:
        t = c.get("t")
        v = c.find(f"{NS}v")
        if t == "s" and v is not None:
            return self.shared[int(v.text)]
        if t == "inlineStr":
            isn = c.find(f"{NS}is")
            return "".join(x.text or "" for x in isn.iter(f"{NS}t")) if isn is not None else ""
        return v.text if v is not None else ""

    def rows(self, sheet_name: str) -> list[list[str]]:
        """Return each row as a list of trimmed strings (ragged, 0-indexed)."""
        if sheet_name not in self.sheets:
            return []
        ws = ET.fromstring(self.zip.read(self.sheets[sheet_name]))
        out: list[list[str]] = []
        for row in ws.iter(f"{NS}row"):
            cells: dict[int, str] = {}
            max_col = -1
            for c in row.findall(f"{NS}c"):
                idx = self._col_index(c.get("r"))
                cells[idx] = (self._cell_value(c) or "").strip()
                max_col = max(max_col, idx)
            out.append([cells.get(i, "") for i in range(max_col + 1)])
        return out


# --------------------------------------------------------------------------- #
# Naming knowledge (generic, customer-neutral)
# --------------------------------------------------------------------------- #

# Component token -> (policy component key, code_set name or None).
TOKEN_MAP: dict[str, tuple[str, str | None]] = {
    "resourcename": ("resource", None),
    "resource": ("resource", None),
    "resourcetype": ("resource_prefix", None),
    "resourceprefix": ("resource_prefix", None),
    "businessservice": ("business_service", "business_service"),
    "tenant": ("business_service", "business_service"),
    "clientidentifier": ("client_identifier", None),
    "buxxxx": ("client_identifier", None),
    "workload": ("workload", None),
    "purpose": ("purpose", None),
    "purposecode": ("purpose", None),
    "use": ("use", "use"),
    "usecode": ("use", "use"),
    "region": ("region", "region"),
    "regioncode": ("region", "region"),
    "environment": ("environment", "environment"),
    "env": ("environment", "environment"),
    "index": ("index", None),
    "number": ("index", None),
    "instance": ("index", None),
    "suffix": ("suffix", None),
}

# Resource name (slugged) -> azurerm Terraform resource type.
TERRAFORM_TYPES: dict[str, list[str]] = {
    "resource_group": ["azurerm_resource_group"],
    "storage_account": ["azurerm_storage_account"],
    "key_vault": ["azurerm_key_vault"],
    "virtual_network": ["azurerm_virtual_network"],
    "virtual_network_vnet": ["azurerm_virtual_network"],
    "platform_vnet": ["azurerm_virtual_network"],
    "subnet": ["azurerm_subnet"],
    "subnets": ["azurerm_subnet"],
    "network_security_group": ["azurerm_network_security_group"],
    "network_security_group_nsg": ["azurerm_network_security_group"],
    "nsg": ["azurerm_network_security_group"],
    "route_table": ["azurerm_route_table"],
    "public_ip": ["azurerm_public_ip"],
    "public_ips": ["azurerm_public_ip"],
    "firewall": ["azurerm_firewall"],
    "azure_firewall": ["azurerm_firewall"],
    "firewall_policy": ["azurerm_firewall_policy"],
    "azure_firewall_policy": ["azurerm_firewall_policy"],
    "log_analytics_workspace": ["azurerm_log_analytics_workspace"],
    "event_hub": ["azurerm_eventhub"],
    "private_endpoint": ["azurerm_private_endpoint"],
    "private_endpoints": ["azurerm_private_endpoint"],
    "private_dns_zone": ["azurerm_private_dns_zone"],
    "disk": ["azurerm_managed_disk"],
    "managed_disk": ["azurerm_managed_disk"],
    "load_balancer": ["azurerm_lb"],
    "managed_identity": ["azurerm_user_assigned_identity"],
    "network_watcher": ["azurerm_network_watcher"],
    "kubernetes_service_aks": ["azurerm_kubernetes_cluster"],
    "aks": ["azurerm_kubernetes_cluster"],
    "bastion": ["azurerm_bastion_host"],
    "virtual_wan": ["azurerm_virtual_wan"],
    "azure_virtual_wan": ["azurerm_virtual_wan"],
    "virtual_wan_hub": ["azurerm_virtual_hub"],
    "expressroute_gateway": ["azurerm_express_route_gateway"],
    "expressroute_circuit": ["azurerm_express_route_circuit"],
}

APPROVED_STATUS_HINTS = ("done", "no conflict", "agreed", "approved", "final")
DRAFT_STATUS_HINTS = (
    "in-progress", "in progress", "not clear", "to be discussed", "to be agreed",
    "to be analysed", "to be analyzed", "proposed", "tbd", "draft", "wip",
)


def slug(text: str) -> str:
    text = re.sub(r"\([^)]*\)", " ", text)  # drop parenthetical notes
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def normalise_token(token: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", token.lower())


def status_from_text(text: str) -> str | None:
    low = text.lower()
    for hint in APPROVED_STATUS_HINTS:
        if hint in low:
            return "approved"
    for hint in DRAFT_STATUS_HINTS:
        if hint in low:
            return "draft"
    return None


# --------------------------------------------------------------------------- #
# Code-set extraction
# --------------------------------------------------------------------------- #


def find_header(rows: list[list[str]], *needles: str) -> int:
    low_needles = [n.lower() for n in needles]
    for i, row in enumerate(rows):
        joined = " | ".join(cell.lower() for cell in row)
        if all(n in joined for n in low_needles):
            return i
    return -1


def col_of(header: list[str], *needles: str) -> int:
    for i, cell in enumerate(header):
        low = cell.lower()
        if any(n in low for n in needles):
            return i
    return -1


def section_end(rows: list[list[str]], start: int) -> int:
    """Return the index of the next numbered section title (e.g. '2. ...'), else len."""
    for i in range(start, len(rows)):
        first = next((c for c in rows[i] if c.strip()), "")
        if re.match(r"^\d+\.\s", first.strip()):
            return i
    return len(rows)


def extract_region_codes(wb: Workbook, warnings: list[str]) -> dict[str, str]:
    rows = wb.rows("Region_Codes")
    if not rows:
        return {}
    h = find_header(rows, "region name", "region code")
    if h < 0:
        warnings.append("Region_Codes: header row not found; region code set is empty.")
        return {}
    header = rows[h]
    name_c = col_of(header, "region name")
    code_c = col_of(header, "region code")
    alt_c = col_of(header, "possible code", "us region")
    mapping: dict[str, str] = {}
    for row in rows[h + 1:]:
        name = row[name_c] if name_c < len(row) else ""
        code = row[code_c] if 0 <= code_c < len(row) else ""
        if not name or not code:
            continue
        code_l = code.strip().lower()
        mapping[name.strip().lower()] = code_l
        mapping[code_l] = code_l
        if 0 <= alt_c < len(row) and row[alt_c].strip():
            mapping[row[alt_c].strip().lower()] = code_l
    return mapping


def extract_code_reference(wb: Workbook, warnings: list[str]) -> dict[str, dict[str, str]]:
    rows = wb.rows("Code_Reference")
    sets: dict[str, dict[str, str]] = {"environment": {}, "business_service": {}, "use": {}}
    if not rows:
        return sets

    # Environment: Lifecycle Environment -> Resource Environment Code
    h = find_header(rows, "lifecycle environment", "environment code")
    if h >= 0:
        header = rows[h]
        life_c = col_of(header, "lifecycle environment")
        code_c = col_of(header, "resource environment code", "environment code")
        for row in rows[h + 1:]:
            if find_header([row], "resource naming patterns") == 0:
                break
            name = row[life_c] if 0 <= life_c < len(row) else ""
            code = row[code_c] if 0 <= code_c < len(row) else ""
            if name and code:
                sets["environment"][name.strip().lower()] = code.strip().lower()
                sets["environment"][code.strip().lower()] = code.strip().lower()
    else:
        warnings.append("Code_Reference: environment mapping header not found.")

    # Business service / subscription type codes: Type Code -> code
    h = find_header(rows, "type code", "formal name")
    if h >= 0:
        header = rows[h]
        code_c = col_of(header, "type code")
        name_c = col_of(header, "formal name")
        for row in rows[h + 1: section_end(rows, h + 1)]:
            code = row[code_c] if 0 <= code_c < len(row) else ""
            name = row[name_c] if 0 <= name_c < len(row) else ""
            if code and code.strip().isalnum() and len(code.strip()) <= 8:
                sets["business_service"][code.strip().lower()] = code.strip().lower()
                if name:
                    sets["business_service"][name.strip().lower()] = code.strip().lower()

    # Service use codes: Use Code -> code
    h = find_header(rows, "use code", "service domain")
    if h >= 0:
        header = rows[h]
        code_c = col_of(header, "use code")
        dom_c = col_of(header, "service domain")
        for row in rows[h + 1: section_end(rows, h + 1)]:
            code = row[code_c] if 0 <= code_c < len(row) else ""
            if code and code.strip().isalnum() and len(code.strip()) <= 8:
                sets["use"][code.strip().lower()] = code.strip().lower()
                dom = row[dom_c] if 0 <= dom_c < len(row) else ""
                if dom:
                    sets["use"][dom.strip().lower()] = code.strip().lower()

    return {k: v for k, v in sets.items() if v}


# --------------------------------------------------------------------------- #
# Constraint extraction
# --------------------------------------------------------------------------- #


def extract_constraints(wb: Workbook) -> list[tuple[str, dict]]:
    rows = wb.rows("MSFT_Constraint")
    out: list[tuple[str, dict]] = []
    h = find_header(rows, "resource type", "constraint")
    if h < 0:
        return out
    header = rows[h]
    type_c = col_of(header, "resource type")
    con_c = col_of(header, "constraint", "microsoft constraint")
    for row in rows[h + 1:]:
        name = row[type_c] if 0 <= type_c < len(row) else ""
        text = row[con_c] if 0 <= con_c < len(row) else ""
        if not name:
            continue
        info: dict = {}
        m = re.search(r"(\d+)\s*[-\u2013]\s*(\d+)\s*char", text, re.I)
        if m:
            info["min_length"] = int(m.group(1))
            info["max_length"] = int(m.group(2))
        else:
            m = re.search(r"up to\s*(\d+)\s*char", text, re.I)
            if m:
                info["max_length"] = int(m.group(1))
            else:
                m = re.search(r"(\d+)\s*char", text, re.I)
                if m:
                    info["max_length"] = int(m.group(1))
        if "globally unique" in text.lower():
            info["uniqueness_scope"] = "global"
        if info:
            out.append((slug(name), info))
    return out


def match_constraint(rule_slug: str, name_text: str, constraints: list[tuple[str, dict]]) -> dict:
    ns = normalise_token(name_text)
    for cslug, info in constraints:
        cns = normalise_token(cslug)
        if cns and (cns in ns or ns in cns or cslug in rule_slug or rule_slug in cslug):
            return info
    return {}


# --------------------------------------------------------------------------- #
# Pattern parsing
# --------------------------------------------------------------------------- #


def parse_pattern(pattern: str) -> tuple[list[dict], str, list[str]]:
    """Parse a '<a>-<b>' style pattern into components, separator, notes."""
    notes: list[str] = []
    text = pattern.strip()
    # Strip a leading label such as "Key Vault:".
    if ":" in text and "<" in text and text.index(":") < text.index("<"):
        text = text.split(":", 1)[1].strip()
    # Keep only the first line / first example.
    text = text.splitlines()[0].strip().rstrip(";").strip()
    if "<" not in text:
        return [], "-", ["no <token> placeholders found"]

    literal_prefix = text[: text.index("<")]
    sep_match = re.search(r"[^<>\w]", literal_prefix[::-1])
    separator_candidates: list[str] = []
    prefix = literal_prefix
    if prefix and not prefix[-1].isalnum():
        # trailing separator between literal and first token
        separator_candidates.append(prefix[-1])
        prefix = prefix[:-1]
    prefix = prefix.strip()

    tokens = re.findall(r"<([^>]+)>", text)
    between = re.findall(r">([^<]*)<", text)
    for b in between:
        separator_candidates.append(b.strip())

    non_empty_seps = [s for s in separator_candidates if s != ""]
    if non_empty_seps and "" in separator_candidates:
        notes.append("mixed separators in pattern; review ordering")
    separator = non_empty_seps[0] if non_empty_seps else ""
    if len(set(non_empty_seps)) > 1:
        notes.append("inconsistent separators: " + ",".join(sorted(set(non_empty_seps))))

    components: list[dict] = []
    if prefix:
        components.append({"key": "resource", "literal": prefix.lower()})
    for tok in tokens:
        norm = normalise_token(tok)
        key, code_set = TOKEN_MAP.get(norm, (slug(tok) or "part", None))
        if key == "resource" and components and components[0].get("literal"):
            # '<resource_name>' token after a concrete literal: skip duplicate.
            continue
        comp: dict = {"key": key}
        if code_set:
            comp["code_set"] = code_set
        components.append(comp)
    return components, separator, notes


def synthesise_regex(components: list[dict], separator: str) -> str:
    literal = ""
    if components and components[0].get("literal"):
        literal = re.escape(components[0]["literal"])
    if separator == "-":
        return f"^{literal}(?:-[a-z0-9]+)+$" if literal else "^[a-z0-9]+(?:-[a-z0-9]+)*$"
    return f"^{literal}[a-z0-9]+$" if literal else "^[a-z0-9]+$"


# --------------------------------------------------------------------------- #
# Rule extraction
# --------------------------------------------------------------------------- #


def extract_rules(wb: Workbook, constraints, warnings) -> tuple[dict, list[dict]]:
    report_rows: list[dict] = []
    rules: dict[str, dict] = {}

    # Status hints from Resource_List (Resource Name -> Current Status).
    status_by_name: dict[str, str] = {}
    rl = wb.rows("Resource_List")
    h = find_header(rl, "resource name", "naming pattern")
    if h >= 0:
        header = rl[h]
        name_c = col_of(header, "resource name")
        stat_c = col_of(header, "current status", "status")
        for row in rl[h + 1:]:
            name = row[name_c] if 0 <= name_c < len(row) else ""
            stat = row[stat_c] if 0 <= stat_c < len(row) else ""
            if name and stat:
                status_by_name[normalise_token(name)] = stat

    rows = wb.rows("Comprehensive_Resource_Analysis")
    source_sheet = "Comprehensive_Resource_Analysis"
    h = find_header(rows, "resource name", "naming pattern")
    if h < 0:
        rows = rl
        source_sheet = "Resource_List"
        h = find_header(rows, "resource name", "naming pattern")
    if h < 0:
        warnings.append("No resource sheet with 'Resource Name' + 'Naming Pattern' headers found.")
        return rules, report_rows

    header = rows[h]
    name_c = col_of(header, "resource name")
    pat_c = col_of(header, "naming pattern")
    status_c = col_of(header, "current status", "proposal status", "status")

    seen_names: set[str] = set()
    for row in rows[h + 1:]:
        name = row[name_c] if 0 <= name_c < len(row) else ""
        pattern = row[pat_c] if 0 <= pat_c < len(row) else ""
        if not name or "<" not in pattern:
            continue
        rule_key = slug(name)
        if not rule_key or rule_key in seen_names:
            continue
        seen_names.add(rule_key)

        components, separator, notes = parse_pattern(pattern)
        info = match_constraint(rule_key, name, constraints)

        raw_status = ""
        if 0 <= status_c < len(row):
            raw_status = row[status_c]
        status = status_from_text(raw_status) if raw_status else None
        if status is None:
            status = status_by_name.get(normalise_token(name), "")
            status = status_from_text(status) if status else None
        if status is None:
            status = "draft"  # safe, advisory default
        if not components:
            status = "missing"
            notes.append("pattern could not be parsed")

        rule = {
            "status": status,
            "separator": separator,
            "pattern": info.get("pattern", synthesise_regex(components, separator)),
            "uniqueness_scope": info.get("uniqueness_scope", "unknown"),
            "terraform_resource_types": TERRAFORM_TYPES.get(rule_key, []),
            "components": components,
        }
        if "min_length" in info:
            rule["min_length"] = info["min_length"]
        if "max_length" in info:
            rule["max_length"] = info["max_length"]
        rules[rule_key] = rule

        report_rows.append({
            "rule": rule_key,
            "resource": name,
            "source_pattern": pattern.splitlines()[0].strip(),
            "status": status,
            "terraform_mapped": bool(rule["terraform_resource_types"]),
            "notes": notes,
        })

    if source_sheet == "Resource_List":
        warnings.append("Fell back to Resource_List; Comprehensive_Resource_Analysis not usable.")
    return rules, report_rows


# --------------------------------------------------------------------------- #
# Policy assembly
# --------------------------------------------------------------------------- #


def build_policy(wb: Workbook, source: Path) -> tuple[dict, list[dict], list[str]]:
    warnings: list[str] = []
    code_sets: dict[str, dict[str, str]] = {}
    region = extract_region_codes(wb, warnings)
    if region:
        code_sets["region"] = region
    code_sets.update(extract_code_reference(wb, warnings))

    constraints = extract_constraints(wb)
    rules, report_rows = extract_rules(wb, constraints, warnings)

    # Drop code_set references that have no matching code set.
    available = set(code_sets.keys())
    for rule in rules.values():
        for comp in rule["components"]:
            if comp.get("code_set") and comp["code_set"] not in available:
                comp.pop("code_set", None)

    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    policy = {
        "metadata": {
            "source_workbook": source.name,
            "source_sha256": digest,
            "generated_by": f"xlsx2policy.py {VERSION}",
            "notice": "Generated from the naming workbook. Edit the workbook, then re-run the converter. Do not hand-edit.",
        },
        "normal_case": "lower",
        "code_sets": code_sets,
        "rules": rules,
    }
    return policy, report_rows, warnings


def render_report(policy: dict, report_rows: list[dict], warnings: list[str]) -> str:
    lines = ["# Naming Workbook Conversion Report", ""]
    lines.append(f"- Source workbook: `{policy['metadata']['source_workbook']}`")
    lines.append(f"- Source SHA-256: `{policy['metadata']['source_sha256']}`")
    lines.append(f"- Code sets: {', '.join(sorted(policy['code_sets'])) or 'none'}")
    lines.append(f"- Rules generated: {len(policy['rules'])}")
    approved = sum(1 for r in policy["rules"].values() if r["status"] == "approved")
    lines.append(f"- Approved (enforced) rules: {approved}")
    lines.append("")
    if warnings:
        lines.append("## Warnings")
        lines.extend(f"- {w}" for w in warnings)
        lines.append("")
    lines.append("## Rules")
    lines.append("")
    lines.append("| Rule | Resource | Status | TF mapped | Source pattern | Notes |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for r in sorted(report_rows, key=lambda x: x["rule"]):
        notes = "; ".join(r["notes"]) if r["notes"] else ""
        tf = "yes" if r["terraform_mapped"] else "no"
        lines.append(
            f"| `{r['rule']}` | {r['resource']} | {r['status']} | {tf} | `{r['source_pattern']}` | {notes} |"
        )
    lines.append("")
    lines.append(
        "Only `approved` rules are enforced by the engine. Review `draft`, "
        "`conflict`, and `missing` rows with the customer before promoting them."
    )
    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="xlsx2policy",
        description="Compile a naming-convention workbook into policy.json (offline, stdlib only).",
    )
    parser.add_argument("workbook", type=Path, help="Path to the naming .xlsx workbook.")
    parser.add_argument("--out", type=Path, default=Path("policy.json"), help="Output policy JSON path.")
    parser.add_argument("--report", type=Path, help="Optional Markdown conversion report path.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if --out is missing or its embedded source hash is stale.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    args = parser.parse_args(argv)

    if not args.workbook.is_file():
        print(f"error: workbook not found: {args.workbook}", file=sys.stderr)
        return 2

    try:
        wb = Workbook(args.workbook)
    except (zipfile.BadZipFile, KeyError, ET.ParseError) as exc:
        print(f"error: cannot read workbook ({exc}).", file=sys.stderr)
        return 2

    policy, report_rows, warnings = build_policy(wb, args.workbook)

    if args.check:
        if not args.out.is_file():
            print(f"stale: {args.out} does not exist; run the converter.", file=sys.stderr)
            return 1
        try:
            existing = json.loads(args.out.read_text(encoding="utf-8"))
            old = existing.get("metadata", {}).get("source_sha256")
        except (json.JSONDecodeError, OSError):
            old = None
        new = policy["metadata"]["source_sha256"]
        if old != new:
            print(f"stale: {args.out} does not match current workbook; re-run the converter.", file=sys.stderr)
            return 1
        print(f"up to date: {args.out} matches {args.workbook.name}.")
        return 0

    args.out.write_text(json.dumps(policy, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.out} ({len(policy['rules'])} rules, {len(policy['code_sets'])} code sets).")
    if warnings:
        print(f"{len(warnings)} warning(s); see the report.", file=sys.stderr)
    if args.report:
        args.report.write_text(render_report(policy, report_rows, warnings), encoding="utf-8")
        print(f"Wrote {args.report}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
