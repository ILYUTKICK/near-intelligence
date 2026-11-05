import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir, mkdtemp, readFile, realpath, rm, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import openapiTS, { astToString } from "openapi-typescript";

export async function generate(args = []) {
  const repo = fileURLToPath(new URL("../../../", import.meta.url));
  const check = args.includes("--check");
  const pythonIndex = args.indexOf("--python");
  const python = pythonIndex < 0
    ? join(repo, "apps/api/.venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python")
    : args[pythonIndex + 1];
  if (!python || !existsSync(python)) throw new Error("Create the frozen apps/api/.venv or pass --python /absolute/path");
  const local = join(repo, ".local");
  await mkdir(local, { recursive: true });
  const temporary = await mkdtemp(join(local, "ni004-openapi-"));
  try {
    const schemaFile = join(temporary, "openapi.json");
    execFileSync(python, [join(repo, "scripts/generate-api.py"), "--output", schemaFile], {
      cwd: repo, timeout: 30000, windowsHide: true, stdio: ["ignore", "pipe", "pipe"],
    });
    const json = await readFile(schemaFile, "utf8");
    const generated = "// Generated from FastAPI OpenAPI. Do not edit.\n" + astToString(await openapiTS(JSON.parse(json)));
    const outputs = [
      [join(repo, "packages/shared-types/openapi.json"), json],
      [join(repo, "packages/shared-types/src/generated/api.ts"), generated],
    ];
    for (const [path, content] of outputs) {
      if (check) {
        const committed = await readFile(path, "utf8").catch(() => "");
        if (committed !== content) throw new Error(`API contract drift: ${path}`);
      } else {
        await mkdir(dirname(path), { recursive: true });
        await writeFile(path, content, "utf8");
      }
    }
    console.log(check ? "OpenAPI and TypeScript are current" : "Generated OpenAPI and TypeScript");
  } finally {
    // Only delete the freshly created directory, after verifying the absolute parent.
    if (dirname(await realpath(temporary)) !== await realpath(local)) throw new Error("Unsafe temporary path");
    await rm(temporary, { recursive: true });
  }
}
