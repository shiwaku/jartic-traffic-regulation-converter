import maplibregl from 'maplibre-gl'
import { Protocol } from 'pmtiles'
import 'maplibre-gl/dist/maplibre-gl.css'

import { getBasemapStyle, type Basemap } from './basemap'
import { JAPAN_BOUNDS, LAYERS, MAX_ZOOM } from './config'
import { loadDataset } from './dataset'
import {
  BASE_OPACITY,
  buildLayers,
  idsOf,
  nameOf,
  OPACITY_PROP,
  regulationSource,
  SOURCE_ID,
} from './regulation'
import { applyThemeAttr, initialTheme, type Theme } from './theme'
import { BasemapControl } from './ui/basemapControl'
import { $, fatal } from './ui/dom'
import { initLayerPanel } from './ui/layerPanel'
import { renderMeta, renderZoom } from './ui/meta'
import { showFeaturePopup } from './ui/popup'
import { MAP_HASH_KEY, readState, writeState } from './urlstate'
import './style.css'

/**
 * 画面の組み立て。ここは配線だけを持ち、
 * 設定は config.ts、データは dataset.ts、部品は ui/ に置く。
 */

// ---- データ読み込み --------------------------------------------------------
// dataset.json が PMTiles の配信URLの情報源なので、地図を作る前に解決する。

const dataset = await loadDataset().catch((e: unknown) => {
  const msg = e instanceof Error ? e.message : String(e)
  fatal(
    `${msg}\n\nPMTiles の配信先はここに記録されているため、これが無いと地図を組み立てられません。`,
  )
  throw e
})

// 背景の最適化ベクトルタイルも PMTiles 配信なので、常に登録する。
maplibregl.addProtocol('pmtiles', new Protocol().tile)

// ---- 表示状態 --------------------------------------------------------------
// 位置は MapLibre が hash の map= に、表示レイヤー・不透明度・背景は urlstate が
// 同じ hash の別キーに書く。テーマだけは端末の好みなので localStorage。

const saved = readState()
let theme: Theme = initialTheme()
let base: Basemap = saved.base ?? 'pale'
let regOpacity = saved.opacity ?? 1
const visible = new Set(
  saved.layers ??
    Object.keys(LAYERS).filter((name) => (dataset.by_layer[name]?.n ?? 0) > 0),
)
applyThemeAttr(theme)

const isMobile = window.matchMedia('(max-width: 640px)').matches
const tileMaxZoom = dataset.tiles?.max_zoom ?? MAX_ZOOM

const persist = (): void => writeState({ layers: visible, opacity: regOpacity, base })

// ---- 地図 ------------------------------------------------------------------

const map = new maplibregl.Map({
  container: 'map',
  style: await getBasemapStyle(base, theme),
  center: [139.7, 35.68],
  zoom: 10,
  minZoom: 4,
  // タイルの最大 ZL を超えても、位置合わせのため少し寄れるようにする
  maxZoom: tileMaxZoom + 4,
  maxPitch: 85,
  // 位置を URL の #map=ズーム/緯度/経度 に反映（共有・リロード時の位置維持）。
  // キー名を付けることで、表示レイヤーなど別のパラメータと共存できる。
  hash: MAP_HASH_KEY,
  attributionControl: false,
  // モバイルはGPU/メモリが限られるため保持タイル数と描画解像度を絞る。
  // 逼迫すると WebGL コンテキストが失われ地図がまるごと消えるため、その圧を下げる。
  maxTileCacheSize: isMobile ? 24 : undefined,
  pixelRatio: isMobile ? Math.min(window.devicePixelRatio || 1, 2) : undefined,
})

map.addControl(
  new maplibregl.NavigationControl({ showCompass: true, visualizePitch: true }),
  'top-right',
)
map.addControl(
  new maplibregl.GeolocateControl({
    positionOptions: { enableHighAccuracy: false },
    fitBoundsOptions: { maxZoom: 17 },
    trackUserLocation: true,
    showUserLocation: true,
  }),
  'top-right',
)
map.addControl(new maplibregl.FullscreenControl(), 'top-right')
map.addControl(new maplibregl.ScaleControl({ maxWidth: 200, unit: 'metric' }), 'bottom-left')
map.addControl(new maplibregl.AttributionControl({ compact: true }))

