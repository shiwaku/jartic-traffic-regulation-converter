import attributeDef from '../../data/attributes.json'
import pipelineDef from '../../data/pipeline.json'
import layerDef from '../../data/regulation_layers.json'

/**
 * パイプラインと共有する設定。
 *
 * ズーム域・レイヤー定義・属性表はリポジトリ直下 data/ の JSON が単一の情報源で、
 * Python 側（src/config.py）も同じファイルを読む。ここで数字や和名を書き直すと
 * 二重定義になるので書かない。
 */

/** 規制を描き始めるズーム。低ズームでは密度が高すぎて潰れる。 */
export const MIN_ZOOM: number = pipelineDef.tiles.display_min_zoom
/** タイルに収録されている最大ズーム。これを超えると引き伸ばし表示。 */
export const MAX_ZOOM: number = pipelineDef.tiles.max_zoom

/**
 * 規制種別ごとのアイコンのスプライト。
 * 別リポジトリ（jartic-regulation-sprite）で作って GitHub Pages が配信している。
 * アイコン名は共通規制種別コードそのものなので、`reg:63` のように引ける。
 * 背景地図のスタイルが持つスプライトは id を `default` にして残すため、
 * そちらの `icon-image` は書き換えずに済む。
 */
export const SPRITE_ID = 'reg'
export const SPRITE_URL = 'https://shiwaku.github.io/jartic-regulation-sprite/sprite'

/**
 * アイコンを出し始めるズーム。これより低いズームでは点・線・面で描く。
 * 一時停止だけで152万件あるため、低ズームで symbol レイヤーを出すと
 * 衝突判定が重くなりすぎる。
 */
export const ICON_MIN_ZOOM = 13

/** 全国分のデータなので、初期表示・全体表示はこの範囲に合わせる。 */
export const JAPAN_BOUNDS: [number, number, number, number] = [122, 20, 154, 46]

export type LayerSpec = { label: string; codes: string[]; color: string }

/** レイヤー名 → 表示名・色。並び順が凡例の順。 */
export const LAYERS = (layerDef as { layers: Record<string, LayerSpec> }).layers

export type Attribute = {
  key: string
  source?: string
  derived?: boolean
  label?: string
  display?: boolean
}

const ATTRIBUTES = (attributeDef as { attributes: Attribute[] }).attributes

/**
 * ポップアップに出す属性（この順に並べる）。
 * タイルに載る属性は data/attributes.json が決めるので、
 * そこから外した属性は自動的にここからも消える。
 */
export const POPUP_ATTRIBUTES: { key: string; label: string }[] = ATTRIBUTES.filter(
  (a): a is Attribute & { label: string } => a.display !== false && !!a.label,
).map((a) => ({ key: a.key, label: a.label }))

/** 点で表現される規制。線・面レイヤーより前面に積む。 */
export const POINT_LAYERS = new Set([
  'stop',
  'stopline',
  'signal',
  'crosswalk',
  'turn_restrict',
])
