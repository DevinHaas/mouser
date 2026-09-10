# 3D performance investigation

## What the measurements show

- The production build passes. Client JavaScript is 1.67 MB raw / about 493 KB gzip in total; the shared Three/React chunk is about 254 KB gzip. This is material, but it is not the largest problem.
- Five module-level `useGLTF.preload()` calls start fetching 17.86 MiB of GLBs as soon as the game module loads: capsule, chest, arrow, astronaut, and terminal (`mouser-game.tsx:1536`, `astronaut-boosters.tsx:416`, `terminal-screen.tsx:565`).
- The live GLBs are served with `Cache-Control: public, max-age=0` and `CF-Cache-Status: DYNAMIC`. Repeat visits must revalidate them; they are not immutable CDN assets.
- Every model is high-poly and has no Draco/Meshopt or GPU texture-compression extension. The capsule is 100,956 triangles and is rendered up to seven times (706,692 submitted triangles before frustum culling). The tiny scroll arrow is 100,682 triangles in a second WebGL canvas. The astronaut is 118,320, terminal 101,262, and chest 109,897 triangles.
- Embedded JPEGs decode to roughly 89 MiB of RGBA texture memory across the five preloaded models before mipmaps. The chest alone is about 25 MiB; the arrow is about 16 MiB.
- `Field` allocates two `Vector3`s per live tube per frame (`mouser-game.tsx:394`, `:480`) and writes four DOM style properties per hit target per frame (`:400-403`). This creates avoidable garbage collection and style work.
- The main canvas renders at up to 1.75 DPR (`mouser-game.tsx:1273`) with no adaptive quality policy. The arrow canvas adds another continuously animated WebGL context (`:717-725`).

## What is already good

The canvas is viewport-sized instead of 300vh, DPR is capped, models share cached geometry/textures, shadows and post-processing are absent, and the 1024×545 terminal texture updates only when its content or cursor blink changes—not every frame (`terminal-screen.tsx:502-510`). Keep these choices.

## Recommended order

1. Replace `up.glb` and its WebGL canvas with a CSS/SVG arrow. This removes 3.13 MiB, 100,682 triangles, a decoded 2048² texture, and one renderer/context.
2. Export low-poly assets, starting with the repeated capsule. Aim for visual parity at actual screen size, not arbitrary triangle targets; then resize 2048/2560 textures. Decimation improves transfer, parse time, memory, and every frame. Mesh compression alone only improves transfer/decode.
3. Stop preloading every model at module evaluation. Load only start-visible assets, then defer chest and terminal until game start or nearby progression. Avoid launching all decodes together.
4. Give versioned GLB filenames long-lived immutable cache headers and cache them at Cloudflare. The existing astronaut query string versions the URL but does not fix the zero-TTL response.
5. Reuse projection/live-position vectors and collapse button positioning to a transform-based write. Then add adaptive DPR using the already-installed Drei performance monitor; reduce toward 1.0–1.25 under sustained slow frames.

## Verification gap

Chrome DevTools MCP is not configured, so FPS, long tasks, LCP/INP/CLS, GPU timings, and low-end-device traces could not be measured. After enabling `chrome-devtools-mcp`, record cold/warm desktop and mobile traces for the start screen, scrolling, terminal zoom/typing, and chest release. Treat the current findings as a strong static/network diagnosis, not the final runtime baseline.
