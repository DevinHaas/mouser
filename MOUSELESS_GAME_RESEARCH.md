# Mouseless Keyboard-Navigation Game: Research & Stack Guide

## 1. HOW MOUSELESS TOOLS DETECT CLICKABLE ELEMENTS

### Shortcat (macOS)
- Uses **OS Accessibility API (AXUIElement)**, not DOM parsing
- Reads roles, labels, and parent-child hierarchies from the accessibility tree
- Detects: buttons, links, text fields, checkboxes, radio buttons, menus
- **Key for your game:** All interactive elements must be real semantic HTML with proper roles/labels

### Vimium / Vimari (Browser Extensions)
- Scans **live DOM** and accessibility tree simultaneously
- Detects clickable: `<a>`, `<button>`, `<input>`, `<select>`, elements with `role="button"` / `role="link"`, clickable divs with event handlers
- **Critical limit:** Canvas/WebGL content is **invisible**—cannot be targeted
- Assigns labels based on: text content, `aria-label`, `title`, image `alt` text
- Updates link hint labels whenever elements change (focus, visibility)

### Homerow
- Hybrid approach: accessibility tree + DOM scanning
- Supports manual ARIA hints: `data-homerow-hint="X"` for custom labels
- Focuses on real interactive elements; ignores purely decorative content

### Detection Summary
```
DETECTABLE (mouseless tools):
✓ <button>, <a>, <input>, <select>, <textarea>
✓ [role="button"], [role="link"], [role="option"], [tabindex]
✓ contenteditable=true with [role="textbox"]
✓ Proper <label> + input association
✓ aria-label, aria-labelledby

NOT DETECTABLE:
✗ Canvas / WebGL / <img> (unless <img> is inside <a>)
✗ Div with no role and no event handler registered
✗ Pseudo-elements, styled text without semantic wrapper
```

---

## 2. RENDERING TALL PIXEL-ART SCROLLING BACKGROUNDS

### Recommended: CSS Background + Positioned Elements

**Why not canvas?**  
Canvas is invisible to accessibility tools—breaks the entire premise.

**Implementation:**
```css
.game-container {
  position: relative;
  height: 100vh;
  overflow-y: scroll;
  background-image: url('medieval-city.png');
  background-size: auto;
  background-attachment: scroll;
  image-rendering: pixelated;
  /* or: image-rendering: crisp-edges; (Firefox) */
}

.game-scene {
  position: relative;
  height: 2400px; /* taller than viewport */
  background-image: url('tileset.png');
  image-rendering: pixelated;
}
```

### Performance Optimization
- **Sprite sheets:** Use `background-position` to avoid multiple image requests
- **Size:** Serve pixel art at native resolution (e.g., 320×240 for medieval scene)—upscale via `image-rendering: pixelated`, not pixel count
- **Large images:** Use `background-attachment: scroll` (not `fixed`) to avoid GPU bottleneck on tall backgrounds
- **CSS will-change:** Sparingly apply to animated parallax layers
  ```css
  .parallax-layer {
    will-change: transform;
    transform: translateY(var(--scroll-offset));
  }
  ```
- **Sprite atlas:** One 2048×2048 or larger spritesheet reduces request overhead

### Zoom Tolerance
- `image-rendering: pixelated` works reliably at integer scales (100%, 200%)
- At fractional scales (150%, zoom in/out), pixels may appear uneven in Chrome/Firefox—acceptable for a game, but test early

---

## 3. POSITIONING SEMANTIC ELEMENTS OVER THE SCROLLING SCENE

### Strategy: Absolutely-Positioned Interactive Elements

```html
<div class="game-container">
  <!-- Tall background scene -->
  <div class="game-scene"></div>
  
  <!-- Interactive buttons/inputs positioned precisely -->
  <button class="interact-btn" style="position: absolute; top: 340px; left: 120px;">
    Pick Lock
  </button>
  
  <input type="text" class="sign-text" 
         style="position: absolute; top: 500px; left: 200px; width: 200px;"
         placeholder="Read the sign...">
  
  <a href="#" class="pixel-door" role="button"
     style="position: absolute; top: 800px; left: 90px;">
    Enter Tower
  </a>
</div>
```

