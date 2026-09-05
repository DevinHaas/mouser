/** Popular mouseless / keyboard-navigation tools. Picked by a mix of
 * GitHub stars and general adoption in the vim-motions/no-mouse community.
 *
 * ponytail: icons are a single letter on a color chip instead of fetched
 * logo images — real logos would mean hotlinking or vendoring binary
 * assets under uncertain license, for a cosmetic profile badge. Swap in
 * real marks later if that matters.
 */
export type MouselessTool = {
  id: string
  name: string
  website: string
  github: string
  color: string
}

export const MOUSELESS_TOOLS: MouselessTool[] = [
  { id: 'vimium', name: 'Vimium', website: 'https://vimium.github.io', github: 'https://github.com/philc/vimium', color: '#e6483c' },
  { id: 'surfingkeys', name: 'Surfingkeys', website: 'https://github.com/brookhong/Surfingkeys', github: 'https://github.com/brookhong/Surfingkeys', color: '#3c8ee6' },
  { id: 'tridactyl', name: 'Tridactyl', website: 'https://tridactyl.xyz', github: 'https://github.com/tridactyl/tridactyl', color: '#ff9500' },
  { id: 'qutebrowser', name: 'qutebrowser', website: 'https://www.qutebrowser.org', github: 'https://github.com/qutebrowser/qutebrowser', color: '#5cb85c' },
  { id: 'homerow', name: 'Homerow', website: 'https://www.homerow.app', github: 'https://github.com/homerow-app', color: '#8a63d2' },
  { id: 'shortcat', name: 'Shortcat', website: 'https://shortcatapp.com', github: 'https://github.com/shortcat', color: '#e6a23c' },
  { id: 'vimac', name: 'Vimac', website: 'https://vimacapp.com', github: 'https://github.com/dexterleng/vimac', color: '#2c9e6f' },
  { id: 'warpd', name: 'warpd', website: 'https://github.com/rvaiya/warpd', github: 'https://github.com/rvaiya/warpd', color: '#c94f4f' },
  { id: 'neru', name: 'Neru', website: 'https://github.com/xssc/neru', github: 'https://github.com/xssc/neru', color: '#4fc9c9' },
]

export const MOUSELESS_TOOL_BY_ID = new Map(MOUSELESS_TOOLS.map((t) => [t.id, t]))
