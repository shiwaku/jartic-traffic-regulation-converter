import maplibregl from 'maplibre-gl'
import { Protocol } from 'pmtiles'
import 'maplibre-gl/dist/maplibre-gl.css'

import { BASEMAPS, getBasemapStyle, type Basemap } from './basemap'
import {
  BASE_OPACITY,
  buildLayers,
  idsOf,
  JAPAN_BOUNDS,
  LAYERS,
  loadRegulation,
  MAX_ZOOM,
  MIN_ZOOM,
  OPACITY_PROP,
  SOURCE_ID,
  type Regulation,
} from './regulation'
import { applyThemeAttr, initialTheme, type Theme } from './theme'
import './style.css'

let theme: Theme = initialTheme()
let base: Basemap = 'pale'
applyThemeAttr(theme)

const isMobile = window.matchMedia('(max-width: 640px)').matches

const $ = <T extends HTMLElement>(id: string): T => document.getElementById(id) as T

// ---- データ読み込み --------------------------------------------------------
// PMTiles の所在が決まらないと地図に何も出ないため、地図を作る前に解決する。

let reg: Regulation
try {
  reg = await loadRegulation()
} catch (e) {
  const el = $('error')
  el.hidden = false
  el.textContent = e instanceof Error ? e.message : String(e)
  throw e
}

// 背景の最適化ベクトルタイルも PMTiles 配信なので、常に登録する。
maplibregl.addProtocol('pmtiles', new Protocol().tile)

const ds = reg.dataset
/** 表示中のレイヤー名。 */
const visible = new Set(Object.keys(LAYERS))
let regOpacity = 1

// ---- 地図 ------------------------------------------------------------------