### CSS Styling to Match Pixel Aesthetic
```css
.interact-btn {
  position: absolute;
  padding: 8px 12px;
  background: #4a3728;
  border: 2px solid #8b6f47;
  color: #fff;
  font-family: 'Courier New', monospace;
  font-size: 12px;
  image-rendering: pixelated;
  box-shadow: 2px 2px 0 rgba(0,0,0,0.5);
  cursor: pointer;
  /* Match pixel scale */
  transform: scaleX(2) scaleY(2);
  transform-origin: top left;
}

.sign-text {
  position: absolute;
  background: #d4af37;
  border: 3px solid #8b4513;
  padding: 6px;
  font-size: 11px;
  font-family: 'Pixel Font', monospace;
}
```

### Scroll-into-View on Focus
```javascript
document.addEventListener('focusin', (e) => {
  if (e.target.matches('[class*="interact"]')) {
    e.target.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
});
```

---

## 4. ACCESSIBILITY & MOUSELESS TOOL DETECTABILITY

### Essential Practices

| Element | Roles | Required Attributes | Best Practice |
|---------|-------|---------------------|----------------|
| `<button>` | button | `aria-label` if no text | Semantic; always detected |
| `<a>` | link | `aria-label` | Semantic; target always detected |
| `<input type="text">` | textbox | `<label>` via `for=` | Pair with visible label |
| `<div contenteditable>` | textbox | `role="textbox"` `aria-multiline="true"` | Requires explicit role |
| Selectable text block | N/A | `user-select: text` | Wrap in `<span>` if needed |
| Custom button | button | `role="button"` `tabindex="0"` | Add keyboard handler |

### Code Pattern
```html
<label for="player-name">Enter your name:</label>
<input type="text" id="player-name" 
       aria-label="Enter your character name" 
       placeholder="Name...">

<button aria-label="Pick the lock on the chest">
  🔓 Pick Lock
</button>

<div contenteditable="true" 
     role="textbox" 
     aria-label="Sign inscription"
     aria-multiline="true"
     data-homerow-hint="S">
  Decipher this ancient text...
</div>

<a href="#action" role="button" 
   aria-label="Climb the tower stairs"
   tabindex="0">
  [CLIMB]
</a>
```

### Tab Order & Focus Management
```css
/* Ensure visible focus indicator */
button:focus-visible, input:focus-visible {
  outline: 3px solid #ffff00;
  outline-offset: 2px;
}

/* Adjust tab order if needed */
.urgent-quest { order: -1; } /* Visual tab order via flexbox */
```

### Testing
- **Vimium:** Press `f` in any mouseless game—all buttons/links should get hints
- **Shortcat:** Cmd+' should reveal all clickable elements
- **Browser DevTools → Accessibility Tree:** Inspect semantic role tree to verify detection

---

## 5. RECOMMENDED STACK

### Frontend Framework
**Plain React + CSS** (simplest, fewest dependencies)
- No game engine overhead; focus on semantic HTML
- State management for task progression
- CSS Grid/Flexbox for responsive button placement
- Good: React 18+ supports Suspense, easy scroll-into-view with refs

**Alternative: Vanilla JS**
- Lower complexity if game is small/self-contained
- Easier debugging of accessibility tree interactions

**Avoid:**
- Next.js (overkill)
- Three.js / Babylon.js (canvas-based, invisible to mouseless tools)
- Phaser (game engine, also canvas-driven)

### Tech Stack
```
Frontend:     React 18 + TypeScript
Styling:      Tailwind + CSS modules (for pixel-perfect positioning)
State:        Zustand or Redux (task tracking, progression)
Testing:      Vitest + Playwright (test keyboard nav)
Build:        Vite (fast, minimal config)
Host:         Vercel or GitHub Pages (static / serverless)
```

### Starter Project Structure
```
mouser/
├── src/
│   ├── components/
│   │   ├── GameScene.tsx         # Main container
│   │   ├── InteractiveButton.tsx  # Reusable semantic button
│   │   ├── InputField.tsx         # Accessible input wrapper
│   │   └── ScrollingBackground.tsx
│   ├── hooks/
│   │   ├── useGameProgress.ts
│   │   └── useAccessibilityAnnounce.ts
│   ├── styles/
│   │   ├── pixel.css             # Image-rendering, pixelated fonts
│   │   └── a11y.css              # Focus states, aria labels
│   └── App.tsx
├── public/
│   ├── medieval-city.png         # ~500KB max
│   └── ui-sprites.png            # Button, sign, text overlays
├── vite.config.ts
└── tsconfig.json
```

---

## 6. PRIOR ART & INSPIRATION

