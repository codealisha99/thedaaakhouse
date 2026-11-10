// Run: npx tsx lib/journey.check.ts — smallest guard on stage mapping.
import assert from "node:assert";
import { stageFor } from "./journey";
const old = new Date(Date.now() - 40 * 864e5).toISOString();
assert.equal(stageFor("applied", new Date().toISOString()), "posted");
assert.equal(stageFor("applied", old), "dead");
assert.equal(stageFor("offer", old), "delivered");
assert.equal(stageFor("final_round", null), "out");
assert.equal(stageFor("unknown", null), "drafted");
console.log("journey ok");
