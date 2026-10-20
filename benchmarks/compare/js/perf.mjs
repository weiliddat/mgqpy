// node --expose-gc perf.mjs CASES.json REVERSE(0|1) OUTPUT.json  (run by perf_js.py)
// The paired method of benchmarks/run.py, ported to Node: per case, verify each
// variant's answer, warm up, calibrate the loop count on the slowest variant to
// a CPU-time target, then time shuffled blocks. sift is the baseline; a second,
// independently loaded sift module is the identical-source control.
import { readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { Query } from "mingo";

const require = createRequire(import.meta.url);
const [casesPath, reverse, outputPath] = process.argv.slice(2);
const config = JSON.parse(readFileSync(casesPath, "utf8"));

const revive = (key, value) => {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    if ("$$f" in value) return Number(value.$$f);
    if ("$$bytes" in value) return Buffer.from(value.$$bytes, "hex");
    if ("$$date" in value) return new Date(value.$$date);
    if ("$$re" in value) return new RegExp(value.$$re[0], value.$$re[1]);
  }
  return value;
};

function loadSift() {
  for (const key of Object.keys(require.cache)) {
    if (key.includes("/node_modules/sift/")) delete require.cache[key];
  }
  return require("sift").default;
}

const loaders = {
  sift: () => ({ prepare: (q) => loadedSift(q), match: (p, d) => p(d) }),
  mingo: () => ({ prepare: (q) => new Query(q), match: (p, d) => p.test(d) }),
  control: () => ({ prepare: (q) => loadedControl(q), match: (p, d) => p(d) }),
};
let loadedSift, loadedControl;
const order = reverse === "1" ? ["control", "mingo", "sift"] : ["sift", "mingo", "control"];
for (const name of order) {
  if (name === "sift") loadedSift = loadSift();
  if (name === "control") loadedControl = loadSift();
}
if (loadedSift === loadedControl) throw new Error("control must be an independent module instance");
const variants = Object.fromEntries(Object.keys(loaders).map((name) => [name, loaders[name]()]));

const cpu = () => { const u = process.cpuUsage(); return u.user + u.system; };
function mulberry32(seed) {
  return () => {
    seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
function timeit(fn, loops) {
  const start = cpu();
  for (let i = 0; i < loops; i++) fn();
  return (cpu() - start) / loops;
}

const OPERATIONS = ["match", "construct", "single-use"];
const rows = [];
for (const item of config.cases) {
  const statuses = {}, prepared = {}, inputs = {};
  for (const [name, v] of Object.entries(variants)) {
    const [q, d] = JSON.parse(item.encoded, revive);
    inputs[name] = [q, d];
    try {
      prepared[name] = v.prepare(q);
      const value = v.match(prepared[name], d);
      statuses[name] = { value: String(value), eligible: value === item.expected && item.server === "agrees" };
    } catch (error) {
      statuses[name] = { error: `${error.constructor.name}: ${error.message}`.slice(0, 200), eligible: false };
    }
  }
  const row = { name: item.name, expected: item.expected, server: item.server, status: statuses, timings: {} };
  if (statuses.sift.eligible || statuses.mingo.eligible) {
    for (const operation of config.operations) {
      const functions = {};
      for (const [name, v] of Object.entries(variants)) {
        if (!statuses[name].eligible) continue;
        const [q, d] = inputs[name], p = prepared[name];
        functions[name] = operation === "match" ? () => v.match(p, d)
          : operation === "construct" ? () => v.prepare(q) : () => v.match(v.prepare(q), d);
      }
      for (const fn of Object.values(functions)) for (let i = 0; i < config.warmups; i++) fn();
      let calibration = 0;
      for (const fn of Object.values(functions)) calibration = Math.max(calibration, timeit(fn, 100));
      const loops = Math.max(20, Math.min(100000, Math.floor(config.seconds * 1e6 / Math.max(calibration, 1e-3))));
      const samples = Object.fromEntries(Object.keys(functions).map((n) => [n, []]));
      const rng = mulberry32(4361 + item.index + 1000 * OPERATIONS.indexOf(operation));
      for (let block = 0; block < config.blocks; block++) {
        const names = Object.keys(functions);
        for (let i = names.length - 1; i > 0; i--) {
          const j = Math.floor(rng() * (i + 1));
          [names[i], names[j]] = [names[j], names[i]];
        }
        for (const name of names) samples[name].push(timeit(functions[name], loops));
        globalThis.gc();
      }
      if (operation !== "construct") {
        for (const [name, fn] of Object.entries(functions)) {
          if (fn() !== item.expected) throw new Error(`${item.name} ${name}: answer changed after timing`);
        }
      }
      row.timings[operation] = { loops, samples_us: samples };
    }
  }
  rows.push(row);
}
writeFileSync(outputPath, JSON.stringify({ reverse_imports: reverse === "1", rows }));