// 規制ソースが読めないと地図に何も出ない。理由を画面に出す（起動時の HEAD 確認は
// 往復が増えるだけで、途中で配信が止まった場合を捕まえられないのでやらない）。
let reportedSourceError = false
map.on('error', (e) => {
  const sourceId = (e as unknown as { sourceId?: string }).sourceId
  if (sourceId !== SOURCE_ID || reportedSourceError) return
  reportedSourceError = true
  fatal(
    `PMTiles を取得できませんでした。\n${dataset.pmtiles_url}\n\n` +
      '配信元が停止しているか、ネットワークに到達できていません。',
  )
})

// ---- 規制レイヤーの投入 ----------------------------------------------------
// 背景スタイルを差し替えると全レイヤーが消えるため、切替のたびに貼り直す。

/**
 * 背景の注記（地名・道路番号）より下に差し込むためのアンカーを探す。
 * 最適化ベクトルタイルは line/fill が並んだ後ろに注記の symbol 群が来る構成なので、
 * 「最後の line/fill より後ろにある最初の symbol」を境目とする。
 * 写真・白図には symbol が無いので undefined（＝最前面）になる。
 */
function labelAnchor(): string | undefined {
  const layers = map.getStyle().layers
  let lastShape = -1
  for (let i = 0; i < layers.length; i++) {
    const t = layers[i].type
    if (t === 'line' || t === 'fill') lastShape = i
  }
  for (let i = lastShape + 1; i < layers.length; i++) {
    if (layers[i].type === 'symbol') return layers[i].id
  }
  return undefined
}

/** クリック判定とスライダー操作の対象になる、投入済みレイヤー ID。 */
const activeIds: string[] = []

function addRegulationLayers(): void {
  if (!map.getSource(SOURCE_ID)) map.addSource(SOURCE_ID, regulationSource(dataset))

  const before = labelAnchor()
  activeIds.length = 0

  for (const { id, spec } of buildLayers()) {
    const name = nameOf(id)
    if (!map.getLayer(id)) {
      map.addLayer(
        {
          id,
          source: SOURCE_ID,
          ...spec,
          layout: { ...(spec.layout ?? {}), visibility: visible.has(name) ? 'visible' : 'none' },
          paint: {
            ...spec.paint,
            [OPACITY_PROP[spec.type]]: BASE_OPACITY[spec.type] * regOpacity,
          },
        } as unknown as maplibregl.LayerSpecification,
        before,
      )
    }
    activeIds.push(id)
  }
}

// 写真（ラスタ）と白図（sources なし）を往復すると diff 適用が破綻するため
// diff:false で作り直す。setStyle 直後は isStyleLoaded() が旧スタイルで true を
// 返して競合するので、idle を待ってから貼り直す。
async function reloadStyle(): Promise<void> {
  map.setStyle(await getBasemapStyle(base, theme), { diff: false })
  map.once('idle', addRegulationLayers)
}

// ---- テーマ切替 ------------------------------------------------------------
const themeBtn = $<HTMLButtonElement>('theme-btn')
const renderThemeBtn = (): void => {
  themeBtn.textContent = theme === 'dark' ? '☀️' : '🌙'
}
themeBtn.addEventListener('click', () => {
  theme = theme === 'dark' ? 'light' : 'dark'
  applyThemeAttr(theme)
  renderThemeBtn()
  void reloadStyle()
})

// ---- パネル開閉 ------------------------------------------------------------
const panel = $('panel')
const collapseBtn = $<HTMLButtonElement>('collapse-btn')
const renderCollapseBtn = (): void => {
  collapseBtn.textContent = panel.classList.contains('collapsed') ? '▾' : '▴'
}
collapseBtn.addEventListener('click', () => {
  panel.classList.toggle('collapsed')
  renderCollapseBtn()
})

