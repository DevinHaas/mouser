import { useHotkey } from "@tanstack/react-hotkeys";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import { authClient } from "@/lib/auth-client";
import { findCommandPages } from "@/lib/command-pages";

export function CommandMenu() {
  const { data: session } = authClient.useSession();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(0);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listId = useId();
  const options = useMemo(
    () => findCommandPages(query, session?.user.id),
    [query, session?.user.id],
  );

  useHotkey("Mod+K", () => setOpen((value) => !value), { preventDefault: true });

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      dialog.showModal();
      requestAnimationFrame(() => inputRef.current?.focus());
    } else if (!open && dialog.open) {
      dialog.close();
    }
  }, [open]);

  const close = () => {
    setOpen(false);
    setQuery("");
    setSelected(0);
  };

  const navigate = (path: string) => location.assign(path);

  return (
    <>
      <button
        className="command-menu-trigger"
        type="button"
        aria-label="Open page navigation"
        onClick={() => setOpen(true)}
      >
        <kbd><span className="cmd-glyph">⌘</span>K</kbd><span>to navigate</span>
      </button>
      <dialog
        ref={dialogRef}
        className="command-menu"
        aria-labelledby={`${listId}-title`}
        onCancel={(event) => {
          event.preventDefault();
          close();
        }}
        onClick={(event) => event.target === event.currentTarget && close()}
        onClose={() => setOpen(false)}
      >
        <h2 id={`${listId}-title`} className="command-menu-title">Go to a page</h2>
        <input
          ref={inputRef}
          className="command-menu-input"
          type="search"
          placeholder="Type a page name…"
          value={query}
          role="combobox"
          aria-autocomplete="list"
          aria-controls={listId}
          aria-expanded="true"
          aria-activedescendant={options[selected] ? `${listId}-${selected}` : undefined}
          onChange={(event) => {
            setQuery(event.target.value);
            setSelected(0);
          }}
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              event.stopPropagation();
              close();
              return;
            }
            if (!options.length || !["ArrowDown", "ArrowUp", "Enter"].includes(event.key)) return;
            event.preventDefault();
            event.stopPropagation();
            if (event.key === "Enter") navigate(options[selected].path);
            else setSelected((index) => (index + (event.key === "ArrowDown" ? 1 : -1) + options.length) % options.length);
          }}
        />
        <div id={listId} className="command-menu-list" role="listbox">
          {options.map((page, index) => (
            <button
              id={`${listId}-${index}`}
              className="command-menu-item"
              type="button"
              role="option"
              aria-selected={index === selected}
              key={page.path}
              onPointerMove={() => setSelected(index)}
              onClick={() => navigate(page.path)}
            >
              <span>{page.name}</span><small>{page.hint}</small>
            </button>
          ))}
          {!options.length && <p className="command-menu-empty">No matching page</p>}
        </div>
        <p className="command-menu-help"><kbd>↑</kbd><kbd>↓</kbd> move <kbd>↵</kbd> open <kbd>esc</kbd> close</p>
      </dialog>
    </>
  );
}