const map = new maplibregl.Map({
  container: 'map',
  style: await getBasemapStyle(base, theme),
  center: [139.7, 35.68],
  zoom: 10,
  minZoom: 4,
  // タイルの最大 ZL を超えても、位置合わせのため少し寄れるようにする
  maxZoom: MAX_ZOOM + 4,
  maxPitch: 85,
  // 地図位置を URL の #ズーム/緯度/経度 に反映（共有・リロード時の位置維持）
  hash: true,
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
  if (!map.getSource(SOURCE_ID)) map.addSource(SOURCE_ID, reg.source)

  const before = labelAnchor()
  activeIds.length = 0

  for (const { id, spec } of buildLayers()) {
    const name = id.replace(/-(fill|line|point)$/, '')
    if (!map.getLayer(id)) {
      map.addLayer(
        {
          id,
          source: SOURCE_ID,
          minzoom: MIN_ZOOM,
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

// ---- レイヤー一覧 ----------------------------------------------------------

function setVisible(name: string, on: boolean): void {
  if (on) visible.add(name)
  else visible.delete(name)
  for (const id of idsOf(name)) {
    if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', on ? 'visible' : 'none')
  }
}

function buildLayerList(): void {
  const host = $('layers')
  host.innerHTML = ''
  for (const [name, spec] of Object.entries(LAYERS)) {
    const n = ds?.by_layer?.[name]?.n
    const row = document.createElement('label')
    row.className = 'reg-item'
    row.innerHTML =
      `<input type="checkbox" checked data-layer="${name}" />` +
      `<span class="chip" style="--chip:${spec.color}"></span>` +
      `<span class="reg-label">${spec.label}</span>` +
      `<span class="reg-n">${n != null ? n.toLocaleString() : ''}</span>`
    host.append(row)
  }
  host.querySelectorAll<HTMLInputElement>('input[data-layer]').forEach((el) => {
    el.addEventListener('change', () => setVisible(el.dataset.layer!, el.checked))
  })

  const setAll = (on: boolean): void => {
    host.querySelectorAll<HTMLInputElement>('input[data-layer]').forEach((el) => {
      el.checked = on
      setVisible(el.dataset.layer!, on)
    })
  }
  $<HTMLButtonElement>('all-on').addEventListener('click', () => setAll(true))
  $<HTMLButtonElement>('all-off').addEventListener('click', () => setAll(false))
}

// ---- 不透明度 --------------------------------------------------------------
const opacityRange = $<HTMLInputElement>('opacity-range')
const opacityVal = $('opacity-val')
opacityRange.addEventListener('input', () => {
  regOpacity = Number(opacityRange.value)
  opacityVal.textContent = `${Math.round(regOpacity * 100)}%`
  for (const id of activeIds) {
    const layer = map.getLayer(id)
    if (!layer) continue
    const prop = OPACITY_PROP[layer.type]
    if (prop) map.setPaintProperty(id, prop, BASE_OPACITY[layer.type] * regOpacity)
  }
})

// ---- 全国表示 --------------------------------------------------------------
$<HTMLButtonElement>('fit-btn').addEventListener('click', () =>
  map.fitBounds(JAPAN_BOUNDS, { padding: 24 }),
)

// ---- 背景地図スイッチャー（右下） ------------------------------------------
class BasemapControl implements maplibregl.IControl {
  private el!: HTMLElement
  onAdd(): HTMLElement {
    this.el = document.createElement('div')
    this.el.className = 'maplibregl-ctrl basemap-switch'
    for (const { key, label } of BASEMAPS) {
      const btn = document.createElement('button')
      btn.type = 'button'
      btn.textContent = label
      btn.dataset.base = key
      btn.setAttribute('aria-selected', String(key === base))
      btn.addEventListener('click', () => setBase(key))
      this.el.append(btn)
    }
    return this.el
  }
  onRemove(): void {
    this.el.remove()
  }
  sync(): void {
    for (const btn of this.el.querySelectorAll<HTMLButtonElement>('button')) {
      btn.setAttribute('aria-selected', String(btn.dataset.base === base))
    }
  }
}
const basemapCtrl = new BasemapControl()
map.addControl(basemapCtrl, 'bottom-right')

function setBase(next: Basemap): void {
  if (next === base) return
  base = next
  basemapCtrl.sync()
  void reloadStyle()
}

// ---- ズームレベル表示 ------------------------------------------------------
const zoomBadge = $('zoom-badge')
const zoomNote = $('zoom-note')
const renderZoom = (): void => {
  const z = map.getZoom()
  zoomBadge.textContent = `Z${z.toFixed(1)}`
  zoomNote.textContent =
    z < MIN_ZOOM
      ? `規制は Z${MIN_ZOOM} 以上で表示されます（低ズームでは密度が高く潰れるため）`
      : z > MAX_ZOOM + 0.5
        ? `タイルの最大ZL（Z${MAX_ZOOM}）を超えています。引き伸ばし表示です`
        : `規制の収録範囲は Z${MIN_ZOOM}–Z${MAX_ZOOM}`
}
map.on('zoom', renderZoom)

// ---- クリックで属性表示 ----------------------------------------------------

const PROP_LABEL: Record<string, string> = {
  kind: '規制種別',
  code: '共通規制種別コード',
  shape_name: '規制形態',
  pref: '都道府県コード',
  police: '警察署コード',
  route: '路線名',
  crossing: '交差点名称',
  road_type: '道路種別',
  speed: '速度',
  zone30: 'ゾーン30',
  n_lanes: '車両通行帯数',
  length: '距離・延長',
  area: '面積',
  side: '片側・両側',
  n_stoplines: '停止線本数',
  has_signal: '信号の有無',
  dir_kind: '指定・禁止方向の別',
  dir_in: '進入方向',
  dir_deny: '禁止する方向',
  dir_allow: '指定する方向',
  t1_from: '規制時間 開始',
  t1_to: '規制時間 終了',
  dow1: '規制曜日',
  veh1: '対象車両',
  reason: '規制理由',
  updated: 'データ更新日',
  uid: 'ユニークキー',
}

/** 属性値は元データ由来なので、そのまま innerHTML に入れない。 */
const esc = (s: string): string => s.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`)

const hitLayers = (): string[] => activeIds.filter((id) => map.getLayer(id))

map.on('click', (e) => {
  const ids = hitLayers()
  if (!ids.length) return
  const hits = map.queryRenderedFeatures(e.point, { layers: ids })
  if (!hits.length) return
  const p = hits[0].properties as Record<string, unknown>
  const rows = Object.entries(PROP_LABEL)
    .filter(([k]) => p[k] !== undefined && p[k] !== '')
    .map(([k, label]) => `<dt>${label}</dt><dd>${esc(String(p[k]))}</dd>`)
    .join('')
  new maplibregl.Popup({ maxWidth: '320px' })
    .setLngLat(e.lngLat)
    .setHTML(
      `<p class="popup-title">${esc(String(p.kind ?? '規制'))}</p>` +
        `<dl class="popup-kv">${rows}</dl>`,
    )
    .addTo(map)
})

// レイヤーは背景切替のたびに貼り直されるため、レイヤー指定の mouseenter ではなく
// 地図全体の mousemove で判定する（登録が古いレイヤーに残らないようにする）。
map.on('mousemove', (e) => {
  const ids = hitLayers()
  const hit = ids.length > 0 && map.queryRenderedFeatures(e.point, { layers: ids }).length > 0
  map.getCanvas().style.cursor = hit ? 'pointer' : ''
})

// ---- データ情報 ------------------------------------------------------------
function renderMeta(): void {
  if (!ds) {
    $('meta').innerHTML = '<dt>状態</dt><dd>dataset.json 未生成</dd>'
    return
  }
  const rows: [string, string][] = [
    ['対象年月', ds.target_month],
    ['公開日', `${ds.release_day}（JARTIC）`],
    ['都道府県', `${ds.n_prefectures} / 47`],
    ['レコード', ds.rows_total.toLocaleString()],
    ['フィーチャ', ds.features_total.toLocaleString()],
    ['形状異常', ds.anomalies_total.toLocaleString()],
    ['PMTiles', `${ds.pmtiles_mb} MB（${reg.isLocal ? '同梱' : 'R2 配信'}）`],
  ]
  $('meta').innerHTML = rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('')
}

// ---- 初期化 ----------------------------------------------------------------
if (ds) $('subtitle').textContent = ds.target_month
$('build-ver').textContent = `build: ${__BUILD_TIME__}`
renderThemeBtn()
buildLayerList()
renderMeta()
renderZoom()
if (isMobile) panel.classList.add('collapsed')
renderCollapseBtn()

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
