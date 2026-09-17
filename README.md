# Battlezone BZN Format Reference

> **Reference-only fork.** This repository is retained primarily for its Battlezone BZN format documentation and parser implementation details. It is **not** the maintained packaged Battlezone BZN utility.
>
> For the supported user-facing tool, use **[Battlezone BZN Scanner](https://github.com/GrizzlyOne95/Battlezone98Redux_BZN_Scanner)** (`BZBZNScanner.exe`). New Battlezone-facing scanning, validation, diagnostics, and packaged tooling should live there.

## Purpose

This fork preserves useful reverse-engineering/reference material for the **Battlezone family BZN map/save format**, especially:

- Battlezone (1998)
- Battlezone 98 Redux
- Battlezone II: Combat Commander
- Battlezone Combat Commander
- Battlezone: Rise of the Black Dogs

The original codebase also contains support/framework work for Star Trek Armada formats. That material is retained as upstream/reference context, but it is not the focus of this fork.

`BZNConvert` and the rest of the solution should be treated as **reference code**, not as a separately supported Battlezone utility or release product.

## BZN Format Overview

BZN is a simple serialized data-array format used for Battlezone maps and save files. It can store data in both ASCII and binary forms.

At a high level:

- **Binary mode:** `Type + Size + Value`
- **ASCII mode:** `Name + Value`
- Save files use the same family of structures with additional game state.
- Individual Battlezone titles vary in field width, alignment, endian handling, and object semantics.
- ASCII BZNs are comparatively loose because they are emitted by simple text-writing code rather than a rigid schema.
- Binary BZNs are generally more structurally predictable.

## Battlezone Format Differences

| Game | Type size | Size size | Alignment | Endian |
|:--|--:|--:|--:|:--|
| Battlezone: Rise of the Black Dogs | 0 | 2 | 2 | Big |
| Battlezone (1998) | 2* | 2 | 0 | Little |
| Battlezone 98 Redux | 2 | 2 | 0 | Little |
| Battlezone II: Combat Commander | 1 | 2 | 0 | Little |
| Battlezone Combat Commander | 1 | 2 | 0 | Little |

\* Some Battlezone BZNs contain garbage in the high byte of the nominal two-byte type field. The parser therefore treats the effective type domain as one byte because the known type set is below 256 values.

## Structural Notes

The parser is split into two conceptual stages:

1. **Tokenizer / stream reader** — `BZNStreamReader` reads the file, determines flavor/format, and emits a stream of `BZNTokens`.
2. **Game-specific parser** — `BZNFileBattlezone` interprets those tokens using Battlezone-specific field/object knowledge.

This separation is useful reference material because it isolates the low-level serialized representation from game-specific object semantics.

### Object boundaries

One of the central difficulties is that binary BZN data does not provide explicit end markers for most objects. The parser therefore needs contextual knowledge to determine where one object ends and the next begins.

ASCII BZNs sometimes contain object-start markers, but these are effectively comments emitted by the game rather than a robust structural delimiter.

### Hints

`BZNFileBattlezone` can consume external hints describing expected object structures, such as information derived from ODF `classLabel` behavior. See the `BuildHintsBZ1` and `BuildHintsBZ2` implementations in `BZNParser/Battlezone/BZNFileBattlezone.cs` for reference.

Without sufficient hints, the parser uses memoized trial paths and may emit `MultiClass` results when more than one interpretation remains possible.

### Bookmarks / speculative parsing

The parser uses temporary bookmarks in the token stream as rollback points. This allows it to attempt an interpretation, detect that the guessed structure is inconsistent, rewind, and try another path.

This is particularly important for BZ2/Battlezone Combat Commander data, where substantial object information is not serialized directly into the BZN.

## Known Malformation Tracking

`BZNFileBattlezone.Malformations` tracks recoverable or notable structural issues. Existing categories include:

- `UNKNOWN` — unspecified condition; should normally not be used.
- `INCOMPAT` — data not loadable by the game.
- `MISINTERPRET` — a field was interpreted by the game as a different field but remains loadable.
- `OVERCOUNT` — more objects of a given type than expected.
- `NOT_IMPLEMENTED` — known field not yet implemented by the parser.
- `INCORRECT` — invalid serialized value corrected by the parser.
- `LINE_ENDING` — ASCII line endings differ from the CRLF form expected by Battlezone.

## Example Parser Use

```csharp
using BZNParser.Battlezone;
using BZNParser.Reader;

var hints = BattlezoneBZNHints.BuildHintsBZ1();

using var fileStream = File.OpenRead("path/to/file.bzn");
using var reader = new BZNStreamReader(fileStream, "path/to/file.bzn");
var bznFile = new BZNFileBattlezone(reader, Hints: hints);

// Parsed data is then available through the BZNFileBattlezone model.
```

## Relationship to Battlezone BZN Scanner

This repository should be used when we need to understand or cross-check **BZN serialization details, parser behavior, format differences, malformed-file handling, or conversion/reference logic**.

The maintained product path is:

**Battlezone98Redux_BZN_Scanner → `BZBZNScanner.exe`**

If a useful parser insight from this repository should become a supported feature, port the relevant concept into BZN Scanner rather than reviving `BZNConvert` as a competing packaged utility.

## Repository Status

- Reference/research repository: **yes**
- Supported packaged Battlezone utility: **no**
- Automatic `BZNConvert` releases: **disabled in this fork**
- Parser/source retained as implementation reference: **yes**
