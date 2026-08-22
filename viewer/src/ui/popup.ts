import maplibregl from 'maplibre-gl'
import type { MapGeoJSONFeature } from 'maplibre-gl'

import { LAYERS, POPUP_ATTRIBUTES } from '../config'
import { nameOf } from '../regulation'
import { esc } from './dom'

/**
 * クリックした地点の属性を出す。
 *
 * 交差点では13レイヤーが重なる（一時停止・停止線・信号機・横断歩道…）ので、
 * 当たった順に**すべて**出す。1件だけ出すと、下にある規制が見えない。
 */

/** 一度に出す上限。交差点では十数件当たることがある。 */
const MAX_FEATURES = 8

function rows(props: Record<string, unknown>): string {
  return POPUP_ATTRIBUTES.filter(({ key }) => {
    const v = props[key]
    return v !== undefined && v !== null && v !== ''
  })
    .map(({ key, label }) => `<dt>${label}</dt><dd>${esc(String(props[key]))}</dd>`)
    .join('')
}

function block(f: MapGeoJSONFeature): string {
  const props = f.properties as Record<string, unknown>
  const layer = LAYERS[nameOf(f.layer.id)]
  const title = esc(String(props.kind ?? layer?.label ?? '規制'))
  const chip = layer
    ? `<span class="chip" style="--chip:${esc(layer.color)}"></span>`
    : ''
  const sub = layer && props.kind ? `<span class="popup-layer">${esc(layer.label)}</span>` : ''
  return (
    `<p class="popup-title">${chip}${title}${sub}</p>` +
    `<dl class="popup-kv">${rows(props)}</dl>`
  )
}

export function showFeaturePopup(
  map: maplibregl.Map,
  lngLat: maplibregl.LngLatLike,
  features: MapGeoJSONFeature[],
): void {
  if (!features.length) return
  const shown = features.slice(0, MAX_FEATURES)
  const more =
    features.length > shown.length
      ? `<p class="popup-more">ほか ${features.length - shown.length} 件</p>`
      : ''
  new maplibregl.Popup({ maxWidth: '340px', className: 'reg-popup' })
    .setLngLat(lngLat)
    .setHTML(shown.map(block).join('<hr class="popup-sep" />') + more)
    .addTo(map)
}
