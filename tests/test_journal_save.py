import os
import json
import pytest
import shutil
from unittest.mock import patch
import scripts.journal_save as js

# テストデータ
VALID_SESSION_DATA = {
    "session_id": "2026-06-22T17-00_285A.T_dcf",
    "date": "2026-06-22",
    "ticker": ["285A.T"],
    "company": ["KIOXIA Holdings"],
    "workflow": "dcf",
    "trigger": "manual",
    "tags": ["NAND", "半導体"],
    "confidence": "high",
    "price_at_session": 2150.0,
    "artifacts": [
        "out/285A.T_KIOXIA_HOLDINGS_CORPORATION/analysis/dcf_285A.T.xlsx"
    ],
    "summary_markdown": "# セッション要約\n\n## 目的\nキオクシアのDCFモデルを構築し、適正株価を算出する。\n\n## 結論...\n",
    "decisions": [
        {
            "id": "d001",
            "category": "assumption",
            "topic": "WACC設定",
            "question": "WACCを何%に設定するか",
            "chosen": "8.5%",
            "alternatives": [
                {"value": "7.8%", "reason_rejected": "リスクフリーレートの上昇を未反映"}
            ],
            "rationale": "10年JGB 1.05% + エクイティリスクプレミアム6.0% + ベータ1.15で算出",
            "source": "日本証券業協会公表データ、Bloomberg",
            "confidence": "high",
            "impact": "high"
        }
    ]
}

INVALID_SESSION_DATA = {
    "session_id": "invalid-id-format",  # パターン不一致
    "date": "2026-06-22",
    "ticker": "285A.T",  # 配列ではない
    "company": ["KIOXIA Holdings"],
    "workflow": "dcf",
    "trigger": "invalid-trigger",  # enum違反
    "tags": ["NAND"],
    "confidence": "high",
    "artifacts": [],
    "decisions": []
}

@pytest.fixture
def temp_journal_dir(tmp_path):
    """
    テスト用の一時的な JOURNAL_DIR を提供するフィクスチャ。
    テスト終了後に自動クリーンアップされる。
    """
    orig_dir = js.JOURNAL_DIR
    js.JOURNAL_DIR = str(tmp_path)
    yield tmp_path
    js.JOURNAL_DIR = orig_dir

def test_validate_data_valid():
    # 正常データの検証が通ることを確認
    assert js.validate_data(VALID_SESSION_DATA) is True

def test_validate_data_invalid():
    # 異常データで例外が発生することを確認
    with pytest.raises(ValueError):
        js.validate_data(INVALID_SESSION_DATA)

def test_save_session_files_creation(temp_journal_dir):
    md_path, json_path = js.save_session(VALID_SESSION_DATA)
    
    assert os.path.exists(md_path)
    assert os.path.exists(json_path)
    
    # MDファイルの内容確認
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()
        assert "session_id: \"2026-06-22T17-00_285A.T_dcf\"" in content
        assert "ticker:" in content
        assert "  - \"285A.T\"" in content
        assert "キオクシアのDCFモデルを構築し" in content
        
    # JSONファイルの内容確認
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        assert data["session_id"] == "2026-06-22T17-00_285A.T_dcf"
        assert len(data["decisions"]) == 1
        assert data["decisions"][0]["topic"] == "WACC設定"

def test_index_json_update(temp_journal_dir):
    # 最初のセッション保存
    js.save_session(VALID_SESSION_DATA)
    
    index_path = os.path.join(str(temp_journal_dir), "index.json")
    assert os.path.exists(index_path)
    
    with open(index_path, "r", encoding="utf-8") as f:
        index_data = json.load(f)
        assert len(index_data["sessions"]) == 1
        assert index_data["sessions"][0]["session_id"] == "2026-06-22T17-00_285A.T_dcf"
        assert index_data["sessions"][0]["tickers"] == ["285A.T"]
        
    # 2回目のセッション（同じID）保存で上書きされることを確認
    modified_data = VALID_SESSION_DATA.copy()
    modified_data["confidence"] = "low"
    js.save_session(modified_data)
    
    with open(index_path, "r", encoding="utf-8") as f:
        index_data = json.load(f)
        assert len(index_data["sessions"]) == 1
        assert index_data["sessions"][0]["confidence"] == "low"
        
    # 異なるセッションIDの保存で追記されることを確認
    new_data = VALID_SESSION_DATA.copy()
    new_data["session_id"] = "2026-06-22T18-00_7203.T_comps"
    new_data["ticker"] = ["7203.T"]
    new_data["company"] = ["Toyota Motor"]
    js.save_session(new_data)
    
    with open(index_path, "r", encoding="utf-8") as f:
        index_data = json.load(f)
        assert len(index_data["sessions"]) == 2
        assert index_data["sessions"][1]["session_id"] == "2026-06-22T18-00_7203.T_comps"

def test_main_stdin(temp_journal_dir):
    # 標準入力からの受け渡しテスト
    test_json = json.dumps(VALID_SESSION_DATA)
    
    with patch("sys.argv", ["scripts/journal_save.py"]), \
         patch("sys.stdin.read", return_value=test_json), \
         patch("sys.stdin.isatty", return_value=False), \
         patch("sys.exit") as mock_exit:
        js.main()
        mock_exit.assert_not_called()
        
    index_path = os.path.join(str(temp_journal_dir), "index.json")
    assert os.path.exists(index_path)

def test_main_data_json(temp_journal_dir):
    test_json = json.dumps(VALID_SESSION_DATA)
    with patch("sys.argv", ["scripts/journal_save.py", "--data-json", test_json]), \
         patch("sys.exit") as mock_exit:
        js.main()
        mock_exit.assert_not_called()
    index_path = os.path.join(str(temp_journal_dir), "index.json")
    assert os.path.exists(index_path)

def test_main_data_file(temp_journal_dir, tmp_path):
    test_json = json.dumps(VALID_SESSION_DATA)
    data_file = tmp_path / "temp_data.json"
    data_file.write_text(test_json, encoding="utf-8")
    
    with patch("sys.argv", ["scripts/journal_save.py", "--data-file", str(data_file)]), \
         patch("sys.exit") as mock_exit:
        js.main()
        mock_exit.assert_not_called()
    index_path = os.path.join(str(temp_journal_dir), "index.json")
    assert os.path.exists(index_path)

def test_main_invalid_json(temp_journal_dir):
    with patch("sys.argv", ["scripts/journal_save.py", "--data-json", "{invalid-json"]), \
         patch("sys.exit") as mock_exit:
        js.main()
        mock_exit.assert_called_with(1)

def test_main_validation_failed(temp_journal_dir):
    invalid_data = VALID_SESSION_DATA.copy()
    invalid_data["session_id"] = "invalid"
    test_json = json.dumps(invalid_data)
    with patch("sys.argv", ["scripts/journal_save.py", "--data-json", test_json]), \
         patch("sys.exit") as mock_exit:
        js.main()
        mock_exit.assert_called_with(1)

