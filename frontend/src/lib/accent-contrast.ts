function rgb(hex: string): number[] {
  if (!/^#[a-f0-9]{6}$/i.test(hex)) throw new RangeError('Expected a six-digit hex colour')
  return [1, 3, 5].map(index => parseInt(hex.slice(index, index + 2), 16))
}
function luminance(hex: string): number {
  const values = rgb(hex).map(value => { const c = value / 255; return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4 })
  return values[0] * 0.2126 + values[1] * 0.7152 + values[2] * 0.0722
}
export function contrastRatio(a: string, b: string): number {
  const x = luminance(a), y = luminance(b)
  return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05)
}
export function resolveAccentTokens(hex: string, theme: 'dark' | 'light', surfaces: { background: string; card: string; accent?: string }) {
  const channels = rgb(hex)
  const meets = (colour: string) => Object.values(surfaces).every(surface => contrastRatio(colour, surface!) >= 4.5)
  const mix = (amount: number) => '#' + channels.map(value => Math.round(value + ((theme === 'light' ? 0 : 255) - value) * amount).toString(16).padStart(2, '0')).join('')
  let primary = hex
  if (!meets(primary)) {
    let low = 0, high = 1
    for (let i = 0; i < 24; i++) { const middle = (low + high) / 2; if (meets(mix(middle))) high = middle; else low = middle }
    primary = mix(high)
  }
  const primaryForeground = contrastRatio('#000000', primary) >= contrastRatio('#ffffff', primary) ? '#000000' : '#ffffff'
  return { primary, primaryForeground, accentForeground: primary, ring: primary }
}
