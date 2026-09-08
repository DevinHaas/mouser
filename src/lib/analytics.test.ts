import assert from "node:assert/strict";
import { shouldShowIntro } from "./analytics";

assert.equal(shouldShowIntro("", false), true);
assert.equal(shouldShowIntro("", true), false);
assert.equal(shouldShowIntro("?play=1", false), false);
assert.equal(shouldShowIntro("?train=1", false), false);
assert.equal(shouldShowIntro("?intro=1", true), true);

console.log("intro visibility ok");
