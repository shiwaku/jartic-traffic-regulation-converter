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

/**
 * 低ズームの点は**発光**で描く。ぼかした大きい円で光をにじませ、その内側に
 * もう一枚、芯に小さくて硬い白を置く（3層）。手法は
 * [jma-liden-tile-pipeline](https://github.com/shiwaku/jma-liden-tile-pipeline)
 * のビューワに倣っている。`circle-blur` は 1 を超えてよい。
 *
 * 芯を白にすると「光っている」ように見えるが、種別の色は外側2層に載る。
 * **半径を上げすぎると暈が融合して密集部が塊になる**（一時停止は152万件ある）。
 * 控えめな値にしてある。
 */
const GLOW_STACK: {
  suffix: string
  radius: ExpressionSpecification
  blur: number
  base: number
  white: boolean
  pick: boolean
}[] = [
  {
    suffix: 'glow',
    radius: ['interpolate', ['linear'], ['zoom'], 9, 4.5, 11, 7, 13, 11],
    blur: 2.2, base: 0.35, white: false, pick: true,
  },
  {
    suffix: 'mid',
    radius: ['interpolate', ['linear'], ['zoom'], 9, 2.4, 11, 3.8, 13, 5.6],
    blur: 1.2, base: 0.6, white: false, pick: false,
  },
  {
    suffix: 'point',
    radius: ['interpolate', ['linear'], ['zoom'], 9, 1.1, 11, 1.8, 13, 2.6],
    blur: 0, base: 1, white: true, pick: false,
  },
]

/** アイコンは 64px で作ってあるので、地図では 20〜27px になるよう縮める。 */
const iconSize: ExpressionSpecification = [
  'interpolate', ['linear'], ['zoom'],
  13, 0.3,
  16, 0.42,
]

/** 各レイヤー種別の基準不透明度。発光の3層はここではなく GLOW_STACK が持つ。 */
const BASE = { fill: 0.14, line: 0.9, symbol: 1 }

/** 不透明度スライダーが動かす paint プロパティ（レイヤー種別ごとに違う）。 */
const OPACITY_PROP: Record<string, string> = {
  fill: 'fill-opacity',
  line: 'line-opacity',
  circle: 'circle-opacity',
  symbol: 'icon-opacity',
}

/**
 * 組み立てたレイヤー1枚。
 * `opacity` は不透明度スライダーが動かす対象、`pick` はクリック判定に使うか。
 * 発光は同じフィーチャを3枚重ねるので、拾うのは1枚だけにする（重複を出さない）。
 */
export type BuiltLayer = {
  id: string
  spec: LayerSpecInput
  opacity: { prop: string; base: number }
  pick: boolean
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
  const shape = POINT_LAYERS.has(name)
    ? GLOW_STACK.map((g) => `${name}-${g.suffix}`)
    : [`${name}-line`, `${name}-fill`]
  return [...shape, `${name}-icon`]
}

/** MapLibre レイヤー ID から、もとの規制レイヤー名を返す。 */
export function nameOf(id: string): string {
  return id.replace(/-(fill|line|point|icon|glow|mid)$/, '')
}

/**
 * 面 → 線 → 発光の点 → アイコン の順に積む（後のものが前面）。
 * 点は Z13 でアイコンに切り替わるので、そこで消す（同じ位置に二重に描かない）。
 */
export function buildLayers(): BuiltLayer[] {
  const out: BuiltLayer[] = []

  for (const [name, spec] of Object.entries(LAYERS)) {
    if (POINT_LAYERS.has(name)) continue
    out.push({
      id: `${name}-fill`,
      opacity: { prop: OPACITY_PROP.fill, base: BASE.fill },
      pick: true,
      spec: {
        type: 'fill',
        'source-layer': name,
        minzoom: MIN_ZOOM,
        filter: ['==', ['geometry-type'], 'Polygon'],
        paint: { 'fill-color': spec.color, 'fill-opacity': BASE.fill },
      },
    })
    out.push({
      id: `${name}-line`,
      opacity: { prop: OPACITY_PROP.line, base: BASE.line },
      pick: true,
      spec: {
        type: 'line',
        'source-layer': name,
        minzoom: MIN_ZOOM,
        layout: { 'line-cap': 'round' },
        paint: {
          'line-color': spec.color,
          'line-width': lineWidth,
          'line-opacity': BASE.line,
        },
      },
    })
  }

  for (const [name, spec] of Object.entries(LAYERS)) {
    if (!POINT_LAYERS.has(name)) continue
    for (const g of GLOW_STACK) {
      out.push({
        id: `${name}-${g.suffix}`,
        opacity: { prop: OPACITY_PROP.circle, base: g.base },
        pick: g.pick,
        spec: {
          type: 'circle',
          'source-layer': name,
          minzoom: MIN_ZOOM,
          maxzoom: ICON_MIN_ZOOM,
          paint: {
            'circle-color': g.white ? '#ffffff' : spec.color,
            'circle-radius': g.radius,
            'circle-blur': g.blur,
            'circle-opacity': g.base,
          },
        },
      })
    }
  }

  // 規制種別ごとのアイコン。スプライトのアイコン名は共通規制種別コードそのものなので、
  // 属性 code から直に引ける。密度が高いので衝突判定に任せて間引く
  // （icon-allow-overlap は付けない）。
  for (const name of Object.keys(LAYERS)) {
    out.push({
      id: `${name}-icon`,
      opacity: { prop: OPACITY_PROP.symbol, base: BASE.symbol },
      pick: true,
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
        paint: { 'icon-opacity': BASE.symbol },
      },
    })
  }

  return out
}
