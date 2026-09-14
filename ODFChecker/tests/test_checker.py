from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from odfcheck.checker import load_documents, parse_odf, scan_documents


class OdfCheckerTests(unittest.TestCase):
    def test_flare_building_class_is_crash_risk(self) -> None:
        document = parse_odf(
            "azflmpit.odf",
            """
[GameObjectClass]
baseName = "flare"

[FlareBuildingClass]
payloadName = "xmlasbld"
shotDelay = 0.10
""",
        )
        diagnostics = scan_documents((document,))
        ids = {diagnostic.rule_id for diagnostic in diagnostics}
        self.assertIn("BZODF001", ids)

        flare = next(d for d in diagnostics if d.rule_id == "BZODF001")
        self.assertEqual("error", flare.severity)
        self.assertIn("payloadName is present", flare.message)

    def test_absozero_known_schema_defects(self) -> None:
        document = parse_odf(
            "azsample.odf",
            """
[GameObject]
basename = "avtank"

[MagnetClass]
triggetDelay = 0.25

[ScavengerCraftClass]
scrapCapacity = 20

[flameClass]
flameLength = 12
variance = 2
shotColor = 1 0 0

[ExplosionClass]
xplBuilding = "xmlasbld"
""",
        )
        diagnostics = scan_documents((document,))
        ids = [diagnostic.rule_id for diagnostic in diagnostics]
        self.assertIn("BZODF002", ids)
        self.assertIn("BZODF003", ids)
        self.assertIn("BZODF004", ids)
        self.assertIn("BZODF005", ids)
        self.assertIn("BZODF101", ids)
        self.assertIn("BZODF102", ids)
        self.assertEqual(3, ids.count("BZODF103"))
        self.assertIn("BZODF104", ids)

    def test_correct_sections_do_not_trigger_alias_rules(self) -> None:
        document = parse_odf(
            "good.odf",
            """
[GameObjectClass]
baseName = "avtank"

[FlareMineClass]
payloadName = "xlasbld"

[MagnetMineClass]
triggerDelay = 0.25

[ScavengerClass]
scrapCapacity = 20

[FlamePuffClass]
flameRadius = 4
flameDelay = 0.1
flameTexture = "flame"
flameFrames = 8
""",
        )
        diagnostics = scan_documents((document,))
        self.assertEqual((), diagnostics)

    def test_zip_scan_is_case_insensitive_for_extension(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = Path(temp_dir) / "mod.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr(
                    "addon/AZMGPUL2.ODF",
                    "[MagnetClass]\ntriggetDelay = 0.10\n",
                )
                archive.writestr("addon/readme.txt", "ignored")

            documents = load_documents(archive_path)
            self.assertEqual(1, len(documents))
            diagnostics = scan_documents(documents)
            self.assertEqual(
                {"BZODF002", "BZODF101"},
                {diagnostic.rule_id for diagnostic in diagnostics},
            )


if __name__ == "__main__":
    unittest.main()
