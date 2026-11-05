import { generate } from "../packages/shared-types/scripts/generate.mjs";

generate(process.argv.slice(2)).catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
