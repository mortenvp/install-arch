#!/usr/bin/env python3
"""Render a GNOME monitors.xml for the currently connected DRM outputs.

GNOME monitor configurations include both stable EDID identity fields and the
DRM connector name. Some NVIDIA setups can enumerate the same physical
monitors on different DP-* connectors across boots. This script keeps the
layout/orientation from an existing monitors.xml, but rewrites connector names
from the EDID identity currently visible in /sys/class/drm.
"""

from __future__ import annotations

import argparse
import copy
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


Identity = tuple[str, str, str]


@dataclass(frozen=True)
class ConnectedMonitor:
    connector: str
    identity: Identity


def decode_manufacturer(edid: bytes) -> str:
    if len(edid) < 10:
        raise ValueError("EDID is too short to contain a manufacturer ID")

    raw = (edid[8] << 8) | edid[9]
    chars = [
        chr(((raw >> 10) & 0x1F) + 64),
        chr(((raw >> 5) & 0x1F) + 64),
        chr((raw & 0x1F) + 64),
    ]
    if any(ch < "A" or ch > "Z" for ch in chars):
        raise ValueError("EDID contains an invalid manufacturer ID")
    return "".join(chars)


def descriptor_text(edid: bytes, tag: int) -> str | None:
    for offset in range(54, 126, 18):
        descriptor = edid[offset : offset + 18]
        if len(descriptor) < 18:
            continue
        if descriptor[:3] != b"\x00\x00\x00" or descriptor[3] != tag:
            continue

        raw = descriptor[5:18].split(b"\n", 1)[0].split(b"\r", 1)[0]
        text = raw.decode("ascii", errors="ignore").strip()
        return re.sub(r"\s+", " ", text) if text else None
    return None


def fallback_product(edid: bytes) -> str:
    product_code = int.from_bytes(edid[10:12], byteorder="little", signed=False)
    return f"0x{product_code:04x}"


def fallback_serial(edid: bytes) -> str:
    serial = int.from_bytes(edid[12:16], byteorder="little", signed=False)
    return f"0x{serial:08x}"


def decode_edid_identity(edid: bytes) -> Identity:
    vendor = decode_manufacturer(edid)
    product = descriptor_text(edid, 0xFC) or fallback_product(edid)
    serial = descriptor_text(edid, 0xFF) or fallback_serial(edid)
    return (vendor, product, serial)


def mutter_connector_name(sysfs_name: str) -> str:
    name = re.sub(r"^card\d+-", "", sysfs_name)

    # The kernel exposes HDMI as HDMI-A-N in sysfs, while Mutter/GNOME usually
    # stores it as HDMI-N in monitors.xml.
    name = re.sub(r"^HDMI-A-", "HDMI-", name)
    return name


def connected_monitors(drm_dir: Path) -> list[ConnectedMonitor]:
    monitors: list[ConnectedMonitor] = []
    for status_file in sorted(drm_dir.glob("card*-*/status")):
        try:
            if status_file.read_text(encoding="ascii").strip() != "connected":
                continue
        except OSError:
            continue

        connector_dir = status_file.parent
        edid_file = connector_dir / "edid"
        try:
            edid = edid_file.read_bytes()
        except OSError:
            continue

        if not edid:
            continue

        try:
            identity = decode_edid_identity(edid)
        except ValueError as exc:
            print(
                f"Skipping {connector_dir.name}: could not decode EDID: {exc}",
                file=sys.stderr,
            )
            continue

        monitors.append(
            ConnectedMonitor(
                connector=mutter_connector_name(connector_dir.name),
                identity=identity,
            )
        )

    return monitors


def spec_identity(spec: ET.Element) -> Identity | None:
    vendor = spec.findtext("vendor")
    product = spec.findtext("product")
    serial = spec.findtext("serial")
    if vendor is None or product is None or serial is None:
        return None
    return (vendor, product, serial)


def logical_identities(configuration: ET.Element) -> list[Identity]:
    identities: list[Identity] = []
    for spec in configuration.findall("./logicalmonitor/monitor/monitorspec"):
        identity = spec_identity(spec)
        if identity is not None:
            identities.append(identity)
    return identities


def disabled_identities(configuration: ET.Element) -> list[Identity]:
    identities: list[Identity] = []
    for spec in configuration.findall("./disabled/monitorspec"):
        identity = spec_identity(spec)
        if identity is not None:
            identities.append(identity)
    return identities