### Existing Keyboard-Navigation Trainers
- **Vim Adventures** ([vim-adventures.com](https://vim-adventures.com/)): Zelda-style game for Vim commands
- **Vim Racer** ([vim-racer.com](https://vim-racer.com/)): Race to targets using keyboard
- **VIM Genius** ([vimgenius.com](http://www.vimgenius.com/)): Flashcard trainer
- **KeyCombiner** ([keycombiner.com/vimium](https://keycombiner.com/vimium/)): Spaced repetition for Vimium shortcuts

**Lesson:** Game + keyboard nav works when progression is tied to **correct keyboard input**, not just clicking. Your pixel-art world adds aesthetic hook.

---

## 7. GOTCHAS & PERFORMANCE NOTES

### Gotchas
1. **Zoom/Fractional Scales:** `image-rendering: pixelated` can distort at 150% zoom in Chrome—test on user device
2. **Mobile:** Vimium/Homerow are desktop extensions; test target audience assumption
3. **Tab Order:** Absolutely-positioned elements don't follow document order—manually set `tabindex` or use flexbox `order`
4. **Parallax & Scroll Hijacking:** If you animate scroll with JS, assistive tools may not track—use native scroll or clear focus sync
5. **Canvas Traps:** Easy to draw UI to canvas for "authentic pixel look"—resist; it's invisible to mouseless tools

### Performance Tips
- Keep background images <500KB per scene
- Use sprite sheets (one 2048×2048) vs. many small PNGs
- Lazy-load background images if game has multiple scenes
- Debounce scroll events for parallax updates
- Preload hint labels (Homerow, Vimium) via `data-*` attributes

### A11y Checklist
- [ ] All interactive elements have semantic roles or `role=` override
- [ ] Focus is visible (outline, ring, underline)
- [ ] Tab order matches visual order (or is intentional)
- [ ] All buttons/inputs have accessible labels
- [ ] Contenteditable elements use `role="textbox"` + `aria-label`
- [ ] Test with Vimium (press `f`), Shortcat (Cmd+'), or VoiceOver

---

## 8. DELIVERABLES

### Phase 1 (Foundation)
- [ ] Vite + React + TypeScript setup
- [ ] Static background image with `image-rendering: pixelated`
- [ ] 3 semantic `<button>` elements positioned absolutely
- [ ] Test with Vimium: all buttons get hints
- [ ] Verify in DevTools accessibility tree

### Phase 2 (Game Loop)
- [ ] Task state machine (e.g., "Click the door" → "Type the incantation" → "Select the treasure")
- [ ] Keyboard event handlers (debounce, validate)
- [ ] Scroll-into-view on focus
- [ ] Progress tracking & feedback

### Phase 3 (Polish)
- [ ] Pixel-perfect CSS styling (borders, shadows, fonts)
- [ ] Parallax scrolling (optional, test perf)
- [ ] Sprite atlas optimization
- [ ] Accessibility audit (WAVE, axe DevTools)

---

## 9. SOURCES & FURTHER READING

**Mouseless Tools:**
- [Vimium GitHub Issues #3536, #4736](https://github.com/philc/vimium/issues) (detection discussions)
- [Vimium Everywhere](https://github.com/phil294/vimium-everywhere) (Linux/Windows keyboard nav)

**Pixel Art & CSS:**
- [MDN: image-rendering (CSS)](https://developer.mozilla.org/en-US/docs/Web/CSS/image-rendering)
- [MDN: Crisp pixel art look (Games guide)](https://developer.mozilla.org/en-US/docs/Games/Techniques/Crisp_pixel_art_look)
- [Frontend Masters: Keeping Pixely Images Pixely and Performant](https://frontendmasters.com/blog/keeping-pixely-images-pixely-and-performant/)
- [CSS-Tricks: image-rendering](https://css-tricks.com/almanac/properties/i/image-rendering/)

**Accessibility & ARIA:**
- [MDN: ARIA textbox role](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Roles/textbox_role)
- [MDN: ARIA option role](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Roles/option_role)
- [Accessibe: ARIA Best Practices](https://accesstive.com/blog/aria-best-practices-and-examples/)

**Game Inspiration:**
- [VIM Adventures](https://vim-adventures.com/)
- [Vim Racer](https://vim-racer.com/)
- [KeyCombiner Vimium Trainer](https://keycombiner.com/vimium/)

---

## QUICK START COMMAND

```bash
npm create vite@latest mouser -- --template react-ts
cd mouser
npm install zustand
npm run dev
```

Then create `src/components/GameScene.tsx` with the pattern above.

