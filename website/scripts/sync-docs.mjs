// Copies the repository's docs/*.md into the site's "reference" section so
// docs/ stays the single source: the first "# Heading" becomes the page title,
// links between docs become site links and other repo links point to GitHub.
import { cp, mkdir, readdir, readFile, rm, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const docsDir = join(here, "..", "..", "docs");
const outDir = join(here, "..", "src", "content", "docs", "reference");
const imagesOut = join(here, "..", "src", "assets", "docs");
const repoBlob = "https://github.com/eyesonplay/eyesonplay/blob/main";

// Sidebar order and friendlier titles; unknown files follow alphabetically.
const PAGES = {
  deployment: { order: 1 },
  "integration-feed": { order: 2 },
  "event-schema": { order: 3, title: "Event reference" },
  "third-party": { order: 4, title: "Third-party software and models" },
  "redis-contract": { order: 5, title: "Redis contract (internals)" },
};

const files = (await readdir(docsDir)).filter((f) => f.endsWith(".md")).sort();
const names = new Set(files.map((f) => f.replace(/\.md$/, "")));

function rewriteLinks(markdown) {
  return markdown.replace(/\]\(([^)\s]+)\)/g, (match, target) => {
    if (/^(https?:|mailto:|#)/.test(target)) return match;
    const [path, hash = ""] = target.split("#");
    const anchor = hash ? `#${hash}` : "";
    const doc = path.replace(/^\.\//, "").replace(/\.md$/, "");
    if (!path.includes("/") && path.endsWith(".md") && names.has(doc)) return `](../${doc}/${anchor})`;
    if (path.startsWith("../")) return `](${repoBlob}/${path.slice(3)}${anchor})`;
    return `](${repoBlob}/docs/${path}${anchor})`;
  });
}

await rm(outDir, { recursive: true, force: true });
await mkdir(outDir, { recursive: true });
for (const file of files) {
  const name = file.replace(/\.md$/, "");
  const source = await readFile(join(docsDir, file), "utf8");
  const heading = source.match(/^#\s+(.+)$/m);
  const page = PAGES[name] ?? {};
  const title = page.title ?? heading?.[1]?.trim() ?? name;
  const body = heading ? source.replace(heading[0], "").trimStart() : source;
  const frontmatter = [
    "---",
    `title: ${JSON.stringify(title)}`,
    `editUrl: ${JSON.stringify(`https://github.com/eyesonplay/eyesonplay/edit/main/docs/${file}`)}`,
    page.order ? `sidebar:\n  order: ${page.order}` : null,
    "---",
    "",
  ]
    .filter((line) => line !== null)
    .join("\n");
  await writeFile(join(outDir, file), frontmatter + rewriteLinks(body));
}
// Screenshots and renders used by the site pages (src/assets/docs/*).
await rm(imagesOut, { recursive: true, force: true });
await cp(join(docsDir, "images"), imagesOut, { recursive: true });
console.log(`sync-docs: ${files.length} pages and images from docs/`);
