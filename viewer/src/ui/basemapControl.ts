import type maplibregl from 'maplibre-gl'

import { BASEMAPS, type Basemap } from '../basemap'

/** 右下の背景地図スイッチャー。 */
export class BasemapControl implements maplibregl.IControl {
  private el!: HTMLElement

  constructor(
    private current: () => Basemap,
    private onSelect: (base: Basemap) => void,
  ) {}

  onAdd(): HTMLElement {
    this.el = document.createElement('div')
    this.el.className = 'maplibregl-ctrl basemap-switch'
    for (const { key, label } of BASEMAPS) {
      const btn = document.createElement('button')
      btn.type = 'button'
      btn.textContent = label
      btn.dataset.base = key
      btn.setAttribute('aria-selected', String(key === this.current()))
      btn.addEventListener('click', () => this.onSelect(key))
      this.el.append(btn)
    }
    return this.el
  }

  onRemove(): void {
    this.el.remove()
  }

  sync(): void {
    for (const btn of this.el.querySelectorAll<HTMLButtonElement>('button')) {
      btn.setAttribute('aria-selected', String(btn.dataset.base === this.current()))
    }
  }
}
