import type { ExpressionSpecification, VectorSourceSpecification } from 'maplibre-gl'

import { ICON_MIN_ZOOM, LAYERS, MIN_ZOOM, POINT_LAYERS, SPRITE_ID } from './config'
import type { Dataset } from './dataset'

/**
 * 交通規制情報の PMTiles ソースと、規制種別ごとの MapLibre レイヤー。
 *
 * PMTiles の置き場所は 2 通り（`src/run_pipeline.py` がサイズで切り替える）。
 *   90MB 以下 … data/regulation.pmtiles としてリポジトリ同梱（同一オリジン）
 *   90MB 超  … Cloudflare R2 の月次キー（不変）
 * どちらであれ URL は dataset.json の `pmtiles_url` に入るので、ここでは持たない。
 * GitHub Release は CORS ヘッダーを返さずブラウザから Range で読めないため使わない。
 */

export const SOURCE_ID = 'reg'

export function regulationSource(dataset: Dataset): VectorSourceSpecification {
  return {
    type: 'vector',
    url: `pmtiles://${dataset.pmtiles_url}`,
    attribution:
      '<a href="https://www.jartic.or.jp/service/opendata/" target="_blank" rel="noopener">JARTIC 交通規制情報</a>',
  }
}

// ---- レイヤー生成 ----------------------------------------------------------

const lineWidth: ExpressionSpecification = [
  'interpolate', ['linear'], ['zoom'],
  9, 0.8,
  13, 1.8,
  16, 3.4,
]

const circleRadius: ExpressionSpecification = [
  'interpolate', ['linear'], ['zoom'],
  9, 1.6,
  13, 3.2,
  16, 6,
]

/** アイコンは 64px で作ってあるので、地図では 20〜27px になるよう縮める。 */
const iconSize: ExpressionSpecification = [
  'interpolate', ['linear'], ['zoom'],
  13, 0.3,
  16, 0.42,
]

/** 各レイヤー種別の基準不透明度。スライダー値はこれに掛ける。 */
export const BASE_OPACITY: Record<string, number> = {
  fill: 0.14,
  line: 0.9,
  circle: 0.85,
  symbol: 1,
}

/** 不透明度スライダーが動かす paint プロパティ（レイヤー種別ごとに違う）。 */
export const OPACITY_PROP: Record<string, string> = {
  fill: 'fill-opacity',
  line: 'line-opacity',
  circle: 'circle-opacity',
  symbol: 'icon-opacity',
}

export type LayerSpecInput = {
  type: 'fill' | 'line' | 'circle' | 'symbol'
  'source-layer': string
  minzoom: number
  maxzoom?: number
  filter?: unknown
  layout?: Record<string, unknown>
  paint: Record<string, unknown>
}

/** レイヤー名から、そのレイヤーを構成する MapLibre レイヤー ID を返す。 */
export function idsOf(name: string): string[] {
  const shape = POINT_LAYERS.has(name) ? [`${name}-point`] : [`${name}-line`, `${name}-fill`]
  return [...shape, `${name}-icon`]
}

/** MapLibre レイヤー ID から、もとの規制レイヤー名を返す。 */
export function nameOf(id: string): string {
  return id.replace(/-(fill|line|point|icon)$/, '')
}

/** 面 → 線 → 点 の順に積む（点が最前面）。 */
export function buildLayers(): { id: string; spec: LayerSpecInput }[] {
  const out: { id: string; spec: LayerSpecInput }[] = []

  for (const [name, spec] of Object.entries(LAYERS)) {
    if (POINT_LAYERS.has(name)) continue
    out.push({
      id: `${name}-fill`,
      spec: {
        type: 'fill',
        'source-layer': name,
        minzoom: MIN_ZOOM,
        filter: ['==', ['geometry-type'], 'Polygon'],
        paint: { 'fill-color': spec.color, 'fill-opacity': BASE_OPACITY.fill },
      },
    })
    out.push({
      id: `${name}-line`,
      spec: {
        type: 'line',
        'source-layer': name,
        minzoom: MIN_ZOOM,
        layout: { 'line-cap': 'round' },
        paint: {
          'line-color': spec.color,
          'line-width': lineWidth,
          'line-opacity': BASE_OPACITY.line,
        },
      },
    })
  }

  for (const [name, spec] of Object.entries(LAYERS)) {
    if (!POINT_LAYERS.has(name)) continue
    out.push({
      id: `${name}-point`,
      spec: {
        type: 'circle',
        'source-layer': name,
        minzoom: MIN_ZOOM,
        // アイコンが出るズームからは丸を消す（同じ位置に二重に描かない）
        maxzoom: ICON_MIN_ZOOM,
        paint: {
          'circle-color': spec.color,
          'circle-radius': circleRadius,
          'circle-opacity': BASE_OPACITY.circle,
          'circle-stroke-width': ['interpolate', ['linear'], ['zoom'], 13, 0, 15, 0.6],
          'circle-stroke-color': '#fff',
        },
      },
    })
  }

  // 規制種別ごとのアイコン。スプライトのアイコン名は共通規制種別コードそのものなので、
  // 属性 code から直に引ける。密度が高いので衝突判定に任せて間引く
  // （icon-allow-overlap は付けない）。
  for (const name of Object.keys(LAYERS)) {
    out.push({
      id: `${name}-icon`,
      spec: {
        type: 'symbol',
        'source-layer': name,
        minzoom: ICON_MIN_ZOOM,
        layout: {
          // スプライトのアイコン名は共通規制種別コードそのもの。
          // スプライトに無いコードは何も描かれない（地図は壊れない）。
          'icon-image': ['concat', `${SPRITE_ID}:`, ['get', 'code']],
          'icon-size': iconSize,
        },
        paint: { 'icon-opacity': BASE_OPACITY.symbol },
      },
    })
  }

  return out
}
