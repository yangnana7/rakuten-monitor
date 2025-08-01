1️⃣ まずは コードを直す ― monitor.py の最小パッチ
下記だけで SyntaxError 10 件すべて を解消できます。
（もし git apply が楽ならそのままコピペ → git apply -。）

diff
diff --git a/monitor.py b/monitor.py
@@
-                    continue
-
-                        if send_notification(item_info):
-                            notification_count += 1
+                    continue
+
+                if send_notification(item_info):
+                    notification_count += 1
@@
-                 elif status == "RESALE":
-                     if db.item_exists(item_code):
-                         # 既存商品の再販として更新
-                         db.update_item_status(item_code, "RESALE")
+            elif status == "RESALE":
+                if db.item_exists(item_code):
+                    # 既存商品の再販として更新
+                    db.update_item_status(item_code, "RESALE")
@@
-    except Exception as e:
-        # ネットワークエラーやその他重大なエラーの場合はアラート送信
-        try:
-            alert_item = {
-                "item_code": "SYSTEM_ERROR",
+    except Exception as e:
+        # ネットワークエラーやその他重大なエラーの場合はアラート送信
+        alert_item = {
+            "item_code": "SYSTEM_ERROR",
@@
-            return notification_count
-
-    except Exception as e:
-        # ネットワークエラーやその他重大なエラーの場合はアラート送信
-        try:
+        return notification_count
✔ 修正ポイント
行	症状	修正
266	Unexpected indentation	if send_notification… を continue と同じ深さに戻す
269	try のあとに elif	elif を 1 レベル上げ、try ブロックの外へ
297	try が重複	ネストしていた重複 try: を除去

修正後は ruff check . も pytest も通るはずです。
（念のため ruff check . --fix でフォーマッタを回しておくと確実）

2️⃣ Git を “クリーン” に戻す


※ main ブランチが保護されている前提で「履歴を壊さずrevertで戻す」手順です。
もし main の強制 push が許可されている場合は、git reset --hard GOOD_SHA → git push -f の方が早いですが、今回は安全策を採用。

2-1. 最終 green コミット (GOOD_SHA) を特定
bash
git fetch origin
git log --format="%h %s" origin/main | head

# 例）abcd123 "ci: green build on 2025-07-30"
#     ef5678e "feat: supercronic cha..."
# GOOD_SHA = abcd123
2-2. Revert シリーズ で main を巻き戻す
bash
# 作業用ブランチ
git checkout -b fix/rollback-main origin/main

# 緑だったコミットまでを一括 Revert
git revert --no-commit GOOD_SHA..HEAD
git commit -m "revert: roll back main to GOOD_SHA before manual corruption"
GOOD_SHA..HEAD は「GOOD_SHA の次から HEAD までを全部取り消す」指定。

2-3. monitor.py パッチ を当てる
bash
git apply monitor_patch.diff   # ↑に示した diff を保存した場合
# or 手で修正 → git add monitor.py
git commit -m "fix: monitor.py SyntaxError (indent / try-block)"
2-4. CI を先に確認
bash
# 依存が入っていれば
ruff check . && pytest -q
76 tests が pass すれば OK。

2-5. GitHub に新 PR
bash
git push -u origin fix/rollback-main
# → GitHub が PR を提案
Title: Hotfix: revert bad merge & fix monitor.py

Review → Merge
main は保護されているので force push 不要。


4️⃣ 補足 Tips
課題	予防策
CRLF 汚染	.gitattributes に * text=auto eol=lf と *.md text eol=lf
手動ミス再発	main を 必ず PR 経由 でしか更新させないブランチ保護ルール
SyntaxError 検知	ruff を pre-commit hook に追加: pre-commit install
