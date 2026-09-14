"""
pyhula 改造パッチ適用スクリプト
================================

使い方:
1. このスクリプト (build_patched_wheel.py) と、
   controlserver.py / userapi.py を同じフォルダに置く
2. 元の pyhula の .whl ファイル
   (例: pyhula-1.1.8-cp312-cp312-win_amd64.whl)
   も同じフォルダに置く
3. そのフォルダで以下を実行する

     python build_patched_wheel.py

4. 同じフォルダに「(元のファイル名)-patched.whl」が生成される
5. できあがった .whl を pip でインストールする

     pip install pyhula-1.1.8-cp312-cp312-win_amd64-patched.whl --force-reinstall

これだけで、改造版の userapi.py / controlserver.py が反映されます。
巨大な .whl を送り合う必要はありません。
"""

import glob
import hashlib
import base64
import os
import shutil
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))

# 差し替えたい2ファイル(このスクリプトと同じフォルダに置く前提)
PATCH_FILES = {
    "pyhula/userapi.py": os.path.join(HERE, "userapi.py"),
    "pyhula/fylo/controlserver.py": os.path.join(HERE, "controlserver.py"),
}

# 差し替えにより不要になる、古いコンパイル済みバイナリ
# (残っているとそちらが優先されて改造が反映されないため削除する)
FILES_TO_REMOVE = [
    "pyhula/fylo/controlserver.cp312-win_amd64.pyd",
]


def record_hash(path):
    with open(path, "rb") as f:
        data = f.read()
    digest = hashlib.sha256(data).digest()
    b64 = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return f"sha256={b64}", len(data)


def find_original_wheel():
    candidates = [
        f for f in glob.glob(os.path.join(HERE, "*.whl")) if "-patched" not in f
    ]
    if not candidates:
        print("エラー: 元の pyhula-*.whl ファイルが見つかりません。")
        print("このスクリプトと同じフォルダに .whl ファイルを置いてください。")
        sys.exit(1)
    if len(candidates) > 1:
        print("複数の .whl ファイルが見つかりました。使うものを選んでください:")
        for i, c in enumerate(candidates):
            print(f"  [{i}] {os.path.basename(c)}")
        idx = int(input("番号を入力: "))
        return candidates[idx]
    return candidates[0]


def main():
    for label, path in PATCH_FILES.items():
        if not os.path.exists(path):
            print(f"エラー: {os.path.basename(path)} が見つかりません。")
            print("このスクリプトと同じフォルダに置いてください。")
            sys.exit(1)

    original_wheel = find_original_wheel()
    print(f"元の wheel: {os.path.basename(original_wheel)}")

    with tempfile.TemporaryDirectory() as tmpdir:
        # 1. 展開
        with zipfile.ZipFile(original_wheel) as zf:
            zf.extractall(tmpdir)

        # 2. 不要な古いバイナリを削除
        for rel_path in FILES_TO_REMOVE:
            target = os.path.join(tmpdir, rel_path)
            if os.path.exists(target):
                os.remove(target)
                print(f"削除: {rel_path}")

        # 3. 改造版ファイルを配置
        for rel_path, src in PATCH_FILES.items():
            dest = os.path.join(tmpdir, rel_path)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(src, dest)
            print(f"差し替え: {rel_path}")

        # 4. RECORD ファイルを実体に合わせて更新
        dist_info_dirs = glob.glob(os.path.join(tmpdir, "*.dist-info"))
        if not dist_info_dirs:
            print("エラー: dist-info フォルダが見つかりません。wheel の構造が想定と違います。")
            sys.exit(1)
        record_path = os.path.join(dist_info_dirs[0], "RECORD")

        with open(record_path, encoding="utf-8") as f:
            lines = f.readlines()

        removed_set = set(FILES_TO_REMOVE)
        patched_set = set(PATCH_FILES.keys())
        already_written = set()

        new_lines = []
        for line in lines:
            rel_path = line.split(",")[0]
            if rel_path in removed_set:
                continue
            if rel_path in patched_set:
                full_path = os.path.join(tmpdir, rel_path)
                h, size = record_hash(full_path)
                new_lines.append(f"{rel_path},{h},{size}\n")
                already_written.add(rel_path)
                continue
            new_lines.append(line)

        # 元の RECORD に無かった新規ファイル(controlserver.py など)を追加
        for rel_path in patched_set - already_written:
            full_path = os.path.join(tmpdir, rel_path)
            h, size = record_hash(full_path)
            new_lines.append(f"{rel_path},{h},{size}\n")

        with open(record_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

        # 5. 再度 zip 化 (.whl として保存)
        base_name = os.path.basename(original_wheel)
        name_no_ext = base_name[:-4] if base_name.lower().endswith(".whl") else base_name
        output_path = os.path.join(HERE, f"{name_no_ext}-patched.whl")

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _dirs, files in os.walk(tmpdir):
                for file in files:
                    full_path = os.path.join(root, file)
                    arcname = os.path.relpath(full_path, tmpdir)
                    zf.write(full_path, arcname)

    print()
    print("完成しました:", os.path.basename(output_path))
    print()
    print("次はこれをインストールしてください:")
    print(f"  pip install \"{os.path.basename(output_path)}\" --force-reinstall")


if __name__ == "__main__":
    main()
