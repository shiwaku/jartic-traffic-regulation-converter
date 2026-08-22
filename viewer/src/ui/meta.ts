import { MAX_ZOOM, MIN_ZOOM } from '../config'
import type { Dataset } from '../dataset'
import { $, esc } from './dom'

/** 収録データの要約。dataset.json の内容をそのまま見せる。 */
export function renderMeta(dataset: Dataset): void {
  const zoom = dataset.tiles
    ? `Z${dataset.tiles.min_zoom}〜Z${dataset.tiles.max_zoom}`
    : `Z${MIN_ZOOM}〜Z${MAX_ZOOM}`
  const rows: [string, string][] = [
    ['対象年月', dataset.target_month],
    ['公開日', `${dataset.release_day}（JARTIC）`],
    ['都道府県', `${dataset.n_prefectures} / 47`],
    ['レコード', dataset.rows_total.toLocaleString()],
    ['フィーチャ', dataset.features_total.toLocaleString()],
    ['形状異常', dataset.anomalies_total.toLocaleString()],
    ['収録ズーム', zoom],
    [
      'PMTiles',
      `${dataset.pmtiles_mb} MB（${dataset.pmtiles_in_repo ? '同梱' : 'R2 配信'}）`,
    ],
  ]
  $('meta').innerHTML = rows
    .map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`)
    .join('')
}

/** ズーム表示と、描画範囲外での注記。 */
export function renderZoom(zoom: number, tileMaxZoom: number): void {
  $('zoom-badge').textContent = `Z${zoom.toFixed(1)}`
  $('zoom-note').textContent =
    zoom < MIN_ZOOM
      ? `規制は Z${MIN_ZOOM} 以上で表示されます（低ズームでは密度が高く潰れるため）`
      : zoom > tileMaxZoom + 0.5
        ? `タイルの最大ZL（Z${tileMaxZoom}）を超えています。引き伸ばし表示です`
        : `規制の収録範囲は Z${MIN_ZOOM}–Z${tileMaxZoom}`
}
