#!/usr/bin/env python3
import argparse
import datetime
import json
import os
import sys

# プロジェクトのルートディレクトリと言語設定
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOURNAL_DIR = os.path.join(PROJECT_ROOT, "out", "_journal")
SCHEMAS_DIR = os.path.join(PROJECT_ROOT, "docs", "schemas")

def load_json_schema(schema_name):
    schema_path = os.path.join(SCHEMAS_DIR, schema_name)
    if os.path.exists(schema_path):
        with open(schema_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def validate_data(data):
    """
    jsonschemaライブラリが利用可能なら厳密にチェックし、
    利用不可の場合は簡易的なバリデーションを実行する。
    """
    schema = load_json_schema("session_schema.json")
    if not schema:
        # スキーマファイルが見つからない場合はスキップ
        return True

    try:
        import jsonschema
        jsonschema.validate(instance=data, schema=schema)
        return True
    except ImportError:
        # フォールバック: 簡易チェック
        required_fields = [
            "session_id", "date", "ticker", "company", "workflow",
            "trigger", "tags", "confidence", "artifacts", "decisions"
        ]
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")
        
        # session_id フォーマットチェック (正規表現)
        import re
        if not re.match(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}-[0-9]{2}_[A-Za-z0-9\.\-_]+_[A-Za-z0-9\.\-_]+$", data["session_id"]):
            raise ValueError(f"Invalid session_id format: {data['session_id']}")
            
        # 配列チェック
        for field in ["ticker", "company", "tags", "artifacts", "decisions"]:
            if not isinstance(data[field], list):
                raise ValueError(f"Field {field} must be an array")
                
        # decisionsの必須フィールドチェック
        for i, decision in enumerate(data["decisions"]):
            dec_required = ["id", "category", "topic", "question", "chosen", "rationale", "confidence", "impact"]
            for field in dec_required:
                if field not in decision:
                    raise ValueError(f"Missing required field in decisions[{i}]: {field}")
        return True
    except Exception as e:
        raise ValueError(f"Schema validation failed: {e}")

def save_session(data):
    session_id = data["session_id"]
    
    # sessionsディレクトリの確保
    sessions_dir = os.path.join(JOURNAL_DIR, "sessions")
    os.makedirs(sessions_dir, exist_ok=True)
    
    # 1. セッション要約 (MD) の生成
    md_path = os.path.join(sessions_dir, f"{session_id}.md")
    
    # フロントマター用データの抽出 (summary_markdownとdecisionsは除外)
    frontmatter = {
        "session_id": data["session_id"],
        "date": data["date"],
        "ticker": data["ticker"],
        "company": data["company"],
        "workflow": data["workflow"],
        "trigger": data["trigger"],
        "tags": data["tags"],
        "confidence": data["confidence"],
        "price_at_session": data.get("price_at_session"),
        "artifacts": data["artifacts"]
    }
    
    # YAML形式にシリアライズ (yamlライブラリに依存せず標準ライブラリで簡易出力)
    yaml_lines = ["---"]
    for k, v in frontmatter.items():
        if isinstance(v, list):
            if not v:
                yaml_lines.append(f"{k}: []")
            else:
                yaml_lines.append(f"{k}:")
                for item in v:
                    yaml_lines.append(f"  - \"{item}\"")
        elif v is None:
            yaml_lines.append(f"{k}: null")
        elif isinstance(v, (int, float)):
            yaml_lines.append(f"{k}: {v}")
        else:
            yaml_lines.append(f"{k}: \"{v}\"")
    yaml_lines.append("---")
    
    frontmatter_str = "\n".join(yaml_lines)
    
    summary_markdown = data.get("summary_markdown", "")
    if not summary_markdown.strip():
        # デフォルトのマークダウン本文を生成
        summary_markdown = f"# セッション要約: {session_id}\n\n## 目的\n未記述\n\n## 結論・主要アウトプット\n未記述\n"
        
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(frontmatter_str + "\n\n" + summary_markdown.strip() + "\n")
        
    # 2. 判断ログ (JSON) の生成
    decisions_path = os.path.join(sessions_dir, f"{session_id}_decisions.json")
    dec_data = {
        "session_id": session_id,
        "decisions": data["decisions"]
    }
    with open(decisions_path, "w", encoding="utf-8") as f:
        json.dump(dec_data, f, ensure_ascii=False, indent=2)
        
    # 3. インデックス (index.json) の更新
    update_index(data, md_path, decisions_path)
    
    return md_path, decisions_path

def update_index(data, md_path, decisions_path):
    index_path = os.path.join(JOURNAL_DIR, "index.json")
    os.makedirs(JOURNAL_DIR, exist_ok=True)
    
    index_data = {
        "sessions": [],
        "trade_count": 0,
        "last_updated": ""
    }
    
    if os.path.exists(index_path):
        try:
            with open(index_path, "r", encoding="utf-8") as f:
                index_data = json.load(f)
        except Exception:
            # 破損している場合は初期化
            pass
            
    # 相対パスに変換
    rel_md_path = os.path.relpath(md_path, JOURNAL_DIR).replace("\\", "/")
    rel_dec_path = os.path.relpath(decisions_path, JOURNAL_DIR).replace("\\", "/")
    rel_artifacts = []
    for art in data["artifacts"]:
        # 絶対パスかプロジェクトルート相対か判断して調整可能。
        # ここではそのまま格納
        rel_artifacts.append(art.replace("\\", "/"))
        
    session_entry = {
        "session_id": data["session_id"],
        "date": data["date"],
        "tickers": data["ticker"],
        "companies": data["company"],
        "workflow": data["workflow"],
        "trigger": data["trigger"],
        "confidence": data["confidence"],
        "tags": data["tags"],
        "summary_path": rel_md_path,
        "decisions_path": rel_dec_path,
        "artifact_paths": rel_artifacts
    }
    
    # 既存の同一セッションIDがある場合は置き換え、なければ追加
    existing_idx = -1
    for idx, s in enumerate(index_data.get("sessions", [])):
        if s["session_id"] == data["session_id"]:
            existing_idx = idx
            break
            
    if "sessions" not in index_data:
        index_data["sessions"] = []
        
    if existing_idx >= 0:
        index_data["sessions"][existing_idx] = session_entry
    else:
        index_data["sessions"].append(session_entry)
        
    # last_updatedの更新
    jst_timezone = datetime.timezone(datetime.timedelta(hours=9))
    now = datetime.datetime.now(jst_timezone)
    index_data["last_updated"] = now.isoformat()
    
    # trade_countの保証
    if "trade_count" not in index_data:
        index_data["trade_count"] = 0
        
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)

