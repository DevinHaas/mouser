import assert from "node:assert/strict";
import { findCommandPages } from "./command-pages";

assert.deepEqual(findCommandPages("leader").map(({ path }) => path), ["/leaderboard"]);
assert.equal(findCommandPages("profile").length, 0);
assert.equal(findCommandPages("profile", "mouse-1")[0].path, "/profile/mouse-1");

console.log("command pages ok");
