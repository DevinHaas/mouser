import { useEffect, useRef, useState } from "react";
import { authClient } from "@/lib/auth-client";
import { MOUSELESS_TOOLS } from "@/lib/mouseless-tools";

const NONE_LABEL = "— none —";

/** Lets the signed-in user pick which mouseless tool they drive the game with.
 * ponytail: native <select> popups are OS/browser chrome — no CSS reaches them
 * (that's the whole complaint this replaces). Custom listbox instead, kept small:
 * no typeahead, no virtualization, just enough a11y (role, aria-selected, Escape). */
export function ToolPicker({ initial }: { initial: string | null }) {
  const [value, setValue] = useState(initial ?? "");
  const [saving, setSaving] = useState(false);
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  async function choose(next: string) {
    setValue(next);
    setOpen(false);
    setSaving(true);
    await authClient.updateUser({ mouselessTool: next || null });
    setSaving(false);
  }

  const current = MOUSELESS_TOOLS.find((t) => t.id === value)?.name ?? NONE_LABEL;

  return (
    <div className="tool-picker" ref={rootRef}>
      <span className="tool-picker-label">mouseless tool</span>
      <button
        type="button"
        className="tool-picker-btn"
        disabled={saving}
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span>{current}</span>
        <span className="tool-picker-arrow" aria-hidden="true" />
      </button>
      {open && (
        <ul className="tool-picker-list" role="listbox">
          <li role="option" aria-selected={value === ""}>
            <button type="button" onClick={() => choose("")}>
              {NONE_LABEL}
            </button>
          </li>
          {MOUSELESS_TOOLS.map((t) => (
            <li key={t.id} role="option" aria-selected={value === t.id}>
              <button type="button" onClick={() => choose(t.id)}>
                {t.name}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
