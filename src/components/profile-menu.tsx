import { useEffect, useRef, useState } from "react";
import { authClient } from "@/lib/auth-client";

/** Top-right account menu: stats/friends/public profile/sign out. */
export function ProfileMenu() {
  const { data: session, isPending } = authClient.useSession();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (isPending || !session) return null;

  return (
    <div className="profile-menu" ref={ref}>
      <button
        type="button"
        className="profile-menu-trigger"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        {session.user.name}
      </button>
      {open && (
        <div className="profile-menu-dropdown" role="menu">
          <a href="/stats" role="menuitem">
            user stats
          </a>
          <a href="/friends" role="menuitem">
            friends
          </a>
          <a href={`/profile/${session.user.id}`} role="menuitem">
            public profile
          </a>
          <button
            type="button"
            role="menuitem"
            onClick={() => authClient.signOut({ fetchOptions: { onSuccess: () => location.assign("/") } })}
          >
            sign out
          </button>
        </div>
      )}
    </div>
  );
}
