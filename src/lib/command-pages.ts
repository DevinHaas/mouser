export const commandPages = [
  { name: "Dashboard", path: "/", hint: "Home" },
  { name: "Leaderboard", path: "/leaderboard", hint: "Top mouseless runs" },
  { name: "User stats", path: "/stats", hint: "Your performance" },
  { name: "Friends", path: "/friends", hint: "Your friends" },
  { name: "Watch intro", path: "/?intro=1", hint: "Replay the opening story" },
];

export function findCommandPages(query: string, userId?: string) {
  const pages = userId
    ? [...commandPages, { name: "Public profile", path: `/profile/${userId}`, hint: "Your profile" }]
    : commandPages;
  const search = query.trim().toLowerCase();
  return search
    ? pages.filter(({ name, hint }) => `${name} ${hint}`.toLowerCase().includes(search))
    : pages;
}
