import assert from "node:assert";
import { test } from "node:test";
import { add } from "./add.ts";

test("adds", () => assert.strictEqual(add(2, 3), 5));
