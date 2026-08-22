import { LAYERS } from '../config'
import type { Dataset } from '../dataset'
import { $, esc } from './dom'

/**
 * 規制レイヤーの一覧・全ON/OFF・不透明度スライダー。
 *
 * 件数は dataset.json から入れる。0件のレイヤー（その月はどの都道府県も
 * 提供していない種別）はチェックボックスを無効にして、
 * 「表示したのに何も出ない」と悩まないようにする。
 */

export type LayerPanelHandlers = {
  onVisibleChange: (visible: Set<string>) => void
  onOpacityChange: (opacity: number) => void
  onFit: () => void
}

export function initLayerPanel(
  dataset: Dataset,
  visible: Set<string>,
  opacity: number,
  handlers: LayerPanelHandlers,
): void {
  const host = $('layers')
  host.innerHTML = ''

  for (const [name, spec] of Object.entries(LAYERS)) {
    const n = dataset.by_layer[name]?.n ?? 0
    const row = document.createElement('label')
    row.className = n ? 'reg-item' : 'reg-item is-empty'
    if (!n) row.title = 'この月は収録がありません'
    row.innerHTML =
      `<input type="checkbox" data-layer="${esc(name)}"` +
      `${visible.has(name) && n ? ' checked' : ''}${n ? '' : ' disabled'} />` +
      `<span class="chip" style="--chip:${esc(spec.color)}"></span>` +
      `<span class="reg-label">${esc(spec.label)}</span>` +
      `<span class="reg-n">${n ? n.toLocaleString() : '0'}</span>`
    host.append(row)
  }

  const boxes = (): HTMLInputElement[] =>
    [...host.querySelectorAll<HTMLInputElement>('input[data-layer]')]

  const sync = (): void => {
    const next = new Set(
      boxes().filter((b) => b.checked).map((b) => b.dataset.layer as string),
    )
    handlers.onVisibleChange(next)
  }

  for (const box of boxes()) {
    box.addEventListener('change', sync)
  }

  const setAll = (on: boolean): void => {
    for (const box of boxes()) {
      if (box.disabled) continue
      box.checked = on
    }
    sync()
  }
  $<HTMLButtonElement>('all-on').addEventListener('click', () => setAll(true))
  $<HTMLButtonElement>('all-off').addEventListener('click', () => setAll(false))
  $<HTMLButtonElement>('fit-btn').addEventListener('click', handlers.onFit)

  const range = $<HTMLInputElement>('opacity-range')
  const val = $('opacity-val')
  range.value = String(opacity)
  val.textContent = `${Math.round(opacity * 100)}%`
  range.addEventListener('input', () => {
    const v = Number(range.value)
    val.textContent = `${Math.round(v * 100)}%`
    handlers.onOpacityChange(v)
  })
}
