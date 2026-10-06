// @ts-check
import starlight from "@astrojs/starlight";
import { defineConfig } from "astro/config";

// GitHub Pages: SITE_URL/BASE_PATH come from the workflow (custom domain, or
// https://eyesonplay.github.io/eyesonplay until one is configured).
const site = process.env.SITE_URL ?? "https://eyesonplay.com";
const base = process.env.BASE_PATH ?? "/";
const repo = "https://github.com/eyesonplay/eyesonplay";

export default defineConfig({
  site,
  base,
  integrations: [
    starlight({
      title: "EyesOnPlay",
      description: "Open-source real-time sports video analysis for football and tennis from a single broadcast camera.",
      logo: { src: "./src/assets/logo.svg", replacesTitle: false },
      favicon: "/favicon.svg",
      social: [{ icon: "github", label: "GitHub", href: repo }],
      editLink: { baseUrl: `${repo}/edit/main/website/` },
      customCss: ["./src/styles/custom.css"],
      head: [
        { tag: "meta", attrs: { property: "og:image", content: new URL(`${base.replace(/\/$/, "")}/og.png`, site).href } },
        { tag: "meta", attrs: { name: "twitter:card", content: "summary_large_image" } },
      ],
      sidebar: [
        { label: "Start here", items: ["getting-started", "guides/how-it-works"] },
        { label: "Sports", items: ["guides/football", "guides/tennis"] },
        { label: "Run it", items: ["guides/configuration"] },
        { label: "Reference", items: [{ autogenerate: { directory: "reference" } }] },
        { label: "Project", items: ["guides/limitations", "guides/licensing", "guides/contributing"] },
      ],
    }),
  ],
});
