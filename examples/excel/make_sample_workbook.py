#!/usr/bin/env python3
"""Generate a synthetic, customer-neutral naming workbook for demos and tests.

Writes a minimal but valid .xlsx using only the Python standard library, with the
same sheet layout xlsx2policy.py expects. All values are invented (Contoso-style)
and contain no customer data.

Usage:
    python make_sample_workbook.py [output.xlsx]
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

# Each sheet is a list of rows; each row is a list of string cells.
SHEETS: dict[str, list[list[str]]] = {
    "Region_Codes": [
        ["S/N", "Region Name", "Region Code", "Possible Code for US Region"],
        ["1", "East US", "eus", "use"],
        ["2", "West Europe", "weu", ""],
        ["3", "Southeast Asia", "sea", ""],
        ["4", "UK South", "uks", ""],
    ],
    "Code_Reference": [
        ["1. Subscription Type Codes", "", "", ""],
        ["Type Code", "Formal Name", "Definition", "Naming Usage"],
        ["plt", "Platform", "Shared platform subscription", "Platform resources"],
        ["app", "Application", "Application workload subscription", "App resources"],
        ["", "", "", ""],
        ["2. Service Use Codes", "", "", ""],
        ["Use Code", "Service Domain", "Definition", "Typical Resources"],
        ["mgmt", "Management", "Platform management tooling", "Log Analytics"],
        ["net", "Networking", "Connectivity services", "Firewall, VNet"],
        ["", "", "", ""],
        ["3. Environment Code Mapping", "", "", ""],
        ["Lifecycle Environment", "Resource Environment Code", "Subscription Environment", "DR"],
        ["Development", "dev", "Dev", "No"],
        ["Test", "tst", "Test", "No"],
        ["Production", "prd", "Prod", "No"],
        ["Non-Production", "nprd", "NonProd", "No"],
        ["", "", "", ""],
        ["4. Resource Naming Patterns", "", "", ""],
        ["Resource Scope", "Naming Pattern", "Example", "Remarks"],
        ["Standard resource", "<resource_name>-<business_service>-<region_code>-<environment>-<index>",
         "rg-plt-eus-prd-01", "Business_Service: plt, app"],
    ],
    "Comprehensive_Resource_Analysis": [
        ["Comprehensive Resource & Placement Analysis", "", "", "", ""],
        ["", "", "", "", ""],
        ["Category", "Resource Name", "Naming Pattern", "Example", "Current Status"],
        ["Platform", "Resource Group", "rg-<BusinessService>-<RegionCode>-<Environment>-<index>",
         "rg-plt-eus-prd-01", "Done (No Conflict)"],
        ["Platform", "Storage Account", "st<BusinessService><RegionCode><Environment><index>",
         "stplteusprd01", "Done (No Conflict)"],
        ["Platform", "Key Vault", "kv-<BusinessService>-<RegionCode>-<Environment>-<index>",
         "kv-plt-eus-prd-01", "Done (No Conflict)"],
        ["Network", "Virtual Network", "vnet-<BusinessService>-<RegionCode>-<Environment>-<index>",
         "vnet-plt-eus-prd-01", "In-Progress (Naming Not Clear)"],
        ["Network", "Azure Firewall", "afw-<BusinessService>-<RegionCode>-<Environment>-<index>",
         "afw-plt-eus-prd-01", "Done (No Conflict)"],
        ["Network", "Subnet", "snet-<Purpose>-<BusinessService>-<RegionCode>-<Environment>-<index>",
         "snet-app-plt-eus-prd-01", "In-Progress (Naming Not Clear)"],
    ],
    "Resource_List": [
        ["Category", "Resource Name", "Naming Pattern", "Current Status"],
        ["Platform", "Resource Group", "rg-<BusinessService>-<RegionCode>-<Environment>-<index>",
         "Done (No Conflict)"],
        ["Network", "Virtual Network", "vnet-<BusinessService>-<RegionCode>-<Environment>-<index>",
         "In-Progress (Naming Not Clear)"],
    ],
    "MSFT_Constraint": [
        ["Resource Type", "Microsoft Constraint", "Impact"],
        ["Storage Account", "3-24 characters, lowercase letters and numbers only, globally unique, no hyphens",
         "Full pattern will not fit"],
        ["Key Vault", "3-24 characters, alphanumeric and hyphens, globally unique", "Shorten pattern"],
        ["Resource Group", "Up to 90 characters", "Full pattern fits"],
        ["Virtual Network", "Up to 64 characters", "Full pattern fits"],
        ["Azure Firewall", "Up to 80 characters", "Full pattern fits"],
    ],
}

CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
    "{sheets}"
    '</Types>'
)

ROOT_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
    '</Relationships>'
)


def col_letter(idx: int) -> str:
    letters = ""
    idx += 1
    while idx:
        idx, rem = divmod(idx - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def sheet_xml(rows: list[list[str]]) -> str:
    parts = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
        "<sheetData>",
    ]
    for r, row in enumerate(rows, start=1):
        parts.append(f'<row r="{r}">')
        for c, value in enumerate(row):
            if value == "":
                continue
            ref = f"{col_letter(c)}{r}"
            text = escape(value)
            parts.append(
                f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{text}</t></is></c>'
            )
        parts.append("</row>")
    parts.append("</sheetData></worksheet>")
    return "".join(parts)


def workbook_xml(names: list[str]) -> str:
    sheet_tags = "".join(
        f'<sheet name="{escape(n)}" sheetId="{i}" r:id="rId{i}"/>'
        for i, n in enumerate(names, start=1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<sheets>{sheet_tags}</sheets></workbook>"
    )


def workbook_rels(count: int) -> str:
    rels = "".join(
        f'<Relationship Id="rId{i}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        f'Target="worksheets/sheet{i}.xml"/>'
        for i in range(1, count + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f"{rels}</Relationships>"
    )


def build(out_path: Path) -> None:
    names = list(SHEETS.keys())
    sheet_overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for i in range(1, len(names) + 1)
    )
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES.format(sheets=sheet_overrides))
        z.writestr("_rels/.rels", ROOT_RELS)
        z.writestr("xl/workbook.xml", workbook_xml(names))
        z.writestr("xl/_rels/workbook.xml.rels", workbook_rels(len(names)))
        for i, name in enumerate(names, start=1):
            z.writestr(f"xl/worksheets/sheet{i}.xml", sheet_xml(SHEETS[name]))


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("sample-naming.xlsx")
    build(target)
    print(f"Wrote {target}")
