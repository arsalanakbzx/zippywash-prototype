// Copies the Pyodide runtime and packs the zippywash Python package into public/,
// so the site serves everything itself (no CDN needed on presentation day).
import fs from "node:fs";
import path from "node:path";
import JSZip from "jszip";

const web = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..");
const repo = path.resolve(web, "..");
const out = path.join(web, "public");

const pyodideSrc = path.join(web, "node_modules", "pyodide");
const pyodideDst = path.join(out, "pyodide");
fs.mkdirSync(pyodideDst, { recursive: true });
for (const f of ["pyodide.js", "pyodide.mjs", "pyodide.asm.js", "pyodide.asm.wasm", "python_stdlib.zip",
                 "pyodide-lock.json"]) {
  fs.copyFileSync(path.join(pyodideSrc, f), path.join(pyodideDst, f));
}

const zip = new JSZip();
function add(dir, rel) {
  for (const name of fs.readdirSync(dir)) {
    if (name === "__pycache__" || name.endsWith(".pyc")) continue;
    const full = path.join(dir, name);
    const r = path.posix.join(rel, name);
    if (fs.statSync(full).isDirectory()) add(full, r);
    else if (name.endsWith(".py") || name.endsWith(".sql")) zip.file(r, fs.readFileSync(full));
  }
}
add(path.join(repo, "zippywash"), "zippywash");
fs.writeFileSync(path.join(out, "zippywash.zip"), await zip.generateAsync({ type: "nodebuffer", compression: "DEFLATE" }));
console.log("Python runtime and zippywash package ready in public/");
