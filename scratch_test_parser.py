"""Quick validation of filename parser against real filenames."""
import sys
sys.path.insert(0, ".")
from app.services.filename_parser import parse_filename

test_cases = [
    "Organized_B529-EVT_D69-Q41A-HS-Drop200-OTA_Data_RX_Processed.csv",
    "Organized_B529-EVT_D69-Q54-HS-HSD-Top750-OTA_Data.csv",
    "Organized_B529-EVT_PDER7A-Q55A-HS-HSD Granite-Top750-OTA_Data.csv",
    "Organized_B529-EVT_PDER7A-Q55A-HS-HSD PB-Top750-OTA_Data.csv",
    "Organized_B529-EVT_D71-G1COM-4-Corner-Drop200-OTA_Data.csv",
    "Organized_B529-EVT_R1FNF-NonHS-Drop200-OTA_Data-Plinko.csv",
    "Organized_B529-EVT_D69-Q41B1-1~5(Top side)-NonHS-Drop200 BT-OTA-0.0.51_RX_Processed.csv",
    "Organized_B529-P1_R3CBSNA-HS-Drop300-OTA_Data-Relbot.csv",
    "Organized_B519a-POR_1.07_POR-HS-Drop200-OTA_Data.csv",
    "Organized_PDER3 Drop 200 BT-OTA-0.0.51_RX_Processed.csv",
    "Organized_PDER5 Drop 200 OTA_Data_RX_Processed.csv",
    "Organized_D57-Q30-HS-Drop300 w dwell-OTA_Data_RX_Processed.csv",
    "Organized_D69-RSEVT-NonHS-Drop300-OTA_Data.csv",
    "Organized_B529-EVT_D65-G1 Drop200 BT-OTA-0.0.51_RX_Processed.csv",
    "Organized_B529-EVT_D66-PDER2.1A w HS Drop 200 BT-OTA-0.0.51_RX_Processed.csv",
    "Organized_B529-EVT_R2CNM-NonHS-Drop200-Relbot-OTA_Data.csv",
    "Organized_B529-EVT_D69-Q59A-HS-Drop300-OTA_Data.csv",
]

for fn in test_cases:
    r = parse_filename(fn)
    display = " · ".join(r["display_parts"])
    print(f"  {display}")
    print(f"    [project={r['project']}, build={r['build']}, cfg={r['cfg']}, "
          f"pc={r['precondition']}, cp={r['checkpoint']}, test={r['test_item']}, extra={r['extra']}]")
    print()
