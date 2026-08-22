# jartic-traffic-regulation-converter

日本道路交通情報センター（JARTIC）がオープンデータとして公開している[交通規制情報](https://www.jartic.or.jp/service/opendata/)を全国分パースし、規制種別ごとのレイヤーに束ねて PMTiles に変換し、Web 地図で表示するツールです。

一時停止・信号機・一方通行・最高速度・ゾーン30といった規制は、交通シミュレーションのネットワーク属性としても、規制の分布を見る地図としても使えますが、配布形式は**1都道府県1ファイル・170列・全項目ダブルクォート囲みの CSV** で、そのままでは扱えません。このリポジトリはそこを埋めます。

## 収録データ

<!-- dataset:begin -->
| 項目 | 内容 |
|---|---|
| 対象年月 | 2026年06月 |
| 公開日 | 2026年08月01日(JARTIC) |
| 都道府県 | 47／47 |
| レコード数 | 4,395,720件 |
| 地図に載るフィーチャ数 | 4,389,367件 |
| 形状異常 | 357,583件（data/parse_report.json に内訳） |
| PMTiles | 567.4MB（R2配信(Range配信)） |
<!-- dataset:end -->

### レイヤー

規制種別は103種あり、そのまま並べても読めないため用途で束ねています（対応表は [`data/regulation_layers.json`](data/regulation_layers.json)）。

<!-- layers:begin -->
| レイヤー | 件数 |
|---|---|
| 一時停止 | 1,521,191 |
| 横断歩道 | 1,095,097 |
| 転回・右左折規制 | 407,692 |
| 駐車・停車 | 302,091 |
| 通行帯・中央線 | 268,393 |
| 信号機 | 198,976 |
| 最高速度・徐行 | 195,926 |
| 停止線 | 125,833 |
| 一方通行 | 112,771 |
| 通行止め・通行禁止 | 96,063 |
| 自転車 | 63,304 |
| その他 | 1,948 |
| 優先道路 | 82 |
<!-- layers:end -->

### 都道府県ごとの提供差

**JARTIC の交通規制情報は、都道府県警察ごとに提供する種別が違います。** 「全国データ」として扱うと、ある県には1件も存在しない種別に気づかないまま分析してしまいます。下は提供が47都道府県に届かない種別です（`data/parse_report.json` の `code_availability` から生成）。

たとえば**停止線（コード92）は9都道府県しか提供していません**。**指定方向外進行禁止（コード12）は46都道府県が提供していますが、北海道は提供していません。** 交通シミュレーションの入力に使う場合は、対象地域でその種別が提供されているかを先に確認してください。

<!-- availability:begin -->
| コード | 種別（代表名称） | 提供都道府県 | 全国件数 |
|---|---|---|---|
| 118 | 車両通行帯・進行方向別通行区分 | 1／47 | 1,921 |
| 90 | 導流帯 | 1／47 | 507 |
| 62 | 前方優先道路 | 1／47 | 50 |
| 88 | 安全地帯 | 1／47 | 49 |
| 9 | 重量制限 | 1／47 | 6 |
| 91 | 路面電車停留場 | 1／47 | 2 |
| 107 | 車両通行帯、進行方向別通行区分及び進路の変更禁止（高速道） | 2／47 | 32 |
| 69 | 駐車可 | 3／47 | 91 |
| 113 | Ｓ自専道 | 3／47 | 26 |
| 27 | 軌道敷地内を通行することが出来る区間 | 3／47 | 3 |
| 60 | 進行方向 | 4／47 | 649 |
| 54 | 優先道路 | 4／47 | 13 |
| 6 | 大型通行禁止 | 5／47 | 312 |
| 13 | 車両進入禁止 | 6／47 | 5,163 |
| 64 | 優先本線車道 | 6／47 | 9 |
| 2 | 特定小型原動機付自転車・自転車用道路 | 7／47 | 17 |
| 92 | 停止線 | 9／47 | 120,180 |
| 49 | 最低速度 | 10／47 | 19 |
| 53 | 車両の追越し禁止場所 | 11／47 | 64 |
| 77 | 警笛鳴らせ及び警笛区間 | 11／47 | 64 |
| 61 | 徐行 | 13／47 | 144 |
| 110 | 車両通行帯 | 14／47 | 3,394 |
| 93 | 二段停止線 | 14／47 | 770 |
| 94 | 左折可 | 14／47 | 143 |
| 72 | 時間制限駐車区分（パーキング設置） | 16／47 | 745 |
| 4 | 通行禁止 | 17／47 | 14,324 |
| 55 | 一般原動機付自転車の右折方法（二段階） | 17／47 | 702 |
| 50 | 車両横断禁止 | 17／47 | 100 |
| 71 | 停車可 | 19／47 | 169 |
| 21 | 車両通行帯・進行方向別通行区分 | 20／47 | 4,442 |
| 15 | 道路の中央線 | 22／47 | 1,048 |
| 119 | 進行方向別通行区分及び進路変更禁止 | 23／47 | 8,078 |
| 3 | 通禁（自転車等歩行者用） | 24／47 | 3,712 |
| 16 | 中央線の変移 | 25／47 | 15,939 |
| 83 | 普通自転車の交差点進入禁止 | 26／47 | 518 |
| 8 | 歩行者等通行止め | 27／47 | 631 |
| 19 | 立入禁止部分 | 30／47 | 170 |
| 58 | 進行方向別通行区分 | 31／47 | 49,334 |
| 52 | 進路変更禁止 | 32／47 | 7,987 |
| 24 | 路線バス等優先通行帯 | 34／47 | 237 |
| 57 | 右左折の方法 | 37／47 | 5,607 |
| 5 | 大型自動車等通行止め | 39／47 | 5,357 |
| 116 | 駐方 | 39／47 | 1,997 |
| 111 | 普通自転車専用通行帯 | 39／47 | 401 |
| 20 | 車両通行帯 | 40／47 | 46,508 |
| 7 | 踏切 | 40／47 | 964 |
| 1 | 通行禁止 | 41／47 | 6,622 |
| 100 | 高齢運転者等標章自動車駐車可 | 41／47 | 162 |
| 106 | 環状の交差点における右回り通行 | 41／47 | 126 |
| 86 | 斜め横断可 | 42／47 | 549 |
| 82 | 特例特定小型原動機付自転車・普通自転車の歩道通行部分 | 43／47 | 704 |
| 70 | 駐車可 | 44／47 | 1,413 |
| 14 | 歩行者横断禁止 | 44／47 | 695 |
| 98 | 信号機 | 45／47 | 111,471 |
| 117 | 路側 | 45／47 | 5,716 |
| 56 | 一般原動機付自転車の右折方法（小回り） | 45／47 | 3,942 |
| 12 | 指定方向外進行禁止 | 46／47 | 107,311 |
| 87 | 自転車横断帯 | 46／47 | 36,545 |
| 76 | 停止禁止部分 | 46／47 | 2,890 |
| 65 | 駐停車禁止 | 46／47 | 1,555 |
<!-- availability:end -->

## フォーマットの罠

実データ（2026年6月・47都道府県）で確認した点です。仕様書は[拡張版標準フォーマット k_2.1](https://www.jartic.or.jp/d/opendata/typeD_kisei_73_k_2.1.pdf)。

**座標は1フィールドに折れ線が丸ごと入る。** `経度 緯度;経度 緯度;...` の形で、点と点はセミコロン、経度と緯度はスペース区切りです。

```
141.357539927458 43.057881934149;141.357267729602 43.057848594729;...
```

**この座標フィールドは 128KB を超えることがある。** Python の `csv` は既定でフィールド長を 131,072 バイトに制限しているため、`csv.field_size_limit()` を上げないと途中で例外になります（実データで発生）。

**規制形態コードと実際の点数は一致しないことがある。** 「点・線・面コード」が 1（点）なのに座標が2点あるレコード、2（線）なのに1点しかないレコードが実在します。本ツールは**点数を優先**してジオメトリを決め、食い違いを `parse_report.json` に数えます。

**一方通行の向きは頂点順しかなく、しかも北海道では頂点順が通行方向の「逆」だった。** 共通規制種別コード11（一方通行）のレコードでは「進入方向」「禁止する方向」「指定する方向」がいずれも空で、方向を示すのは座標列の順序だけです。北海道警データを OSM の `oneway` タグと突合したところ、**判定できた51件中50件で頂点順が通行方向と系統的に逆**でした（実在の向き 南2条通=東行き・南3条通=西行き でも確認。検証手法は [sapporo-micro-traffic-sim の scripts/15_verify_oneway.py](https://github.com/shiwaku/sapporo-micro-traffic-sim/blob/main/scripts/15_verify_oneway.py)）。**頂点順をそのまま通行方向として使うと逆走ネットワークができます。** 他の都道府県で同じ規約かは未検証なので、利用する県ごとに OSM と突き合わせて確認してください。

**日本の範囲外の座標が混じる。** 元データ由来の誤りです。本ツールは経度 122〜154度・緯度 20〜46度の外を捨て、件数を `parse_report.json` の `broken_coordinate_points` に記録します。

**文字コードは cp932。** zip 内のファイル名も cp932 で格納されている場合があります。

## データ更新

毎月1日ごろ、対象月の約2か月後に新しい月が公開されます。GitHub Actions の [update-data](.github/workflows/update-data.yml) が**日次でカタログJSONを見て、対象年月が変わったときだけ**取り込みを走らせます。

```
カタログ確認 → 生zipを Release へ退避 → パース・PMTiles生成 → 品質ゲート → R2公開 → main更新 → Pages配信
```

配布URLは月次で変わる（`.../opendata/{更新日時}/typeD_{都道府県ローマ字}.zip`）ため、更新日時や対象年月はスクリプトに埋め込まず[公式のカタログJSON](https://www.jartic.or.jp/d/opendata/opendata.json)から解決します。

### 手元で実行する

依存は Python 3.12 標準ライブラリと [tippecanoe](https://github.com/felt/tippecanoe) のみです。

**tippecanoe には Windows 向けの配布がありません。手元では WSL2 の中で実行してください。** CI も Linux なので、これで CI と同じ経路になります。

```bash
# 実行できる環境か先に確かめる（tippecanoe の在処・版、ディスクの空き、設定ファイル）
python3 src/run_pipeline.py doctor

python3 src/run_pipeline.py check               # 新しい月が出ているかだけ見る
python3 src/run_pipeline.py run                 # 取得から data/ 反映まで通す
python3 src/run_pipeline.py run --reuse         # work/ にある成果物は作り直さない
python3 src/run_pipeline.py run --skip-download # 取得済みの work/zip を使う（CIと同じ経路）
```

終了コードは 0 正常 / 10 新しい月がある（`check`）/ 20 品質ゲートで停止 / 30 環境不備。

**中間生成物は `JARTIC_WORK_DIR` で置き場所を変えられます。** 全国分で zip 320MB・中間 GeoJSONL 約1.6GB・PMTiles 約0.2GB になるため、WSL2 から `/mnt/c` のリポジトリを触る構成では、work だけ Linux 側（ext4）へ逃がしてください。drvfs 越しの読み書きは桁で遅くなります。

```powershell
# Windows から WSL2 の中で通す（work は WSL 側の ext4 に置く）
wsl.exe bash -lc "cd /mnt/c/path/to/jartic-traffic-regulation-converter && JARTIC_WORK_DIR=~/jartic-work python3 src/run_pipeline.py run"
```

`run` は品質ゲートを通ったときだけ `data/` を書き換えます。個別に実行する場合:

```bash
# 1. 交通規制情報（typeD）を47都道府県分ダウンロード（約320MB）
python3 src/jartic_opendata_kisei_dl.py --out work/zip

# 特定県だけ見たいとき（カタログIDで絞る。R01=北海道 / R13=東京）
python3 src/jartic_opendata_kisei_dl.py --out work/zip --only R01 R13

# 2. 行区切りGeoJSON に変換（zipを展開せずストリーム処理）
python3 src/parse_regulation.py --zip-dir work/zip --out work

# 3. PMTiles を生成（ズーム域・属性は data/ の設定から読む）
python3 src/build_tiles.py --work work
```

### 品質ゲート

人のレビューを挟まずに公開するため、前回の結果と比べて次のいずれかに当たると公開を止め、Issue を立てます。

| 判定 | 内容 |
|---|---|
| 対象年月 | 前回より新しくない |
| フィーチャ数 | 前回比 −5% 超 |
| レイヤー | 前回あったレイヤーが0件になった |
| 都道府県 | 前回あった都道府県が欠けた |

しきい値は `src/run_pipeline.py run --max-feature-drop` で変えられます。

品質ゲート落ちだけでなく、**取得の失敗・タイル生成の失敗・R2 への公開失敗もすべて Issue になります**（`data-update-failure` ラベル）。日次で走るので、同じ失敗が続いたときは新しい Issue を立てずに既存へコメントを足します。

### タイルの作り方

生成パラメータは実測で決めています。北海道（R01）と東京（R13）の2県＝全国の15.8%で測った結果:

| 設定 | 2県のサイズ | 生成時間 | 全国換算 |
|---|---|---|---|
| `-Z0 -z14`・全属性（旧） | 98.2MB | 67秒 | 567MB（実測値） |
| `-Z9 -z14`・全属性 | 73.4MB | 27秒 | 約424MB |
| **`-Z9 -z14`・`uid` を外す（現在）** | **37.4MB** | **21秒** | **約216MB** |
| `-Z9 -z14`・表示に必要な9属性だけ | 32.3MB | 22秒 | 約187MB |

**ビューワは Z9 未満を描かないのに、Z0〜8 のタイルを作っていました。** 表示に効かないまま全体の25%と生成時間の60%を使っていたので、収録範囲を表示開始ズームに揃えました。

**`uid`（ユニークキー）1属性でタイルの48%を食っていました。** フィーチャごとに一意な文字列は MVT の辞書圧縮が効かないためです。地図の上で人が読む値でもないので外しました。`uid` は生zipと中間 GeoJSONL には残るので、元データへの追跡性は失われません。交差点名称・路線名は「どこの規制か」を読むのに要るので残しています（外しても3.7MBしか減りません）。

**タイルサイズ上限（`--maximum-tile-bytes`）は付けていません。** 上限を付けるとフィーチャが間引かれ、最大ズームまで寄っても規制が出てこなくなります。しかも効果は属性ダイエットに負けます（上限あり・全属性 50.8MB ＞ 上限なし・`uid` 抜き 37.4MB）。上限なしでも最大タイルは1.32MB、14,070枚のうち 500KB を超えるのは6枚だけでした。

### PMTiles の配布先

全国分は 100MB を超えるため、Git に置けません（GitHub の1ファイル上限）。`src/run_pipeline.py` はサイズを見て自動で切り替えます。

| サイズ | 配布 |
|---|---|
| 90MB 以下 | `data/regulation.pmtiles` としてリポジトリ同梱 |
| 90MB 超 | Cloudflare R2(`shi-works`)へ公開。ビューワは Range リクエストで読む |

R2 へは月次キーと latest キーの**2本**を置きます。月次キーは上書きしないので、過去月のタイルをあとから引けます。

```
https://shi-works.com/pmtiles/jartic-traffic-regulation-converter/{年月}/regulation.pmtiles  # 不変
https://shi-works.com/pmtiles/jartic-traffic-regulation-converter/regulation.pmtiles         # latest
```

**ビューワが読むのは月次キーです。** PMTiles は1ファイルを Range リクエストで細切れに読むため、latest を読ませると月次の差し替えと再生が重なったときに新旧のバイト列をまたいで取得してしまい、タイルが壊れます。月次キーは一度書いたら動かないので、その事故が起きません。あわせて `immutable` を付けているため、ブラウザは一度取った範囲を再検証しません。latest キーは `dataset.json` を読まない利用者向けの口として置いています。

書き込みは月次キー → latest の順で、それぞれアップロード後にサイズを検証します。月次キーの検証が通らなければ latest には触らず、`data/` のコミットもしないので、公開中のビューワは前月の月次キー（消えない）を読み続けます。

**`data/dataset.json` のコミットは R2 への公開が済んだあとに行います。** この順序が「`dataset.json` が指す URL は必ず存在する」という約束を成り立たせています。

月次キーは**直近12か月**を残し、それより古いものは公開時に削除します（月あたり約0.2GB）。残っている月は [`data/history.json`](data/history.json) にバケットの実際の状態から書き出します。保持月数は [`data/pipeline.json`](data/pipeline.json) の `r2.keep_months`。

```bash
python3 src/publish_r2.py            # 月次キー → latest の順に公開し、古い月を剪定
python3 src/publish_r2.py --dry-run  # 何をするかだけ出す
python3 src/publish_r2.py --copy-latest  # 手元に PMTiles が無いとき、R2 上の latest を月次キーへ複製
```

`dataset.json` には `pmtiles_bytes` と `pmtiles_sha256` も入るので、配布物が壊れていないか利用側で確かめられます。

**配信URLは [`data/dataset.json`](data/dataset.json) の `pmtiles_url` が単一の情報源**で、ビューワはそこを読みます。配布先を変えてもビューワのコードは触りません。

GitHub Release のアセットは CORS ヘッダーを返さずブラウザから読めないため使っていません。

### 更新したデータを確実に配信する

`update-data` は `data/` を更新したあと [pages](.github/workflows/pages.yml) を**明示的に呼び、配信するコミットを `ref` で渡します**。

- `github-actions[bot]` の push では `push` トリガーが発火しない（GitHub の仕様）
- 呼び出された側の `actions/checkout` は、既定では**呼び出し元の run のコミット＝更新前**を取る

この2つが重なると、データを更新しても Pages には前月のままの `dataset.json` が載り続けます。`ref` に push 後の SHA を渡すことでそこを塞いでいます。

### 生データのアーカイブ

**JARTIC は最新1か月分しか配布していません。** 過去月の配布URLは消えるため、生データは公開ウィンドウ内に取得しないと復旧できません。そのため update-data は**品質ゲートより先に**生zipを `raw-YYYYMM` の [Release](../../releases) へ退避します。ゲートに落ちても生データは残ります。

```bash
python3 src/mirror_archive.py              # Release から手元へ取り込む
python3 src/mirror_archive.py --from-work  # 手元の work/ から取り込む
# 既定の保存先は ../jartic-archive/{年月}/（環境変数 JARTIC_ARCHIVE_DIR で変更可）
```

## 設定

**同じ値を2か所に書かないため、設定は `data/` の JSON が単一の情報源です。** Python（`src/config.py`）・ビューワ（`viewer/src/config.ts`）・GitHub Actions のどれもここを読みます。

| ファイル | 内容 | 読む側 |
|---|---|---|
| [`data/pipeline.json`](data/pipeline.json) | ズーム域、タイルサイズ上限、同梱の上限MB、R2 の配信先と保持月数、tippecanoe のピン留め版 | Python / ビューワ / CI |
| [`data/attributes.json`](data/attributes.json) | タイルに載せる属性（元CSVの列名・タイル上のキー・ポップアップでの表示名） | Python / ビューワ |
| [`data/regulation_layers.json`](data/regulation_layers.json) | 規制種別コード → 表示レイヤーと色 | Python / ビューワ |

属性を増減するときは `data/attributes.json` だけを直します。パース時に載せる属性とポップアップに出す属性が同じ表から来るので、片方だけ変わることがありません。

## 各スクリプトの役割

| スクリプト | 役割 |
|---|---|
| `src/jartic_opendata_kisei_dl.py` | カタログJSONから最新の交通規制情報を解決して47都道府県分ダウンロード |
| `src/parse_regulation.py` | CSVをストリーム処理し、レイヤーごとの行区切りGeoJSONと品質レポートを出力 |
| `src/build_tiles.py` | 行区切りGeoJSONから PMTiles を1本生成（tippecanoe）。何で作ったかを `tiles_report.json` に残す |
| `src/run_pipeline.py` | 上記を1コマンドで通す。環境チェック（`doctor`）と品質ゲートを持つ |
| `src/publish_r2.py` | PMTiles を R2 の月次キーと latest へ公開し、古い月を剪定 |
| `src/archive_raw.py` | 生zipを `raw-YYYYMM` の Release へ退避 |
| `src/mirror_archive.py` | 生zipと成果物を月ごとのローカルアーカイブへ取り込む |
| `src/update_docs.py` | `dataset.json` から README の収録データ節を生成 |
| `src/config.py` | `data/` の設定JSONの読み口とパス |
| `src/dataset.py` | `data/dataset.json` の組み立てと読み書き |
| `src/gate.py` | 品質ゲートの判定 |
| `src/ci.py` | GitHub Actions への出力（step output / 実行サマリ） |

## テスト

```bash
python -m unittest discover -s tests
```

実データは320MBあるので CI では回せません。代わりに「実データで踏んだ罠」を数十行に詰めた **cp932 の合成zip** を作って、同じ経路（zipをストリーム読み → GeoJSONL → `parse_report.json`）を通します。tippecanoe は要りません。

押さえているのは、無人公開の安全装置である品質ゲートの4条件、128KBを超える座標フィールド、範囲外座標の除去、規制形態コードと点数の不一致、zip内ファイル名の cp932、そして「`dataset.json` がどの URL を指すか」です。[tests](.github/workflows/tests.yml) が push と PR で Linux・Windows の両方で走ります。

## ビューワ

```bash
cd viewer && npm install && npm run dev
```

MapLibre GL JS + PMTiles。[aerial-photo-tile-pipeline](https://github.com/shiwaku/aerial-photo-tile-pipeline/tree/main/viewer) のビューワをベースにしています。

| 機能 | 内容 |
|---|---|
| 背景地図 | 淡色・標準（地理院 最適化ベクトルタイル）／写真（全国最新写真）／白図 を右下で切替 |
| テーマ | ライト・ダーク切替（ダークは背景スタイルの色を明度反転して生成） |
| 規制レイヤー | 13 種を個別に表示切替、全ON／全OFF、不透明度スライダー。その月に収録が無い種別は無効表示 |
| 重ね順 | 規制は背景の注記（地名・道路番号）より下に差し込むため、ラベルが隠れない |
| 属性表示 | クリックした地点に**当たったフィーチャをすべて**ポップアップに並べる（交差点では一時停止・停止線・信号機・横断歩道が重なる） |
| 画面の共有 | 位置・表示レイヤー・不透明度・背景地図を URL ハッシュに載せる（`#map=ズーム/緯度/経度&layers=oneway&opacity=0.6&base=photo`） |
| その他 | 現在地・全画面・スケール、PWA 対応、WebGL コンテキスト消失からの自動復帰 |

規制は Z9 以上で表示されます（低ズームでは密度が高く潰れるため）。タイルの収録も Z9〜Z14 です。

ズーム域・レイヤー定義・属性の表示名はビューワ側に書いていません。`data/pipeline.json`・`data/regulation_layers.json`・`data/attributes.json` をビルド時に読み込むので、パイプラインと必ず一致します。PMTiles の配信URLだけは実行時に `data/dataset.json` から読みます。

構成:

| ファイル | 役割 |
|---|---|
| `src/main.ts` | 配線だけ（状態の保持と、部品どうしのつなぎ） |
| `src/config.ts` | `data/` の設定JSONの読み口 |
| `src/dataset.ts` | `dataset.json` の型と読み込み |
| `src/regulation.ts` | PMTiles ソースと MapLibre レイヤーの生成 |
| `src/urlstate.ts` | URL ハッシュへの表示状態の出し入れ |
| `src/basemap.ts` / `src/theme.ts` | 背景地図とテーマ |
| `src/ui/*` | レイヤーパネル・ポップアップ・背景スイッチャー・収録データ表示 |

## 出典

- 交通規制情報: [公益財団法人 日本道路交通情報センター（JARTIC）](https://www.jartic.or.jp/service/opendata/)
- 背景地図: [国土地理院](https://maps.gsi.go.jp/development/ichiran.html)

## 関連

- [jartic-traffic-signal-cycle-converter](https://github.com/shiwaku/jartic-traffic-signal-cycle-converter) — 同じ JARTIC オープンデータの交差点制御情報（信号サイクル長）版
- [sapporo-micro-traffic-sim](https://github.com/shiwaku/sapporo-micro-traffic-sim) — このデータを入力に使うミクロ交通シミュレーション

## ライセンス

コードは Apache License 2.0（[LICENSE](LICENSE)）。データは含まれません。
