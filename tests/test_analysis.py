import unittest
from pathlib import Path

import analysis


TEMP_ROOT = Path(__file__).parent / "_tmp"


class AnalysisTests(unittest.TestCase):
    def test_find_header_row_detects_checkpoint_and_serial_number(self):
        TEMP_ROOT.mkdir(exist_ok=True)
        csv_file = TEMP_ROOT / "sample.csv"
        csv_file.write_text(
            "metadata,,,,\n"
            "more metadata,,,,\n"
            "Site,Product,SerialNumber,Checkpoint,Test Pass/Fail Status\n"
            "JAWX,B529,SN001,T0,PASS\n",
            encoding="utf-8",
        )

        self.assertEqual(analysis.find_header_row(csv_file), 2)

    def test_discover_power_delta_columns_maps_2442_as_middle_channel(self):
        columns = [
            "SerialNumber",
            "Checkpoint",
            "tc=Power tech=BT:subtc=Avg ant=0:rate=1LE:pwr=8:freq=2402_Delta",
            "tc=Power tech=BT:subtc=Avg ant=0:rate=1LE:pwr=8:freq=2442_Delta",
            "tc=Power tech=BT:subtc=Avg ant=0:rate=1LE:pwr=8:freq=2480_Delta",
        ]

        discovered = analysis.discover_power_delta_columns(columns)

        self.assertEqual(discovered["Tx_LC"].frequency, "2402")
        self.assertEqual(discovered["Tx_MC"].frequency, "2442")
        self.assertEqual(discovered["Tx_HC"].frequency, "2480")

    def test_resolve_data_file_supports_uploaded_file_ids(self):
        TEMP_ROOT.mkdir(exist_ok=True)
        data_dir = TEMP_ROOT / "data"
        upload_dir = TEMP_ROOT / "uploads"
        data_dir.mkdir(exist_ok=True)
        upload_dir.mkdir(exist_ok=True)
        uploaded = upload_dir / "upload.csv"
        uploaded.write_text("SerialNumber,Checkpoint\n", encoding="utf-8")

        resolved = analysis.resolve_data_file("upload:upload.csv", data_dir, upload_dir)

        self.assertEqual(resolved.path, uploaded)
        self.assertEqual(resolved.source_type, "upload")
        self.assertEqual(resolved.display_name, "upload.csv")

    def test_discover_raw_power_columns_all_three_naming_patterns(self):
        # Pattern 1 — B529: ; separator, _Delta on subtc
        cols_p1 = [
            "tech=BT;rate=1LE;pwr=8.0;freq=2402;tc=Power subtc=Avg",
            "tech=BT;rate=1LE;pwr=8.0;freq=2402;tc=Power subtc=Avg_Delta",
        ]
        raw = analysis.discover_raw_power_columns(cols_p1)
        self.assertIn("Tx_LC", raw)
        self.assertIn("Avg", raw["Tx_LC"].column)
        self.assertNotIn("Delta", raw["Tx_LC"].column)

        # Pattern 2 — B519a: : separator, _Delta on freq
        cols_p2 = [
            "tc=Power tech=BT:subtc=Avg ant=0:rate=1LE:pwr=8:freq=2402",
            "tc=Power tech=BT:subtc=Avg ant=0:rate=1LE:pwr=8:freq=2402_Delta",
        ]
        raw = analysis.discover_raw_power_columns(cols_p2)
        self.assertIn("Tx_LC", raw)
        self.assertNotIn("Delta", raw["Tx_LC"].column.lower())

        # Pattern 3 — RX_Processed: subtc=Power_Abs / subtc=Power_Delta
        cols_p3 = [
            "tech=BT;rate=1LE;pwr=8.0;freq=2402;tc=Power subtc=Power_Abs",
            "tech=BT;rate=1LE;pwr=8.0;freq=2402;tc=Power subtc=Power_Delta",
        ]
        raw = analysis.discover_raw_power_columns(cols_p3)
        self.assertIn("Tx_LC", raw)
        self.assertIn("Power_Abs", raw["Tx_LC"].column)

    def test_discover_raw_power_columns_excludes_acp(self):
        cols = [
            "tech=BT;rate=1LE;pwr=8.0;freq=2402;tc=Power subtc=Power_Abs",
            "tech=BT;rate=1LE;pwr=8.0;freq=2402;tc=Power subtc=ACP subsubtc=1",
        ]
        raw = analysis.discover_raw_power_columns(cols)
        self.assertIn("Tx_LC", raw)
        self.assertIn("Power_Abs", raw["Tx_LC"].column)

    def test_parse_test_column_extracts_tc_across_naming_patterns(self):
        from analysis import parse_test_column

        # Pattern 1: ; separator
        p = parse_test_column("tech=BT;rate=1LE;freq=2402;tc=Power subtc=Avg")
        self.assertEqual(p["test_class"], "power")
        self.assertTrue(p["is_power"])
        self.assertFalse(p["is_delta"])

        # Pattern 2: : separator, tc at start
        p = parse_test_column("tc=Power tech=BT:subtc=Avg:freq=2402")
        self.assertEqual(p["test_class"], "power")

        # Pattern 3: ; separator, subtc=Power_Abs
        p = parse_test_column("tech=BT;freq=2402;tc=Power subtc=Power_Abs")
        self.assertEqual(p["test_class"], "power")
        self.assertTrue(p["is_power"])
        self.assertFalse(p["is_delta"])

    def test_resolve_data_file_supports_raw_file_ids(self):
        TEMP_ROOT.mkdir(exist_ok=True)
        data_dir = TEMP_ROOT / "data"
        upload_dir = TEMP_ROOT / "uploads"
        data_dir.mkdir(exist_ok=True)
        upload_dir.mkdir(exist_ok=True)
        raw_file = data_dir / "Organized_raw.csv"
        raw_file.write_text("SerialNumber,Checkpoint\n", encoding="utf-8")

        resolved = analysis.resolve_data_file("raw:Organized_raw.csv", data_dir, upload_dir)

        self.assertEqual(resolved.path, raw_file)
        self.assertEqual(resolved.source_type, "raw")
        self.assertEqual(resolved.file_id, "raw:Organized_raw.csv")


if __name__ == "__main__":
    unittest.main()