// ---- レイヤー・不透明度 ----------------------------------------------------

function applyVisibility(): void {
  for (const name of Object.keys(LAYERS)) {
    const on = visible.has(name)
    for (const id of idsOf(name)) {
      if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', on ? 'visible' : 'none')
    }
  }
}

function applyOpacity(): void {
  for (const id of activeIds) {
    const layer = map.getLayer(id)
    if (!layer) continue
    const prop = OPACITY_PROP[layer.type]
    if (prop) map.setPaintProperty(id, prop, BASE_OPACITY[layer.type] * regOpacity)
  }
}

initLayerPanel(dataset, visible, regOpacity, {
  onVisibleChange: (next) => {
    visible.clear()
    for (const n of next) visible.add(n)
    applyVisibility()
    persist()
  },
  onOpacityChange: (v) => {
    regOpacity = v
    applyOpacity()
    persist()
  },
  onFit: () => map.fitBounds(JAPAN_BOUNDS, { padding: 24 }),
})

// ---- 背景地図スイッチャー（右下） ------------------------------------------
const basemapCtrl = new BasemapControl(
  () => base,
  (next) => {
    if (next === base) return
    base = next
    basemapCtrl.sync()
    persist()
    void reloadStyle()
  },
)
map.addControl(basemapCtrl, 'bottom-right')

// ---- ズームレベル表示 ------------------------------------------------------
map.on('zoom', () => renderZoom(map.getZoom(), tileMaxZoom))

// ---- クリックで属性表示 ----------------------------------------------------

const hitLayers = (): string[] => activeIds.filter((id) => map.getLayer(id))

map.on('click', (e) => {
  const ids = hitLayers()
  if (!ids.length) return
  showFeaturePopup(map, e.lngLat, map.queryRenderedFeatures(e.point, { layers: ids }))
})

// レイヤーは背景切替のたびに貼り直されるため、レイヤー指定の mouseenter ではなく
// 地図全体の mousemove で判定する（登録が古いレイヤーに残らないようにする）。
// 13レイヤーへの当たり判定を毎イベント走らせると重いので、フレームに1回に間引く。
let hoverQueued = false
map.on('mousemove', (e) => {
  if (hoverQueued) return
  hoverQueued = true
  requestAnimationFrame(() => {
    hoverQueued = false
    const ids = hitLayers()
    const hit = ids.length > 0 && map.queryRenderedFeatures(e.point, { layers: ids }).length > 0
    map.getCanvas().style.cursor = hit ? 'pointer' : ''
  })
})

// ---- 初期化 ----------------------------------------------------------------
$('subtitle').textContent = dataset.target_month
$('build-ver').textContent = `build: ${__BUILD_TIME__}`
renderThemeBtn()
renderMeta(dataset)
renderZoom(map.getZoom(), tileMaxZoom)
if (isMobile) panel.classList.add('collapsed')
renderCollapseBtn()
persist()

map.on('load', addRegulationLayers)

// WebGL コンテキスト消失からの復帰。iOS Safari 等ではメモリ逼迫時に GL コンテキストが
// 失われ、レイヤーがまるごと消えて戻らないことがある。復帰時に貼り直して自動回復する。
const canvas = map.getCanvas()
canvas.addEventListener(
  'webglcontextlost',
  (ev) => {
    // preventDefault しないと自動復帰イベントが発火しない
    ev.preventDefault()
  },
  false,
)
canvas.addEventListener(
  'webglcontextrestored',
  () => {
    if (map.isStyleLoaded()) addRegulationLayers()
    else map.once('idle', addRegulationLayers)
  },
  false,
)

// デバッグ/外部連携用にマップを公開
;(window as unknown as { __map: maplibregl.Map }).__map = map

// PWA: Service Worker 登録（本番のみ。dev では HMR を妨げないよう無効）
if (import.meta.env.PROD && 'serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register(`${import.meta.env.BASE_URL}sw.js`).catch(() => {})
  })
  let refreshing = false
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    if (refreshing) return
    refreshing = true
    window.location.reload()
  })
}
