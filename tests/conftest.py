import os
import sys

# プロジェクトルートと scripts ディレクトリを import パスに追加
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'scripts'))
