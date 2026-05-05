import app.services.data_service as data_service
from app.services.file_service import extract_metadata
from app.utils import merge_checkpoint_sequences


def test_get_cleaned_data_preserves_checkpoint_order_from_rawdata(temp_dirs):
    csv_path = temp_dirs["data"] / "Organized_order.csv"
    csv_path.write_text(
        "SerialNumber,Checkpoint,Test Pass/Fail Status,tech=BT;rate=1LE;freq=2402;tc=Power subtc=Avg\n"
        "SN001,T0,PASS,-1.0\n"
        "SN001,T3,PASS,-2.0\n"
        "SN001,T1,PASS,-3.0\n"
        "SN001,T2,PASS,-4.0\n",
        encoding="utf-8",
    )

    original_data_dir = data_service.DATA_DIR
    original_upload_dir = data_service.UPLOAD_DIR
    data_service.DATA_DIR = temp_dirs["data"]
    data_service.UPLOAD_DIR = temp_dirs["uploads"]
    try:
        full_df, unique_cps, reports, summary = data_service.get_cleaned_data(
            ["raw:Organized_order.csv"],
            include_fail_data=False,
            channels=None,
            data_type="delta",
        )
    finally:
        data_service.DATA_DIR = original_data_dir
        data_service.UPLOAD_DIR = original_upload_dir

    assert full_df is not None
    assert unique_cps == ["T0", "T3", "T1", "T2"]
    assert reports[0]["status"] == "ok"
    assert summary["valid_files"] == 1


def test_extract_metadata_preserves_checkpoint_order_from_rawdata(temp_dirs):
    csv_path = temp_dirs["data"] / "Organized_metadata.csv"
    csv_path.write_text(
        "SerialNumber,Checkpoint,tech=BT;rate=1LE;freq=2402;tc=Power subtc=Avg\n"
        "SN001,T0,-1.0\n"
        "SN001,T5,-2.0\n"
        "SN001,T1,-3.0\n"
        "SN001,T3,-4.0\n",
        encoding="utf-8",
    )

    metadata = extract_metadata(str(csv_path))

    assert metadata["unique_cps"] == ["T0", "T5", "T1", "T3"]


def test_merge_checkpoint_sequences_inserts_into_anchor_interval():
    merged = merge_checkpoint_sequences(
        [
            ["T0", "HS", "50", "100"],
            ["T0", "THC", "100"],
        ]
    )
    reversed_merged = merge_checkpoint_sequences(
        [
            ["T0", "THC", "100"],
            ["T0", "HS", "50", "100"],
        ]
    )

    assert merged == ["T0", "THC", "HS", "50", "100"]
    assert reversed_merged == ["T0", "THC", "HS", "50", "100"]


def test_get_cleaned_data_merges_cross_file_checkpoint_intervals(temp_dirs):
    file_a = temp_dirs["data"] / "Organized_a.csv"
    file_b = temp_dirs["data"] / "Organized_b.csv"

    file_a.write_text(
        "SerialNumber,Checkpoint,Test Pass/Fail Status,tech=BT;rate=1LE;freq=2402;tc=Power subtc=Avg\n"
        "SN001,T0,PASS,-1.0\n"
        "SN001,HS,PASS,-2.0\n"
        "SN001,50,PASS,-3.0\n"
        "SN001,100,PASS,-4.0\n",
        encoding="utf-8",
    )
    file_b.write_text(
        "SerialNumber,Checkpoint,Test Pass/Fail Status,tech=BT;rate=1LE;freq=2402;tc=Power subtc=Avg\n"
        "SN002,T0,PASS,-1.0\n"
        "SN002,THC,PASS,-2.0\n"
        "SN002,100,PASS,-3.0\n",
        encoding="utf-8",
    )

    original_data_dir = data_service.DATA_DIR
    original_upload_dir = data_service.UPLOAD_DIR
    data_service.DATA_DIR = temp_dirs["data"]
    data_service.UPLOAD_DIR = temp_dirs["uploads"]
    try:
        _full_df, unique_cps, reports, summary = data_service.get_cleaned_data(
            ["raw:Organized_a.csv", "raw:Organized_b.csv"],
            include_fail_data=False,
            channels=None,
            data_type="delta",
        )
    finally:
        data_service.DATA_DIR = original_data_dir
        data_service.UPLOAD_DIR = original_upload_dir

    assert unique_cps == ["T0", "THC", "HS", "50", "100"]
    assert all(report["status"] == "ok" for report in reports)
    assert summary["valid_files"] == 2
