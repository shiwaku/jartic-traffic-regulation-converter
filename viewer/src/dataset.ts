/**
 * data/dataset.json の読み込み。
 *
 * 対象年月・件数・**PMTiles の配信URL** はここが単一の情報源。
 * 配信先（リポジトリ同梱か Cloudflare R2 か）はサイズで変わるが、
 * ビューワは `pmtiles_url` を読むだけなので、配布先が変わってもコードは触らない。
 */

export type Dataset = {
  target_month: string
  release_day: string
  year_month: string
  features_total: number
  rows_total: number
  n_prefectures: number
  anomalies_total: number
  pmtiles_mb: number
  pmtiles_in_repo: boolean
  /** ビューワが読む PMTiles。同梱ならリポジトリ相対、R2 なら不変の月次キー。 */
  pmtiles_url: string
  /** R2 配信時のみ。dataset.json を読まない利用者向けの「常に最新」の口。 */
  pmtiles_latest_url?: string
  /**
   * 実際に収録されたズーム域。設定ではなく「この配信物の事実」。
   * 古い dataset.json には無い、または一部しか無い。
   */
  tiles?: {
    min_zoom: number
    max_zoom: number
    max_tile_bytes: number
    n_layers?: number
    tippecanoe_version?: string
  }
  by_layer: Record<string, { label: string; n: number }>
}

/**
 * dataset.json は「どこからタイルを読むか」を持っているので、
 * これが無いと地図を組み立てられない。失敗は致命として扱う。
 */
export async function loadDataset(): Promise<Dataset> {
  let res: Response
  try {
    res = await fetch('data/dataset.json', { cache: 'no-store' })
  } catch (e) {
    throw new Error(
      'data/dataset.json を取得できませんでした（ネットワークに到達できていません）。\n' +
        `${e instanceof Error ? e.message : String(e)}`,
    )
  }
  if (!res.ok) {
    throw new Error(`data/dataset.json を取得できませんでした（HTTP ${res.status}）。`)
  }
  return (await res.json()) as Dataset
}
