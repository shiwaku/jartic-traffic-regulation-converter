import type { ExpressionSpecification, VectorSourceSpecification } from 'maplibre-gl'
import layerDef from '../../data/regulation_layers.json'

/**
 * 交通規制情報の PMTiles と、規制種別ごとのレイヤー定義。
 *
 * PMTiles の置き場所は 2 通りある（`src/run_pipeline.py` がサイズで切り替える）。
 *   90MB 以下 … data/regulation.pmtiles としてリポジトリ同梱（同一オリジン）
 *   90MB 超  … Cloudflare R2 へ固定パスで公開
 * どちらにあるかは HEAD で確かめる。GitHub Release は CORS ヘッダーを返さず
 * ブラウザから Range で読めないため使わない。
 */

export const SOURCE_ID = 'reg'

const PMTILES_LOCAL = 'data/regulation.pmtiles'
const PMTILES_R2 =
  'https://shi-works.com/pmtiles/jartic-traffic-regulation-converter/regulation.pmtiles'

/** 全国分のデータなので、初期表示・全体表示はこの範囲に合わせる。 */
export const JAPAN_BOUNDS: [number, number, number, number] = [122, 20, 154, 46]

/** 低ズームでは密度が高すぎて潰れるため、ここから下は描かない。 */
export const MIN_ZOOM = 9
/** タイルの最大ズーム。これを超えると引き伸ばし表示になる。 */
export const MAX_ZOOM = 14

/** 点で表現される規制。線・面レイヤーより前面に積む。 */
const POINT_LAYERS = new Set(['stop', 'stopline', 'signal', 'crosswalk', 'turn_restrict'])

export type LayerSpec = { label: string; codes: string[]; color: string }

export const LAYERS = (layerDef as { layers: Record<string, LayerSpec> }).layers

export type Dataset = {
  target_month: string
  release_day: string
  features_total: number
  rows_total: number
  n_prefectures: number
  anomalies_total: number
  pmtiles_mb: number
  pmtiles_in_repo: boolean
  by_layer: Record<string, { label: string; n: number }>
}

export type Regulation = {
  source: VectorSourceSpecification
  /** PMTiles を同梱から読めたか（false なら R2 配信）。 */
  isLocal: boolean
  dataset: Dataset | null
}

async function exists(url: string): Promise<boolean> {
  try {
    const r = await fetch(url, { method: 'HEAD' })
    return r.ok
  } catch {
    return false
  }
}

async function loadDataset(): Promise<Dataset | null> {
  try {
    const r = await fetch('data/dataset.json', { cache: 'no-store' })
    return r.ok ? ((await r.json()) as Dataset) : null
  } catch {
    return null
  }
}

export async function loadRegulation(): Promise<Regulation> {
  const isLocal = await exists(PMTILES_LOCAL)
  const url = isLocal ? PMTILES_LOCAL : PMTILES_R2

  // ソースが読めないと地図に何も出ない。ここで弾いて理由を出す。
  if (!isLocal && !(await exists(PMTILES_R2))) {
    throw new Error(
      `PMTiles を取得できませんでした。\n${PMTILES_R2}\n\n` +
        '配信元が停止しているか、ネットワークに到達できていません。',
    )
  }

  return {
    source: {
      type: 'vector',
      url: `pmtiles://${url}`,
      attribution:
        '<a href="https://www.jartic.or.jp/service/opendata/" target="_blank" rel="noopener">JARTIC 交通規制情報</a>',
    },
    isLocal,
    dataset: await loadDataset(),
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

export type LayerIds = { name: string; ids: string[] }

/** レイヤー名から、そのレイヤーを構成する MapLibre レイヤー ID を返す。 */
export function idsOf(name: string): string[] {
  return POINT_LAYERS.has(name) ? [`${name}-point`] : [`${name}-line`, `${name}-fill`]
}

/**
 * 面 → 線 → 点 の順に積む（点が最前面）。
 * `before` を渡すと、そのレイヤーの下に差し込む（背景の注記を隠さないため）。
 */
export function buildLayers(): { id: string; spec: LayerSpecInput }[] {
  const out: { id: string; spec: LayerSpecInput }[] = []

  for (const [name, spec] of Object.entries(LAYERS)) {
    if (POINT_LAYERS.has(name)) continue
    out.push({
      id: `${name}-fill`,
      spec: {
        type: 'fill',
        'source-layer': name,
        filter: ['==', ['geometry-type'], 'Polygon'],
        paint: { 'fill-color': spec.color, 'fill-opacity': 0.14 },
      },
    })
    out.push({
      id: `${name}-line`,
      spec: {
        type: 'line',
        'source-layer': name,
        layout: { 'line-cap': 'round' },
        paint: { 'line-color': spec.color, 'line-width': lineWidth, 'line-opacity': 0.9 },
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
        paint: {
          'circle-color': spec.color,
          'circle-radius': circleRadius,
          'circle-opacity': 0.85,
          'circle-stroke-width': ['interpolate', ['linear'], ['zoom'], 13, 0, 15, 0.6],
          'circle-stroke-color': '#fff',
        },
      },
    })
  }

  return out
}

type LayerSpecInput = {
  type: 'fill' | 'line' | 'circle'
  'source-layer': string
  filter?: unknown
  layout?: Record<string, unknown>
  paint: Record<string, unknown>
}

/** 不透明度スライダーが動かす paint プロパティ（レイヤー種別ごとに違う）。 */
export const OPACITY_PROP: Record<string, string> = {
  fill: 'fill-opacity',
  line: 'line-opacity',
  circle: 'circle-opacity',
}

/** 各レイヤー種別の基準不透明度。スライダー値はこれに掛ける。 */
export const BASE_OPACITY: Record<string, number> = {
  fill: 0.14,
  line: 0.9,
  circle: 0.85,
}
