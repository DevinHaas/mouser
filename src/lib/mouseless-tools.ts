/** Popular mouseless / keyboard-navigation tools. Picked by a mix of
 * GitHub stars and general adoption in the vim-motions/no-mouse community.
 *
 * Logos are vendored under public/tool-logos/ (favicons / GitHub org avatars,
 * ~1-4KB each). Fetched by hand; refresh with the same sources if a project
 * rebrands.
 */
export type MouselessTool = {
  id: string
  name: string
  website: string
  github: string
  color: string
  logo: string
}

export const MOUSELESS_TOOLS: MouselessTool[] = [
  { id: 'vimium', name: 'Vimium', website: 'https://vimium.github.io', github: 'https://github.com/philc/vimium', color: '#e6483c', logo: '/tool-logos/vimium.webp' },
  { id: 'surfingkeys', name: 'Surfingkeys', website: 'https://github.com/brookhong/Surfingkeys', github: 'https://github.com/brookhong/Surfingkeys', color: '#3c8ee6', logo: '/tool-logos/surfingkeys.webp' },
  { id: 'tridactyl', name: 'Tridactyl', website: 'https://tridactyl.xyz', github: 'https://github.com/tridactyl/tridactyl', color: '#ff9500', logo: '/tool-logos/tridactyl.webp' },
  { id: 'qutebrowser', name: 'qutebrowser', website: 'https://www.qutebrowser.org', github: 'https://github.com/qutebrowser/qutebrowser', color: '#5cb85c', logo: '/tool-logos/qutebrowser.webp' },
  { id: 'homerow', name: 'Homerow', website: 'https://www.homerow.app', github: 'https://github.com/homerow-app', color: '#8a63d2', logo: '/tool-logos/homerow.webp' },
  { id: 'shortcat', name: 'Shortcat', website: 'https://shortcatapp.com', github: 'https://github.com/shortcat', color: '#e6a23c', logo: '/tool-logos/shortcat.webp' },
  { id: 'warpd', name: 'warpd', website: 'https://github.com/rvaiya/warpd', github: 'https://github.com/rvaiya/warpd', color: '#c94f4f', logo: '/tool-logos/warpd.webp' },
  { id: 'neru', name: 'Neru', website: 'https://github.com/y3owk1n/neru', github: 'https://github.com/y3owk1n/neru', color: '#4fc9c9', logo: '/tool-logos/neru.webp' },
]

export const MOUSELESS_TOOL_BY_ID = new Map(MOUSELESS_TOOLS.map((t) => [t.id, t]))
