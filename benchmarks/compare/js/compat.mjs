// node compat.mjs CORPUS.json OUTPUT.json
// Runs the exported compatibility corpus through sift and mingo. compat.py
// writes the corpus (tagged values; null for rows JavaScript cannot represent)
// and compares the output with the same MongoDB results as the Python libraries.
import { readFileSync, writeFileSync } from "node:fs";
import sift from "sift";
import { Query } from "mingo";

const revive = (key, value) => {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    if ("$$f" in value) return Number(value.$$f);
    if ("$$bytes" in value) return Buffer.from(value.$$bytes, "hex");
    if ("$$date" in value) return new Date(value.$$date);
    if ("$$re" in value) return new RegExp(value.$$re[0], value.$$re[1]);
  }
  return value;
};

const [corpusPath, outputPath] = process.argv.slice(2);
const corpus = JSON.parse(readFileSync(corpusPath, "utf8"), revive);
const libraries = {
  sift: (q) => sift(q),
  mingo: (q) => { const query = new Query(q); return (d) => query.test(d); },
};
function evaluate(prepare, queries, documents) {
  return queries.map((query) => {
    if (query === null) return "n/a";
    let test;
    try {
      test = prepare(query);
    } catch (error) {
      return { error: "construct", type: error.constructor.name, message: String(error.message).slice(0, 200) };
    }
    const hits = [];
    let i = 0;
    try {
      for (; i < documents.length; i++) {
        const doc = documents[i];
        if (doc === null) continue;
        const value = test(doc);
        if (value) hits.push(i);
      }
    } catch (error) {
      return { error: "match", type: error.constructor.name, message: String(error.message).slice(0, 200), document: i };
    }
    return hits;
  });
}

const output = {};
for (const [name, prepare] of Object.entries(libraries)) {
  const started = process.cpuUsage();
  const results = evaluate(prepare, corpus.queries, corpus.documents);
  const cpu = process.cpuUsage(started);
  const coverage = evaluate(prepare, corpus.coverage, corpus.coverage_documents);
  const docs = corpus.docs.flatMap((group) => evaluate(prepare, group.queries, group.documents));
  output[name] = { results, coverage, docs, cpu_seconds: (cpu.user + cpu.system) / 1e6 };
}
writeFileSync(outputPath, JSON.stringify(output));
