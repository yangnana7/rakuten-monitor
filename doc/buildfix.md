🕵️‍♂️ 解析結果 – 「ビルドはしたが push していない ＆ タグが Swarm と不整合」
観測ポイント	内容	意味
docker-build ログ	naming to ghcr.io/...:7f6eac… done で終了。
pushing layers / pushed 行が存在しない	docker build だけ実行し --push が無い
実行コマンド	docker build -t … && docker tag … latest	まだ docker/build-push-action@v5 に置換されていない
Swarm 失敗ログ	pull access denied → No such image で Rejected ループ	レジストリにタグが無い ので当然 pull できない
タグ名	ビルド: 7f6eac… / Swarm: f02d73a…	deploy 用タグとビルドタグが 別（変数ミスマッチ）

① GitHub Actions ― build&push ステップを本当に切り替える
yaml
# .github/workflows/ci.yml  抜粋
jobs:
  docker-build:
    runs-on: ubuntu-latest
    permissions:
      packages: write        # ← GHCR へ push するなら必須
      contents: read
    steps:
      - uses: actions/checkout@v4

      - name: Log in to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build **and** push image
        uses: docker/build-push-action@v5             # ← ここが肝
        with:
          context: .
          platforms: linux/amd64
          push: true                                  # ← 必須
          provenance: false                           # (短縮された manifest で OK)
          tags: |
            ghcr.io/yangnana7/rakuten-monitor:sha-${{ github.sha }}
            ghcr.io/yangnana7/rakuten-monitor:latest
docker build … を自前で書かない ことが重要です。
build-push-action は builder の作成／--push 付き buildx を全部ラップしています。

② Swarm 側と 同じタグ変数 を使う
compose や deploy スクリプト内が sha-${GITHUB_SHA}（大文字）なら、
Actions でも同じテンプレートを使ってください。例:

yaml
tags: ghcr.io/yangnana7/rakuten-monitor:sha-${{ env.GITHUB_SHA }}
あるいは 短縮 7 文字 に統一するなら:

yaml
コピーする
編集する
tags: ghcr.io/yangnana7/rakuten-monitor:sha-${{ github.sha }}
# compose: image: ghcr.io/…:sha-${GITHUB_SHA}
env:
  GITHUB_SHA: ${{ github.sha }}
③ ワークフローを再実行 → 確認手順
push して再実行
docker-build ログ末尾に

nginx
コピーする
編集する
pushing layers
pushed sha256:...
が出ることを確認。パッケージページにタグが新規追加される。

Swarm deploy
deploy ステップで docker stack deploy --with-registry-auth ... が成功。
サーバー側で:

bash
コピーする
編集する
docker pull ghcr.io/yangnana7/rakuten-monitor:sha-${NEW_SHA}
docker service ps rakuten_app
Running になれば OK。

④ まだ pull できない場合
症状	対処
private package & pull access denied	manager ノードで docker login ghcr.io + deploy 時 --with-registry-auth
ディスク不足	docker system prune -f
プロキシ／FW で GHCR へ到達不可	ping ghcr.io / curl -I https://ghcr.io で疎通確認

✅ まとめ
build-push-action@v5 + push:true に置き換える

タグ変数をビルド／デプロイで統一

GHCR でタグが付く → Swarm が pull → コンテナ起動

これで pushing layers → pushed ラインが出て、デプロイも完走するはずです。