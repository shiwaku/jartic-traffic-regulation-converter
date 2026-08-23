export type Theme = 'light' | 'dark'

const STORAGE_KEY = 'jartic-traffic-regulation-viewer-theme'

/**
 * 既定はダーク。規制のレイヤーは発光で描くので、暗い背景の方が読みやすい。
 * 端末の設定（`prefers-color-scheme`）には従わない。一度切り替えた選択は
 * localStorage に残るので、そちらが優先される。
 */
const DEFAULT_THEME: Theme = 'dark'

export function initialTheme(): Theme {
  const saved = localStorage.getItem(STORAGE_KEY)
  return saved === 'light' || saved === 'dark' ? saved : DEFAULT_THEME
}

/** <html data-theme="…"> を更新して現在テーマを保存する。 */
export function applyThemeAttr(theme: Theme): void {
  document.documentElement.dataset.theme = theme
  localStorage.setItem(STORAGE_KEY, theme)
}
