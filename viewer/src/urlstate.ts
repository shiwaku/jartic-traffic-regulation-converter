import { LAYERS } from './config'
import type { Basemap } from './basemap'

/**
 * 表示状態を URL ハッシュに載せる。
 *
 * 位置は MapLibre が `hash: 'map'` で `#map=ズーム/緯度/経度` に書く（他のキーは
 * 保持される）。こちらは表示中のレイヤー・不透明度・背景地図を足して、
 * 「一方通行だけ表示した札幌」のような画面をそのまま渡せるようにする。
 *
 * 既定値のときはキーを書かない（URL を短く保ち、既定が変わったときに追従できる）。
 */

export const MAP_HASH_KEY = 'map'

export type ViewState = {
  layers?: Set<string>
  opacity?: number
  base?: Basemap
}

function parse(): Map<string, string> {
  const out = new Map<string, string>()
  for (const part of location.hash.replace(/^#/, '').split('&')) {
    if (!part) continue
    const i = part.indexOf('=')
    if (i < 0) out.set(part, '')
    else out.set(part.slice(0, i), decodeURIComponent(part.slice(i + 1)))
  }
  return out
}

export function readState(): ViewState {
  const p = parse()
  const state: ViewState = {}

  const layers = p.get('layers')
  if (layers !== undefined) {
    const known = new Set(Object.keys(LAYERS))
    // 知らない名前は捨てる（レイヤー構成が変わった古いURLで壊れないように）
    state.layers = new Set(layers.split(',').filter((n) => known.has(n)))
  }

  const opacity = Number(p.get('opacity'))
  if (Number.isFinite(opacity) && opacity > 0 && opacity <= 1) state.opacity = opacity

  const base = p.get('base')
  if (base === 'pale' || base === 'std' || base === 'photo' || base === 'blank') {
    state.base = base
  }

  return state
}

/** 自分のキーだけを書き換える。MapLibre が持つ `map=` は触らない。 */
export function writeState(state: {
  layers: Set<string>
  opacity: number
  base: Basemap
}): void {
  const p = parse()

  const all = Object.keys(LAYERS)
  if (state.layers.size === all.length) p.delete('layers')
  else p.set('layers', all.filter((n) => state.layers.has(n)).join(','))

  if (state.opacity >= 1) p.delete('opacity')
  else p.set('opacity', String(Math.round(state.opacity * 100) / 100))

  if (state.base === 'pale') p.delete('base')
  else p.set('base', state.base)

  // 区切りに使う文字だけを逃がす。`map=ズーム/緯度/経度` の `/` や
  // レイヤー一覧の `,` はそのまま残す（MapLibre が読む形を崩さない）。
  const enc = (v: string): string => v.replace(/[#&\s]/g, (c) => encodeURIComponent(c))
  const hash = [...p].map(([k, v]) => (v === '' ? k : `${k}=${enc(v)}`)).join('&')
  history.replaceState(null, '', hash ? `#${hash}` : location.pathname + location.search)
}
