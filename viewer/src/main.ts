import maplibregl, { type ExpressionSpecification } from 'maplibre-gl'
import * as pmtiles from 'pmtiles'
import 'maplibre-gl/dist/maplibre-gl.css'
import './style.css'
import layerDef from '../../data/regulation_layers.json'

type LayerSpec = { label: string; codes: string[]; color: string }
type Dataset = {
  target_month: string
  features_total: number
  rows_total: number
  n_prefectures: number
  pmtiles_mb: number
  pmtiles_in_repo: boolean
  by_layer: Record<string, { label: string; n: number }>
}

const LAYERS = (layerDef as { layers: Record<string, LayerSpec> }).layers
// 点レイヤーは低ズームで潰れるので下限を上げる。線・面は9から。
const POINT_LAYERS = new Set(['stop', 'stopline', 'signal', 'crosswalk', 'turn_restrict'])
const MIN_ZOOM = 9

// PMTiles は data/ 同梱を第一候補にし、無ければ Release アセットへ落とす。
// 全国分は 100MB を超えるため Git に置けない（run_pipeline がサイズで切り替える）。
const PMTILES_LOCAL = 'data/regulation.pmtiles'
const PMTILES_RELEASE =
  'https://github.com/shiwaku/jartic-traffic-regulation-converter/releases/latest/download/regulation.pmtiles'

const protocol = new pmtiles.Protocol()
maplibregl.addProtocol('pmtiles', protocol.tile)

async function head(url: string): Promise<boolean> {
  try {
    const r = await fetch(url, { method: 'HEAD' })
    return r.ok
  } catch {
    return false
  }
}

async function loadDataset(): Promise<Dataset | null> {
  try {
    const r = await fetch('data/dataset.json')
    return r.ok ? ((await r.json()) as Dataset) : null
  } catch {
    return null
  }
}

const map = new maplibregl.Map({
  container: 'map',
  style: {
    version: 8,
    sources: {
      gsi: {
        type: 'raster',
        tiles: ['https://cyberjapandata.gsi.go.jp/xyz/pale/{z}/{x}/{y}.png'],
        tileSize: 256,
        maxzoom: 18,
        attribution:
          '<a href="https://maps.gsi.go.jp/development/ichiran.html" target="_blank" rel="noopener">国土地理院</a>',
      },
    },
    layers: [
      { id: 'bg', type: 'background', paint: { 'background-color': '#fbfcfd' } },
      {
        id: 'gsi',
        type: 'raster',
        source: 'gsi',
        paint: { 'raster-opacity': 0.6, 'raster-saturation': -0.55 },
      },
    ],
  },
  center: [139.7, 35.68],
  zoom: 10,
  hash: true,
})
map.addControl(new maplibregl.NavigationControl({ visualizePitch: false }), 'bottom-right')
map.addControl(new maplibregl.ScaleControl({ maxWidth: 110, unit: 'metric' }), 'bottom-right')
map.addControl(new maplibregl.GeolocateControl({ trackUserLocation: true }), 'bottom-right')

const width: ExpressionSpecification = [
  'interpolate',
  ['linear'],
  ['zoom'],
  9,
  0.8,
  13,
  1.8,
  16,
  3.4,
]
const radius: ExpressionSpecification = [
  'interpolate',
  ['linear'],
  ['zoom'],
  9,
  1.6,
  13,
  3.2,
  16,
  6,
]

map.on('load', async () => {
  const url = (await head(PMTILES_LOCAL)) ? PMTILES_LOCAL : PMTILES_RELEASE
  map.addSource('reg', { type: 'vector', url: `pmtiles://${url}` })

  const interactive: string[] = []
  // 面 → 線 → 点 の順に積む（点が最前面）
  for (const [name, spec] of Object.entries(LAYERS)) {
    if (POINT_LAYERS.has(name)) continue
    map.addLayer({
      id: `${name}-fill`,
      type: 'fill',
      source: 'reg',
      'source-layer': name,
      filter: ['==', ['geometry-type'], 'Polygon'],
      minzoom: MIN_ZOOM,
      paint: { 'fill-color': spec.color, 'fill-opacity': 0.14 },
    })
    map.addLayer({
      id: `${name}-line`,
      type: 'line',
      source: 'reg',
      'source-layer': name,
      minzoom: MIN_ZOOM,
      layout: { 'line-cap': 'round' },
      paint: { 'line-color': spec.color, 'line-width': width, 'line-opacity': 0.9 },
    })
    interactive.push(`${name}-line`, `${name}-fill`)
  }
  for (const [name, spec] of Object.entries(LAYERS)) {
    if (!POINT_LAYERS.has(name)) continue
    map.addLayer({
      id: `${name}-point`,
      type: 'circle',
      source: 'reg',
      'source-layer': name,
      minzoom: MIN_ZOOM,
      paint: {
        'circle-color': spec.color,
        'circle-radius': radius,
        'circle-opacity': 0.85,
        'circle-stroke-width': ['interpolate', ['linear'], ['zoom'], 13, 0, 15, 0.6],
        'circle-stroke-color': '#fff',
      },
    })
    interactive.push(`${name}-point`)
  }

  buildToggles()
  wirePopup(interactive)

  const ds = await loadDataset()
  renderDataset(ds)
})

