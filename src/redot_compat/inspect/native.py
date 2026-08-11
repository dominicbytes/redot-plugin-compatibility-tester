from __future__ import annotations

import hashlib
import struct
from pathlib import Path

_PE_MACHINES = {0x014C: "x86_32", 0x8664: "x86_64", 0xAA64: "arm64"}
_ELF_MACHINES = {0x03: "x86_32", 0x3E: "x86_64", 0x28: "arm32", 0xB7: "arm64"}
_MACHO_CPUS = {7: "x86_32", 0x01000007: "x86_64", 12: "arm32", 0x0100000C: "arm64"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def binary_architecture(path: Path) -> str | None:
    with path.open("rb") as stream:
        header = stream.read(4096)
    if header.startswith(b"MZ") and len(header) >= 0x40:
        pe_offset = struct.unpack_from("<I", header, 0x3C)[0]
        if pe_offset + 6 <= len(header) and header[pe_offset : pe_offset + 4] == b"PE\0\0":
            machine = struct.unpack_from("<H", header, pe_offset + 4)[0]
            return _PE_MACHINES.get(machine, f"pe-machine-{machine:04x}")
    if header.startswith(b"\x7fELF") and len(header) >= 20:
        byte_order = "<" if header[5] == 1 else ">"
        machine = struct.unpack_from(f"{byte_order}H", header, 18)[0]
        return _ELF_MACHINES.get(machine, f"elf-machine-{machine:04x}")
    if len(header) >= 8:
        magic = header[:4]
        if magic in {b"\xfe\xed\xfa\xce", b"\xfe\xed\xfa\xcf"}:
            cpu = struct.unpack_from(">I", header, 4)[0]
            return _MACHO_CPUS.get(cpu, f"macho-cpu-{cpu:x}")
        if magic in {b"\xce\xfa\xed\xfe", b"\xcf\xfa\xed\xfe"}:
            cpu = struct.unpack_from("<I", header, 4)[0]
            return _MACHO_CPUS.get(cpu, f"macho-cpu-{cpu:x}")
    return None
