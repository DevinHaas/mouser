import { useState } from "react";
import { actions } from "astro:actions";
import { fmtTime } from "@/lib/format";
import type { PodiumEntry } from "./podium";

/** Bottom-right dock: expands on hover to show the podium, links to the board. */
export function LeaderboardDock() {
  const [open, setOpen] = useState(false);
  const [top3, setTop3] = useState<PodiumEntry[] | null>(null);

  // ponytail: fetched once on first hover, never refetched — the start screen
  // is short-lived and a stale podium for one session is harmless.
  const load = () => {
    if (top3) return;
    actions.topThree().then(({ data }) => data && setTop3(data));
  };

  return (
    <a
      className={`leaderboard-dock${open ? " is-open" : ""}`}
      href="/leaderboard"
      onMouseEnter={() => {
        setOpen(true);
        load();
      }}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => {
        setOpen(true);
        load();
      }}
      onBlur={() => setOpen(false)}
    >
      <span className="leaderboard-dock-title">LEADERBOARD</span>
      <ol className="leaderboard-dock-list" aria-hidden={!open}>
        {(top3 ?? [1, 2, 3]).map((r) =>
          typeof r === "number" ? (
            <li key={r} className="ld-skeleton">
              <span className="ld-rank">{r}</span>
              <span className="ld-name" />
              <span className="ld-time" />
            </li>
          ) : (
            <li key={r.rank}>
              <span className="ld-rank">{r.rank}</span>
              <span className="ld-name">{r.name}</span>
              <span className="ld-time">{fmtTime(r.timeMs)}</span>
            </li>
          ),
        )}
      </ol>
    </a>
  );
}
