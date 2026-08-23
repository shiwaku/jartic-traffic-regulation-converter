/** DOM のちょい足しユーティリティ。 */

export const $ = <T extends HTMLElement>(id: string): T =>
  document.getElementById(id) as T

/** 属性値は元データ由来なので、そのまま innerHTML に入れない。 */
export const esc = (s: string): string =>
  s.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`)

/** 致命的な失敗を画面に出す。地図が作れないときはこれだけが出る。 */
export function fatal(message: string): void {
  const el = $('error')
  el.hidden = false
  el.textContent = message
}
