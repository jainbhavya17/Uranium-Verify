export const SITE_TITLE = "Uranium Verify | AICTE Application Review";
export const SITE_DESCRIPTION =
  "An independent prototype for preparing AICTE applications, reviewing supporting documents, resolving queries and tracking application progress.";

export const seo = (title: string, description: string) => () => {
  const pageTitle =
    title.trim().toLowerCase() === "uranium verify" ? SITE_TITLE : `${title} | Uranium Verify`;
  return {
    meta: [
      { title: pageTitle },
      { name: "description", content: description },
      { property: "og:title", content: pageTitle },
      { property: "og:description", content: description },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
      { name: "twitter:title", content: pageTitle },
      { name: "twitter:description", content: description },
    ],
  };
};