function layerIds(name: string): string[] {
  return POINT_LAYERS.has(name) ? [`${name}-point`] : [`${name}-line`, `${name}-fill`]
}

function setVisible(name: string, on: boolean): void {
  for (const id of layerIds(name)) {
    if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', on ? 'visible' : 'none')
  }
}

function buildToggles(): void {
  const host = document.getElementById('layers')!
  host.innerHTML = ''
  for (const [name, spec] of Object.entries(LAYERS)) {
    const label = document.createElement('label')
    label.className = 'toggle'
    label.innerHTML =
      `<input type="checkbox" checked data-layer="${name}" />` +
      `<span class="sw" style="background:${spec.color}"></span>${spec.label}` +
      `<span class="n" data-count="${name}"></span>`
    host.appendChild(label)
  }
  host.querySelectorAll<HTMLInputElement>('input[data-layer]').forEach((el) => {
    el.addEventListener('change', () => setVisible(el.dataset.layer!, el.checked))
  })
  const setAll = (on: boolean) => {
    host.querySelectorAll<HTMLInputElement>('input[data-layer]').forEach((el) => {
      el.checked = on
      setVisible(el.dataset.layer!, on)
    })
  }
  document.getElementById('all-on')!.addEventListener('click', () => setAll(true))
  document.getElementById('all-off')!.addEventListener('click', () => setAll(false))

  const btn = document.getElementById('collapse-btn')!
  const body = document.getElementById('panel-body')!
  btn.addEventListener('click', () => {
    const hidden = body.hasAttribute('hidden')
    if (hidden) body.removeAttribute('hidden')
    else body.setAttribute('hidden', '')
    btn.textContent = hidden ? '−' : '+'
  })
}

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

function wirePopup(ids: string[]): void {
  const existing = ids.filter((id) => map.getLayer(id))
  map.on('click', (e) => {
    const hits = map.queryRenderedFeatures(e.point, { layers: existing })
    if (!hits.length) return
    const p = hits[0].properties as Record<string, unknown>
    const rows = Object.entries(PROP_LABEL)
      .filter(([k]) => p[k] !== undefined && p[k] !== '')
      .map(([k, label]) => `<dt>${label}</dt><dd>${String(p[k])}</dd>`)
      .join('')
    new maplibregl.Popup({ maxWidth: '300px' })
      .setLngLat(e.lngLat)
      .setHTML(
        `<p class="popup-title">${p.kind ?? '規制'}</p><dl class="popup-kv">${rows}</dl>`,
      )
      .addTo(map)
  })
  for (const id of existing) {
    map.on('mouseenter', id, () => (map.getCanvas().style.cursor = 'pointer'))
    map.on('mouseleave', id, () => (map.getCanvas().style.cursor = ''))
  }
}

function renderDataset(ds: Dataset | null): void {
  document.getElementById('build-ver')!.textContent = `build ${__BUILD_TIME__}`
  if (!ds) {
    document.getElementById('brand-sub')!.textContent = 'dataset.json 未生成'
    return
  }
  document.getElementById('brand-sub')!.textContent = ds.target_month
  const dl = document.getElementById('dataset')!
  const rows: [string, string][] = [
    ['レコード', ds.rows_total.toLocaleString()],
    ['フィーチャ', ds.features_total.toLocaleString()],
    ['都道府県', `${ds.n_prefectures} / 47`],
    ['PMTiles', `${ds.pmtiles_mb} MB`],
  ]
  dl.innerHTML = rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('')
  for (const [name, v] of Object.entries(ds.by_layer)) {
    const el = document.querySelector(`[data-count="${name}"]`)
    if (el) el.textContent = v.n.toLocaleString()
  }
}
