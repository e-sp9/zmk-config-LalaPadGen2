# キーレイアウトの変更

- キー割り当て、コンボ、長押し、レイヤー、物理配置、タッチパッドのキー割り当てを変更した場合は、必ず同じ変更内で README のキー配置画像と関連する説明を更新する。
- 画像の正本は `config/lalapadgen2.keymap` と `config/lalapadgen2.json`。画像だけを手編集しない。
- `python3 scripts/render_keymap.py` で `docs/keymap/*.svg` と README の自動生成セクションを更新する。新しい動作を追加したら、必要に応じて生成スクリプトの表示名・描画処理も更新する。
- 完了前に `python3 scripts/render_keymap.py --check` と `git diff --check` を実行し、生成画像を開いて文字の重なりや欠落がないことを確認する。
- 通常レイヤーだけでなく全レイヤー、コンボ、タップ／ホールドの動作を確認する。README の画像を削除したり、古い画像のまま完了扱いにしない。
