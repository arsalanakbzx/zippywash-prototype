// Bridge to the Python domain. The 25 Milestone 5 classes run inside the browser (Pyodide):
// every screen action is one call to zippywash.api.ZippyWashAPI, which returns JSON.
let apiPromise = null;

export function loadPython(onProgress = () => {}) {
  if (apiPromise) return apiPromise;
  apiPromise = (async () => {
    onProgress("Starting Python…");
    const base = new URL("./", window.location.href).href;
    const { loadPyodide } = await import(/* @vite-ignore */ `${base}pyodide/pyodide.mjs`);
    const pyodide = await loadPyodide({ indexURL: `${base}pyodide/` });
    onProgress("Loading the ZippyWash classes…");
    const zip = await (await fetch(`${base}zippywash.zip`)).arrayBuffer();
    pyodide.unpackArchive(zip, "zip");
    onProgress("Preparing sample data…");
    pyodide.runPython(`
from zippywash.api import ZippyWashAPI
from zippywash.database.repository import InMemoryRepository
_api = ZippyWashAPI(InMemoryRepository())
`);
    return pyodide.globals.get("_api");
  })();
  return apiPromise;
}

export async function call(name, payload = {}) {
  const api = await loadPython();
  const res = JSON.parse(api.call_json(name, JSON.stringify(payload)));
  if (!res.ok) throw new Error(res.error);
  return res.data;
}
