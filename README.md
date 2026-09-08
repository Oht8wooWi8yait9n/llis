# NASA Lessons Learned Information System (LLIS) Pre-Rendered Mirror & Sitemap Solution

Automated harvester, static HTML pre-renderer, and weekly synchronization pipeline for the **NASA Lessons Learned Information System (LLIS)**:
`https://llis.nasa.gov/`

This repository solves the single-page application (SPA) indexing problem for **Onyx** (formerly Danswer) and other AI search / RAG platforms, providing 100% full-text coverage of all **2,127** official NASA spaceflight, engineering, and mission lessons learned.

---

## The SPA Indexing Problem & How This Solves It

1. **The Challenge**:
   - `https://llis.nasa.gov/` is built as an Ember.js single-page application.
   - When any lesson page (e.g. `https://llis.nasa.gov/lesson/696`) is fetched by standard HTTP crawlers without a headless browser, the server returns only the empty shell `index.html` (1.7 KB) with `<title>Llis</title>`.
   - Crawling live `llis.nasa.gov/lesson/*` URLs with Onyx's standard Web Connector results in 2,127 blank pages with no searchable text.

2. **The Solution**:
   - This harvester queries the backend Elasticsearch API (`https://llis.nasa.gov/llis/lesson/_search`) to retrieve the entire database of all 2,127 lessons with full text and rich metadata.
   - It pre-renders clean, semantic, static HTML pages (`lessons/{id}.html`) hosted on GitHub Pages (`https://oht8woowi8yait9n.github.io/llis/lessons/{id}.html`).
   - Each page features semantic headings (`<h2>Driving Event</h2>`, `<h2>Lesson(s) Learned</h2>`, `<h2>Recommendation(s)</h2>`), structured metadata badges, and prominent links back to the original entry on live NASA LLIS.
   - Standard web crawlers can ingest 100% of the lesson content with zero headless browser overhead, ultra-fast crawl times, and optimal semantic chunking.

---

## Dataset Overview (2,127 Lessons)

- **Total Lessons**: 2,127 active public records spanning all NASA programs (Apollo, Space Shuttle, ISS, Artemis, Mars Exploration, Commercial Crew, etc.).
- **NASA Centers Represented**:
  - Kennedy Space Center (KSC): 482
  - Jet Propulsion Laboratory (JPL): 420
  - Johnson Space Center (JSC): 237
  - NASA Headquarters (HQ): 206
  - Marshall Space Flight Center (MSFC): 200
  - Goddard Space Flight Center (GSFC): 147
  - Ames Research Center (ARC): 119
  - Glenn Research Center (GRC): 116
  - Langley Research Center, Armstrong Flight Research Center, etc.

---

## Onyx Web Connector Configuration

In your Onyx Admin Console (**Connectors** → **Web**):

| Field | Configuration |
| :--- | :--- |
| **Connector Name** | `NASA-LLIS` |
| **Base URL** | `https://raw.githubusercontent.com/Oht8wooWi8yait9n/llis/main/llis_sitemap.xml` |
| **Scrape Method** | `sitemap` |

Click **Create Connector** to begin indexing the complete NASA Lessons Learned database into Onyx.

---

## Alternative Ingestion Formats

- **Direct Live LLIS Sitemap (`llis_direct_sitemap.xml`)**:
  - `https://raw.githubusercontent.com/Oht8wooWi8yait9n/llis/main/llis_direct_sitemap.xml`
  - Targets direct `https://llis.nasa.gov/lesson/{id}` URLs for crawlers with headless JavaScript rendering (e.g., Playwright) enabled.
- **Offline JSON Lines Database (`llis_lessons.jsonl`)**:
  - Complete structured dump of all 2,127 lessons for local vector databases, fine-tuning, or direct Python ingestion.
- **Human Web Catalog (`index.html`)**:
  - Hosted at `https://oht8woowi8yait9n.github.io/llis/` for searchable table browsing across all lessons.

---

## Automated Maintenance & CI/CD

- **GitHub Actions Workflow**: Runs automatically every Sunday at 00:00 UTC (`.github/workflows/update-sitemap.yml`).
- **Safety Threshold**: Validates that at least 2,000 lessons are harvested before updating, preventing accidental truncation.
- **Manual Trigger**: Supports on-demand execution via GitHub Actions `workflow_dispatch`.
