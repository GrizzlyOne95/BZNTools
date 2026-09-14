from __future__ import annotations

import argparse
import json
import sys
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class OdfEntry:
    key: str
    value: str
    line: int


@dataclass(frozen=True)
class OdfSection:
    name: str
    line: int
    entries: tuple[OdfEntry, ...]

    def has_exact(self, key: str) -> bool:
        return any(entry.key == key for entry in self.entries)

    def values_exact(self, key: str) -> tuple[OdfEntry, ...]:
        return tuple(entry for entry in self.entries if entry.key == key)


@dataclass(frozen=True)
class OdfDocument:
    path: str
    sections: tuple[OdfSection, ...]

    def sections_exact(self, name: str) -> tuple[OdfSection, ...]:
        return tuple(section for section in self.sections if section.name == name)


@dataclass(frozen=True)
class Diagnostic:
    rule_id: str
    severity: str
    path: str
    line: int
    message: str
    suggestion: str
    evidence: str
    evidence_kind: str


@dataclass(frozen=True)
class SectionAliasRule:
    rule_id: str
    wrong: str
    correct: str
    severity: str
    consequence: str
    evidence: str
    evidence_kind: str = "compatibility"


SECTION_ALIAS_RULES = (
    SectionAliasRule(
        "BZODF001",
        "FlareBuildingClass",
        "FlareMineClass",
        "error",
        "Redux does not run the FlareMineClass loader for this section. payloadName can therefore remain inherited/null; FlareMine::Update dereferences the payload OrdnanceClass and may crash immediately.",
        "BZ1_Source Redux decomp: FlareMineClass::Load 0x004D2B10; FlareMine::Update call at 0x004D3093; payload dereference begins at 0x00586FF0.",
        "code-derived",
    ),
    SectionAliasRule(
        "BZODF002",
        "MagnetClass",
        "MagnetMineClass",
        "warning",
        "Redux ignores MagnetMineClass-specific values placed under this section and the object runs inherited/default behavior.",
        "Redux stock ODF/class contract.",
    ),
    SectionAliasRule(
        "BZODF003",
        "ScavengerCraftClass",
        "ScavengerClass",
        "warning",
        "Redux does not read scavenger-specific values from this section.",
        "Redux stock ODF/class contract.",
    ),
    SectionAliasRule(
        "BZODF004",
        "flameClass",
        "FlamePuffClass",
        "warning",
        "Redux does not read FlamePuffClass-specific values from this section.",
        "Redux stock ODF/class contract.",
    ),
    SectionAliasRule(
        "BZODF005",
        "GameObject",
        "GameObjectClass",
        "error",
        "Redux does not treat this as the GameObjectClass section; inheritance/class metadata may be absent and the object can fail to load.",
        "Redux ODF loader / observed 'uses unknown class label \"\"' failure.",
    ),
)


def _strip_inline_comment(value: str) -> str:
    # ODFs commonly use // comments. Preserve // inside quoted strings.
    in_quote = False
    i = 0
    while i < len(value) - 1:
        if value[i] == '"':
            in_quote = not in_quote
        if not in_quote and value[i : i + 2] == "//":
            return value[:i].rstrip()
        i += 1
    return value.rstrip()


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    return value


