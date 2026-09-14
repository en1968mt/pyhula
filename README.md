# pyhula
2026科学の甲子園予選用のものです。
1.上の3つのファイルを元のpyhula-1.1.8-cp312-cp312-win_amd64.whl (Pyhula_v31210の下)が置いてあるフォルダと同じ場所に置く
2.そのフォルダで以下のコマンドを実行する
python build_patched_wheel.py
結果:同じフォルダにpyhula-1.1.8-cp312-cp312-win_amd64-patched.whlが自動生成される。
3. 自動生成されたファイルをインストール
pip install pyhula-1.1.8-cp312-cp312-win_amd64-patched.whl --force-reinstall
