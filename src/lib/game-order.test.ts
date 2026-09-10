import assert from "node:assert/strict";
import { terminalIsDue } from "./game-order";

assert.equal(terminalIsDue(2, 3, false), false);
assert.equal(terminalIsDue(3, 3, false), true);
assert.equal(terminalIsDue(7, 3, true), false);
