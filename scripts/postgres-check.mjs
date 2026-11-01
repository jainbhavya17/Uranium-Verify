import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { randomBytes } from "node:crypto";
import { pathToFileURL } from "node:url";
const location = process.env.EMBEDDED_POSTGRES_MODULE;
const { default: EmbeddedPostgres } = await import(
  location ? pathToFileURL(location).href : "embedded-postgres"
);
mkdirSync("var", { recursive: true });
const credentialsFile = "var/postgres-test-credentials.json";
const credentials = existsSync(credentialsFile)
  ? JSON.parse(readFileSync(credentialsFile, "utf8"))
  : { password: randomBytes(24).toString("hex"), port: 5544 };
if (!existsSync(credentialsFile))
  writeFileSync(credentialsFile, JSON.stringify(credentials), { mode: 0o600 });
const pg = new EmbeddedPostgres({
  databaseDir: "./var/postgres-verification",
  user: "uranium",
  password: credentials.password,
  port: credentials.port,
  persistent: true,
  authMethod: "scram-sha-256",
  initdbFlags: ["--encoding=UTF8", "--locale=C"],
});
if (!existsSync("var/postgres-verification/PG_VERSION")) await pg.initialise();
await pg.start();
console.log("Isolated PostgreSQL verification server ready on 127.0.0.1:" + credentials.port);
process.on("SIGINT", async () => {
  await pg.stop();
  process.exit(0);
});
await new Promise(() => {});