def matching_identities(
    configuration: ET.Element, current_identities: set[Identity]
) -> list[Identity]:
    identities = logical_identities(configuration)
    identities.extend(
        identity
        for identity in disabled_identities(configuration)
        if identity in current_identities
    )
    return identities


def rewrite_configuration(
    configuration: ET.Element, connector_by_identity: dict[Identity, str]
) -> ET.Element:
    rewritten = copy.deepcopy(configuration)

    for spec in rewritten.findall("./logicalmonitor/monitor/monitorspec"):
        identity = spec_identity(spec)
        connector = spec.find("connector")
        if identity is None or connector is None:
            continue
        current_connector = connector_by_identity.get(identity)
        if current_connector:
            connector.text = current_connector

    logical = set(logical_identities(rewritten))
    for disabled in list(rewritten.findall("disabled")):
        spec = disabled.find("monitorspec")
        identity = spec_identity(spec) if spec is not None else None
        connector = spec.find("connector") if spec is not None else None

        # Disabled entries for currently connected monitors are intentional
        # state, for example a laptop panel that should stay off. Stale disabled
        # entries are removed because their connector names may now belong to a
        # different active monitor after NVIDIA connector enumeration changes.
        if (
            identity is not None
            and identity not in logical
            and identity in connector_by_identity
            and connector is not None
        ):
            connector.text = connector_by_identity[identity]
        else:
            rewritten.remove(disabled)

    return rewritten


def canonical_xml(element: ET.Element) -> bytes:
    clone = copy.deepcopy(element)
    ET.indent(clone, space="  ")
    return ET.tostring(clone, encoding="utf-8")


def render(source: Path, drm_dir: Path) -> ET.Element:
    tree = ET.parse(source)
    source_root = tree.getroot()
    if source_root.tag != "monitors":
        raise ValueError(f"{source} does not look like a GNOME monitors.xml file")

    current = connected_monitors(drm_dir)
    if not current:
        raise ValueError(f"no connected monitors with readable EDID found in {drm_dir}")

    current_counts = Counter(monitor.identity for monitor in current)
    current_identities = set(current_counts)
    duplicate_current = {
        identity for identity, count in current_counts.items() if count > 1
    }
    if duplicate_current:
        duplicates = ", ".join("/".join(identity) for identity in duplicate_current)
        raise ValueError(
            "cannot safely remap monitors with duplicate EDID identities: "
            f"{duplicates}"
        )

    connector_by_identity = {
        monitor.identity: monitor.connector for monitor in current
    }

    configurations = list(source_root.findall("configuration"))
    matching: list[tuple[int, ET.Element]] = []
    unmatched: list[ET.Element] = []

    for index, configuration in enumerate(configurations):
        identities = matching_identities(configuration, current_identities)
        if Counter(identities) == current_counts:
            rewritten = rewrite_configuration(configuration, connector_by_identity)
            rank = -index
            matching.append((rank, rewritten))
        else:
            unmatched.append(copy.deepcopy(configuration))

    if not matching:
        raise ValueError(
            "no source configuration matches the currently connected monitor EDIDs"
        )

    output = ET.Element(source_root.tag, source_root.attrib)
    seen: set[bytes] = set()
    for _, configuration in sorted(matching, key=lambda item: item[0]):
        key = canonical_xml(configuration)
        if key in seen:
            continue
        seen.add(key)
        output.append(configuration)

    for configuration in unmatched:
        key = canonical_xml(configuration)
        if key in seen:
            continue
        seen.add(key)
        output.append(configuration)

    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Rewrite GNOME monitors.xml connector names using currently "
            "connected DRM monitor EDIDs."
        )
    )
    parser.add_argument("source", type=Path, help="source monitors.xml")
    parser.add_argument(
        "--drm-dir",
        type=Path,
        default=Path("/sys/class/drm"),
        help="DRM sysfs directory to inspect",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        output = render(args.source, args.drm_dir)
    except (ET.ParseError, OSError, ValueError) as exc:
        print(f"render-gdm-monitors: {exc}", file=sys.stderr)
        return 1

    ET.indent(output, space="  ")
    sys.stdout.write(ET.tostring(output, encoding="unicode"))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
