export const seo = (title: string, description: string) => () => ({
  meta: [
    { title: `${title} | URANIUM VERIFY - AICTE` },
    { name: "description", content: description },
    { property: "og:title", content: `${title} | URANIUM VERIFY` },
    { property: "og:description", content: description },
    { property: "og:type", content: "website" },
    { name: "twitter:card", content: "summary" },
  ],
});
