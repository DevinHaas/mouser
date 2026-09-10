export const terminalIsDue = (
  freeCollected: number,
  terminalAfter: number,
  terminalDone: boolean,
) => !terminalDone && freeCollected >= terminalAfter;
