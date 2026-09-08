import assert from "node:assert/strict";
import { captureError, shouldShowIntro } from "./analytics";

assert.equal(shouldShowIntro("", false), true);
assert.equal(shouldShowIntro("", true), false);
assert.equal(shouldShowIntro("?play=1", false), false);
assert.equal(shouldShowIntro("?train=1", false), false);
assert.equal(shouldShowIntro("?intro=1", true), true);

const logged: unknown[][] = [];
const originalError = console.error;
console.error = (...args) => logged.push(args);
captureError("boom", { operation: "test" });
console.error = originalError;
assert.equal(logged[0]?.[0], "[mouser] test");
assert.equal((logged[0]?.[1] as Error).message, "boom");

console.log("analytics ok");