def main():
    parser = argparse.ArgumentParser(description="Save session journal and decisions.")
    parser.add_argument("--data-file", help="Path to JSON file containing session data")
    parser.add_argument("--data-json", help="Raw JSON string containing session data")
    
    args = parser.parse_args()
    
    raw_data = None
    if args.data_file:
        with open(args.data_file, "r", encoding="utf-8") as f:
            raw_data = f.read()
    elif args.data_json:
        raw_data = args.data_json
    else:
        # 引数なしの場合は標準入力から
        if not sys.stdin.isatty():
            raw_data = sys.stdin.read()
            
    if not raw_data or not raw_data.strip():
        print("Error: No data provided via --data-file, --data-json, or stdin.", file=sys.stderr)
        sys.exit(1)
        return
        
    try:
        data = json.loads(raw_data)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON format: {e}", file=sys.stderr)
        sys.exit(1)
        return
        
    try:
        validate_data(data)
    except ValueError as e:
        print(f"Error: Validation failed: {e}", file=sys.stderr)
        sys.exit(1)
        return
        
    try:
        md_path, json_path = save_session(data)
        print(f"SUCCESS: Saved session to {md_path} and {json_path}")
    except Exception as e:
        print(f"Error: Failed to save session: {e}", file=sys.stderr)
        sys.exit(1)
        return

if __name__ == "__main__":
    main()
