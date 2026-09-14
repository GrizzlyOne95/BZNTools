# Battlezone 98 Redux ODF Checker

`odfcheck` is a cross-platform Python checker for Battlezone 98 Redux ODF files. It is intended to catch silent loader mismatches and crash-prone ODF schema mistakes using rules backed by the Redux loader/decompilation corpus, stock ODF contracts, or specifically documented compatibility fixes.

The checker is deliberately conservative: it reports rules we can support with evidence rather than treating every unfamiliar section/key as invalid.

## Requirements

- Python 3.10+
- No runtime dependencies
- Windows, Linux, or macOS

## Run without installing

From the `ODFChecker` directory:

```bash
PYTHONPATH=src python -m odfcheck /path/to/mod
```

On PowerShell:

```powershell
$env:PYTHONPATH = "src"
python -m odfcheck C:\path\to\mod
```

The input can be:

- one `.odf` file;
- a directory tree (all `.odf` files are scanned recursively); or
- a `.zip` archive containing ODFs.

## Install the CLI

```bash
python -m pip install ./ODFChecker
odfcheck /path/to/mod
```

For development:

```bash
python -m pip install -e ./ODFChecker
odfcheck /path/to/mod
```

## Output

Example:

```text
ODF Checker: 46 ODF(s), 3 error(s), 8 warning(s), 0 info

azflmpit.odf:18: ERROR BZODF001
  [FlareBuildingClass] should be [FlareMineClass]. payloadName is present, but it is under [FlareBuildingClass], a section the Redux FlareMineClass loader does not consume. ...
  Fix: Rename the section to [FlareMineClass].
  Evidence (code-derived): BZ1_Source Redux decomp: FlareMineClass::Load 0x004D2B10; ...
```

Machine-readable output is available for CI/editor integration:

```bash
odfcheck mod.zip --json
```

By default the process exits non-zero only for `error` findings. To make warnings fail CI as well:

```bash
odfcheck addon --fail-on warning
```

To use the checker as a report-only tool:

```bash
odfcheck addon --fail-on none
```

## Initial Redux rules

The first rule set is intentionally small and high-confidence.

| Rule | Severity | Detects |
| --- | --- | --- |
| `BZODF001` | Error | `[FlareBuildingClass]` instead of `[FlareMineClass]`; can leave the FlareMine payload class null and crash in `FlareMine::Update` |
| `BZODF002` | Warning | `[MagnetClass]` instead of `[MagnetMineClass]` |
| `BZODF003` | Warning | `[ScavengerCraftClass]` instead of `[ScavengerClass]` |
| `BZODF004` | Warning | `[flameClass]` instead of `[FlamePuffClass]` |
| `BZODF005` | Error | `[GameObject]` instead of `[GameObjectClass]` |
| `BZODF101` | Warning | `triggetDelay` instead of `triggerDelay` |
| `BZODF102` | Error | `basename` instead of `baseName` on the affected GameObject loader path |
| `BZODF103` | Warning | legacy/non-Redux flame keys such as `flameLength`, `variance`, and `shotColor` |
| `BZODF104` | Warning | known bad `xplBuilding = "xmlasbld"` reference |

Each diagnostic identifies its evidence category:

- `code-derived` — traced to a concrete Redux loader/update path;
- `compatibility` — established by the Redux stock class/key contract;
- `known-fix` — a content-specific correction confirmed during live triage.

This separation is important: future schema mining from `BZ1_Source` can expand the code-derived rule set without presenting inferred conventions as engine facts.

## Tests

```bash
python -m pip install -e ./ODFChecker
python -m unittest discover -s ODFChecker/tests -v
```

The regression suite includes the AbsoZero-style flare crash, the related silent section/key failures, corrected versions of those schemas, and ZIP archive scanning.

## Direction

The next layer should derive more of the schema automatically from the Redux decompilation/source corpus:

1. identify ODF load functions and their section/key hash lookups;
2. associate those lookups with class/load inheritance;
3. record expected value/reference types and required-vs-optional semantics;
4. validate effective values across `baseName` inheritance;
5. validate ODF-to-ODF references against the mod plus an optional stock ODF corpus;
6. distinguish ignored data from crash-prone missing data.

That makes the tool a codebase-rooted compatibility checker rather than a growing list of hand-written typo checks.