def parse_odf(path: str, text: str) -> OdfDocument:
    sections: list[OdfSection] = []
    current_name: str | None = None
    current_line = 0
    current_entries: list[OdfEntry] = []

    def flush() -> None:
        nonlocal current_name, current_line, current_entries
        if current_name is not None:
            sections.append(
                OdfSection(current_name, current_line, tuple(current_entries))
            )
        current_name = None
        current_line = 0
        current_entries = []

    for line_number, raw_line in enumerate(text.splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("//") or line.startswith(";") or line.startswith("#"):
            continue

        if line.startswith("[") and "]" in line:
            end = line.find("]")
            flush()
            current_name = line[1:end].strip()
            current_line = line_number
            continue

        if current_name is None or "=" not in raw_line:
            continue

        key, value = raw_line.split("=", 1)
        key = key.strip()
        value = _strip_inline_comment(value.strip())
        if key:
            current_entries.append(OdfEntry(key, value, line_number))

    flush()
    return OdfDocument(path, tuple(sections))


def _decode_odf(data: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            pass
    return data.decode("latin-1")


def load_documents(source: Path) -> tuple[OdfDocument, ...]:
    documents: list[OdfDocument] = []

    if source.is_dir():
        for path in sorted(source.rglob("*")):
            if path.is_file() and path.suffix.lower() == ".odf":
                rel = path.relative_to(source).as_posix()
                documents.append(parse_odf(rel, _decode_odf(path.read_bytes())))
        return tuple(documents)

    if source.is_file() and source.suffix.lower() == ".zip":
        with zipfile.ZipFile(source) as archive:
            for info in sorted(archive.infolist(), key=lambda item: item.filename.lower()):
                if not info.is_dir() and info.filename.lower().endswith(".odf"):
                    documents.append(
                        parse_odf(info.filename, _decode_odf(archive.read(info)))
                    )
        return tuple(documents)

    if source.is_file() and source.suffix.lower() == ".odf":
        return (parse_odf(source.name, _decode_odf(source.read_bytes())),)

    raise ValueError(f"Unsupported input: {source}. Expected an ODF file, directory, or ZIP archive.")


def _diagnose_section_aliases(document: OdfDocument) -> Iterable[Diagnostic]:
    for section in document.sections:
        for rule in SECTION_ALIAS_RULES:
            if section.name != rule.wrong:
                continue

            detail = rule.consequence
            if rule.rule_id == "BZODF001" and section.has_exact("payloadName"):
                detail = (
                    "payloadName is present, but it is under [FlareBuildingClass], a section "
                    "the Redux FlareMineClass loader does not consume. " + detail
                )

            yield Diagnostic(
                rule.rule_id,
                rule.severity,
                document.path,
                section.line,
                f"[{section.name}] should be [{rule.correct}]. {detail}",
                f"Rename the section to [{rule.correct}].",
                rule.evidence,
                rule.evidence_kind,
            )


def _diagnose_keys(document: OdfDocument) -> Iterable[Diagnostic]:
    for section in document.sections:
        if section.name in {"MagnetClass", "MagnetMineClass"}:
            for entry in section.values_exact("triggetDelay"):
                yield Diagnostic(
                    "BZODF101",
                    "warning",
                    document.path,
                    entry.line,
                    "'triggetDelay' is not the Redux MagnetMineClass key; it is silently ignored.",
                    "Rename the key to 'triggerDelay'.",
                    "Redux stock MagnetMineClass ODF contract.",
                    "compatibility",
                )

        if section.name in {"GameObject", "GameObjectClass"}:
            for entry in section.values_exact("basename"):
                yield Diagnostic(
                    "BZODF102",
                    "error",
                    document.path,
                    entry.line,
                    "'basename' does not match the Redux GameObjectClass inheritance key spelling used by this loader path.",
                    "Rename the key to 'baseName'.",
                    "Redux GameObjectClass ODF loader contract / observed unknown-class-label failure.",
                    "compatibility",
                )

        if section.name in {"flameClass", "FlamePuffClass"}:
            legacy_entries = [
                entry
                for entry in section.entries
                if entry.key in {"flameLength", "variance", "shotColor"}
            ]
            for entry in legacy_entries:
                yield Diagnostic(
                    "BZODF103",
                    "warning",
                    document.path,
                    entry.line,
                    f"'{entry.key}' is not one of the FlamePuffClass fields used by Redux and is ignored here.",
                    "Author the effect with Redux FlamePuffClass fields such as flameRadius, flameDelay, flameTexture, and flameFrames.",
                    "Redux stock FlamePuffClass ODF contract.",
                    "compatibility",
                )

        for entry in section.values_exact("xplBuilding"):
            if _unquote(entry.value).lower() == "xmlasbld":
                yield Diagnostic(
                    "BZODF104",
                    "warning",
                    document.path,
                    entry.line,
                    'xplBuilding references "xmlasbld", a known bad asset name in this content.',
                    'Use xplBuilding = "xlasbld".',
                    "Known Redux content/reference correction confirmed during AbsoZero crash triage.",
                    "known-fix",
                )


def scan_documents(documents: Iterable[OdfDocument]) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    for document in documents:
        diagnostics.extend(_diagnose_section_aliases(document))
        diagnostics.extend(_diagnose_keys(document))
    return tuple(
        sorted(
            diagnostics,
            key=lambda item: (
                item.path.lower(),
                item.line,
                item.rule_id,
            ),
        )
    )


def _severity_counts(diagnostics: Iterable[Diagnostic]) -> dict[str, int]:
    counts = {"error": 0, "warning": 0, "info": 0}
    for diagnostic in diagnostics:
        counts[diagnostic.severity] = counts.get(diagnostic.severity, 0) + 1
    return counts


def _print_text(documents: tuple[OdfDocument, ...], diagnostics: tuple[Diagnostic, ...]) -> None:
    counts = _severity_counts(diagnostics)
    print(
        f"ODF Checker: {len(documents)} ODF(s), "
        f"{counts['error']} error(s), {counts['warning']} warning(s), {counts['info']} info"
    )
    if not diagnostics:
        print("No known Redux ODF schema problems found.")
        return

    for diagnostic in diagnostics:
        print()
        print(
            f"{diagnostic.path}:{diagnostic.line}: "
            f"{diagnostic.severity.upper()} {diagnostic.rule_id}"
        )
        print(f"  {diagnostic.message}")
        print(f"  Fix: {diagnostic.suggestion}")
        print(f"  Evidence ({diagnostic.evidence_kind}): {diagnostic.evidence}")


def _print_json(documents: tuple[OdfDocument, ...], diagnostics: tuple[Diagnostic, ...]) -> None:
    payload = {
        "format": "bzr-odf-checker-v1",
        "files_scanned": len(documents),
        "counts": _severity_counts(diagnostics),
        "diagnostics": [asdict(diagnostic) for diagnostic in diagnostics],
    }
    print(json.dumps(payload, indent=2))


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="odfcheck",
        description=(
            "Battlezone 98 Redux ODF checker. "
            "Scans an ODF, directory tree, or ZIP for code/stock-contract-backed schema defects."
        ),
    )
    parser.add_argument("source", type=Path, help="ODF file, mod directory, or ZIP archive")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of terminal diagnostics.",
    )
    parser.add_argument(
        "--fail-on",
        choices=("error", "warning", "none"),
        default="error",
        help="Exit non-zero on this severity or higher (default: error).",
    )
    return parser


def exit_code(diagnostics: tuple[Diagnostic, ...], fail_on: str) -> int:
    if fail_on == "none":
        return 0
    severities = {diagnostic.severity for diagnostic in diagnostics}
    if "error" in severities:
        return 1
    if fail_on == "warning" and "warning" in severities:
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        documents = load_documents(args.source)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"odfcheck: {exc}", file=sys.stderr)
        return 2

    diagnostics = scan_documents(documents)
    if args.json:
        _print_json(documents, diagnostics)
    else:
        _print_text(documents, diagnostics)
    return exit_code(diagnostics, args.fail_on)


if __name__ == "__main__":
    raise SystemExit(main())
