#!/usr/bin/env python3
"""
NASA Lessons Learned Information System (LLIS) Harvester & Static Site Generator
Extracts all 2,100+ authoritative lessons learned from the NASA LLIS backend API,
pre-renders semantic static HTML pages for 100% full-text indexing by Onyx (without headless browser overhead),
and generates sitemaps and raw JSON Lines for ingestion.
"""

from datetime import datetime, timezone
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

import requests

API_URL = "https://llis.nasa.gov/llis/lesson/_search"
BASE_LIVE_URL = "https://llis.nasa.gov"
GITHUB_PAGES_BASE = "https://oht8woowi8yait9n.github.io/llis"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Content-Type": "application/json",
    "Accept": "application/json",
}

MINIMUM_EXPECTED_LESSONS = 2000
MAX_RETRIES = 3
BACKOFF_BASE = 2


def fetch_all_lessons(session: requests.Session) -> list[dict]:
    payload = {
        "query": {"match_all": {}},
        "from": 0,
        "size": 10000,
    }
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"[*] Fetching all lessons from {API_URL} (attempt {attempt}/{MAX_RETRIES})...")
            resp = session.post(API_URL, json=payload, headers=HEADERS, timeout=60)
            if resp.status_code == 200:
                data = resp.json()
                hits = data.get("hits", {}).get("hits", [])
                total = data.get("hits", {}).get("total", len(hits))
                print(f"[+] Successfully retrieved {len(hits)} lessons (total in index: {total})")
                return hits
        except Exception as e:
            print(f"[!] Request error on attempt {attempt}: {e}")
        if attempt < MAX_RETRIES:
            time.sleep(BACKOFF_BASE ** attempt)
    return []


def clean_text(html_val) -> str:
    if not html_val:
        return ""
    if not isinstance(html_val, str):
        return str(html_val)
    # Fix internal image/asset paths
    fixed = re.sub(r'(src|href)=["\'](/llis_lib/[^"\']+)["\']', r'\1="https://llis.nasa.gov\2"', html_val)
    return fixed.strip()


def extract_org_name(org_val) -> str:
    if isinstance(org_val, dict):
        return org_val.get("name") or org_val.get("abr") or "NASA"
    if org_val:
        return str(org_val)
    return "NASA"


def extract_names_list(val) -> list[str]:
    if not val:
        return []
    if isinstance(val, dict):
        names = val.get("name")
        if isinstance(names, list):
            return [str(n) for n in names if n]
        if names:
            return [str(names)]
        return []
    if isinstance(val, list):
        return [str(v) for v in val if v]
    return [str(val)]


HTML_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>NASA Lesson #{lesson_num}: {title}</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      line-height: 1.6;
      color: #24292e;
      max-width: 960px;
      margin: 0 auto;
      padding: 2rem 1.5rem;
      background-color: #fcfcfc;
    }}
    header {{
      border-bottom: 2px solid #e1e4e8;
      padding-bottom: 1.5rem;
      margin-bottom: 2rem;
    }}
    h1 {{
      font-size: 1.85rem;
      color: #0b3d91; /* NASA Blue */
      margin-top: 0;
      margin-bottom: 0.75rem;
    }}
    .metadata {{
      display: flex;
      flex-wrap: wrap;
      gap: 1rem;
      font-size: 0.92rem;
      color: #586069;
      background-color: #f1f8ff;
      border: 1px solid #c8e1ff;
      border-radius: 6px;
      padding: 0.85rem 1.25rem;
      margin-bottom: 1.5rem;
    }}
    .metadata-item {{
      flex: 1 1 200px;
    }}
    .metadata-label {{
      font-weight: 600;
      color: #0366d6;
    }}
    .canonical-link {{
      display: inline-block;
      margin-top: 0.5rem;
      font-size: 0.95rem;
      color: #d13438;
      font-weight: 600;
    }}
    section {{
      background: #ffffff;
      border: 1px solid #e1e4e8;
      border-radius: 6px;
      padding: 1.5rem;
      margin-bottom: 1.75rem;
      box-shadow: 0 1px 3px rgba(0,0,0,0.02);
    }}
    h2 {{
      font-size: 1.3rem;
      color: #0b3d91;
      border-bottom: 1px solid #eaecef;
      padding-bottom: 0.4rem;
      margin-top: 0;
      margin-bottom: 1rem;
    }}
    img {{
      max-width: 100%;
      height: auto;
      border: 1px solid #d1d5da;
      border-radius: 4px;
      margin: 1rem 0;
    }}
    footer {{
      margin-top: 3rem;
      padding-top: 1rem;
      border-top: 1px solid #e1e4e8;
      font-size: 0.85rem;
      color: #6a737d;
      text-align: center;
    }}
  </style>
</head>
<body>
  <header>
    <h1>NASA Lesson #{lesson_num}: {title}</h1>
    <div class="metadata">
      <div class="metadata-item"><span class="metadata-label">Lesson ID:</span> #{lesson_num} (Database ID: {doc_id})</div>
      <div class="metadata-item"><span class="metadata-label">Date:</span> {lesson_date}</div>
      <div class="metadata-item"><span class="metadata-label">Organization:</span> {org}</div>
      <div class="metadata-item"><span class="metadata-label">Program Phase:</span> {program_phase}</div>
      {mission_dir_html}
      {topics_html}
    </div>
    <div class="canonical-link">
      Source: <a href="https://llis.nasa.gov/lesson/{doc_id}" target="_blank" rel="noopener">View Official NASA LLIS Entry (live system)</a>
    </div>
  </header>

  <main>
    {content_sections}
  </main>

  <footer>
    <p>NASA Lessons Learned Information System (LLIS) Public Archive | Synchronized on {sync_date}</p>
  </footer>
</body>
</html>
"""


def generate_static_pages(hits: list[dict], output_dir: str, sync_date: str) -> list[dict]:
    lessons_dir = os.path.join(output_dir, "lessons")
    os.makedirs(lessons_dir, exist_ok=True)

    processed_lessons = []

    for h in hits:
        doc_id = str(h.get("_id", ""))
        src = h.get("_source", {})

        title = src.get("title") or "Untitled Lesson"
        lesson_num = str(src.get("lesson_number") or src.get("documentid") or doc_id).zfill(4)
        lesson_date = str(src.get("lesson_date") or src.get("lessonDate") or "Not Specified")
        org = extract_org_name(src.get("organization"))
        program_phase = str(src.get("programPhase") or "None")

        mission_dirs = extract_names_list(src.get("missionDirectorate"))
        mission_dir_html = ""
        if mission_dirs and mission_dirs != ["None"]:
            mission_dir_html = f'<div class="metadata-item"><span class="metadata-label">Mission Directorate:</span> {", ".join(mission_dirs)}</div>'

        topics = extract_names_list(src.get("categories"))
        topics_html = ""
        if topics and topics != ["None"]:
            topics_html = f'<div class="metadata-item"><span class="metadata-label">Topic / Category:</span> {", ".join(topics)}</div>'

        sections = []

        # Driving Event / Description
        driving_event = clean_text(src.get("drivingEvent") or src.get("description_event"))
        if driving_event and driving_event != "None":
            sections.append(f'<section><h2>Driving Event / Description</h2>\n{driving_event}\n</section>')

        # Lesson(s) Learned
        lesson_text = clean_text(src.get("lesson") or src.get("lesson_learned"))
        if lesson_text and lesson_text != "None":
            sections.append(f'<section><h2>Lesson(s) Learned</h2>\n{lesson_text}\n</section>')

        # Recommendation(s)
        recommendation = clean_text(src.get("recommendation"))
        if recommendation and recommendation != "None":
            sections.append(f'<section><h2>Recommendation(s)</h2>\n{recommendation}\n</section>')

        # Evidence / Context
        evidence = clean_text(src.get("evidence"))
        if evidence and evidence != "None":
            sections.append(f'<section><h2>Evidence / Additional Context</h2>\n{evidence}\n</section>')

        # Related Policy
        policy = clean_text(src.get("relatedPolicy"))
        if policy and policy != "None":
            sections.append(f'<section><h2>Related Policies & Standards</h2>\n{policy}\n</section>')

        content_sections = "\n".join(sections)
        if not content_sections:
            content_sections = "<section><p><em>No additional text documented for this lesson entry.</em></p></section>"

        html_out = HTML_PAGE_TEMPLATE.format(
            lesson_num=escape(lesson_num),
            title=escape(title),
            doc_id=escape(doc_id),
            lesson_date=escape(lesson_date),
            org=escape(org),
            program_phase=escape(program_phase),
            mission_dir_html=mission_dir_html,
            topics_html=topics_html,
            content_sections=content_sections,
            sync_date=sync_date,
        )

        file_path = os.path.join(lessons_dir, f"{doc_id}.html")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html_out)

        processed_lessons.append({
            "id": doc_id,
            "lesson_number": lesson_num,
            "title": title,
            "date": lesson_date,
            "org": org,
            "program_phase": program_phase,
            "github_pages_url": f"{GITHUB_PAGES_BASE}/lessons/{doc_id}.html",
            "live_url": f"{BASE_LIVE_URL}/lesson/{doc_id}",
            "driving_event": driving_event,
            "lesson": lesson_text,
            "recommendation": recommendation,
        })

    return processed_lessons


def generate_index_page(lessons: list[dict], output_dir: str, sync_date: str):
    """Generate root index.html catalog for human browsing and search crawlers."""
    index_path = os.path.join(output_dir, "index.html")

    rows = []
    for item in sorted(lessons, key=lambda x: str(x["lesson_number"]), reverse=True):
        row = (
            f'<tr>'
            f'<td><a href="lessons/{item["id"]}.html">#{escape(item["lesson_number"])}</a></td>'
            f'<td><a href="lessons/{item["id"]}.html"><strong>{escape(item["title"])}</strong></a></td>'
            f'<td>{escape(item["org"])}</td>'
            f'<td>{escape(item["date"][:10])}</td>'
            f'<td><a href="{item["live_url"]}" target="_blank" rel="noopener">NASA LLIS</a></td>'
            f'</tr>'
        )
        rows.append(row)

    rows_html = "\n".join(rows)

    index_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>NASA Lessons Learned Information System (LLIS) - Static Archive</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      line-height: 1.5;
      color: #24292e;
      max-width: 1200px;
      margin: 0 auto;
      padding: 2rem 1.5rem;
      background-color: #fafbfc;
    }}
    header {{
      margin-bottom: 2rem;
      border-bottom: 2px solid #e1e4e8;
      padding-bottom: 1rem;
    }}
    h1 {{ color: #0b3d91; margin-bottom: 0.5rem; }}
    p.lead {{ font-size: 1.1rem; color: #586069; }}
    .stats-bar {{
      display: flex;
      gap: 2rem;
      background: #f1f8ff;
      border: 1px solid #c8e1ff;
      border-radius: 6px;
      padding: 1rem 1.5rem;
      margin-bottom: 2rem;
      font-weight: 500;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: #fff;
      border: 1px solid #e1e4e8;
      border-radius: 6px;
      overflow: hidden;
    }}
    th, td {{
      padding: 0.75rem 1rem;
      text-align: left;
      border-bottom: 1px solid #e1e4e8;
      font-size: 0.92rem;
    }}
    th {{ background: #f6f8fa; color: #0b3d91; font-weight: 600; }}
    tr:hover {{ background-color: #f1f8ff; }}
    a {{ color: #0366d6; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    footer {{
      margin-top: 3rem;
      padding-top: 1rem;
      border-top: 1px solid #e1e4e8;
      font-size: 0.85rem;
      color: #6a737d;
      text-align: center;
    }}
  </style>
</head>
<body>
  <header>
    <h1>NASA Lessons Learned Information System (LLIS)</h1>
    <p class="lead">Static HTML pre-rendered mirror optimized for Onyx search and RAG indexing.</p>
    <div class="stats-bar">
      <div>Total Public Lessons: <strong>{len(lessons)}</strong></div>
      <div>Source: <strong>https://llis.nasa.gov/</strong></div>
      <div>Last Synchronized: <strong>{sync_date}</strong></div>
    </div>
  </header>

  <main>
    <table>
      <thead>
        <tr>
          <th>ID</th>
          <th>Title</th>
          <th>Organization</th>
          <th>Date</th>
          <th>Live LLIS Link</th>
        </tr>
      </thead>
      <tbody>
        {rows_html}
      </tbody>
    </table>
  </main>

  <footer>
    <p>NASA LLIS Static Pre-rendered Archive | Maintained via automated GitHub Actions synchronization.</p>
  </footer>
</body>
</html>
"""
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(index_html)
    print(f"[+] Generated root catalog index: {index_path}")


def write_sitemaps(lessons: list[dict], output_dir: str, current_date: str):
    # 1. Primary Sitemap (GitHub Pages pre-rendered HTML - ideal for Onyx)
    gh_sitemap_path = os.path.join(output_dir, "llis_sitemap.xml")
    gh_urls_path = os.path.join(output_dir, "llis_urls.txt")

    gh_urls = [f"{GITHUB_PAGES_BASE}/"] + [item["github_pages_url"] for item in lessons]

    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for u in gh_urls:
        escaped_u = escape(u)
        priority = "1.0" if u == f"{GITHUB_PAGES_BASE}/" else "0.8"
        xml_lines.append("  <url>")
        xml_lines.append(f"    <loc>{escaped_u}</loc>")
        xml_lines.append(f"    <lastmod>{current_date}</lastmod>")
        xml_lines.append("    <changefreq>monthly</changefreq>")
        xml_lines.append(f"    <priority>{priority}</priority>")
        xml_lines.append("  </url>")
    xml_lines.append("</urlset>\n")

    gh_xml_content = "\n".join(xml_lines)
    ET.fromstring(gh_xml_content.encode("utf-8"))  # Validate XML

    with open(gh_sitemap_path, "w", encoding="utf-8") as f:
        f.write(gh_xml_content)
    with open(gh_urls_path, "w", encoding="utf-8") as f:
        for u in gh_urls:
            f.write(f"{u}\n")
    print(f"[+] Successfully wrote primary sitemap: {gh_sitemap_path} ({len(gh_urls)} URLs)")

    # 2. Direct Sitemap (Pointing to live llis.nasa.gov URLs)
    direct_sitemap_path = os.path.join(output_dir, "llis_direct_sitemap.xml")
    direct_urls_path = os.path.join(output_dir, "llis_direct_urls.txt")

    direct_urls = [f"{BASE_LIVE_URL}/"] + [item["live_url"] for item in lessons]

    d_xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for u in direct_urls:
        escaped_u = escape(u)
        priority = "1.0" if u == f"{BASE_LIVE_URL}/" else "0.8"
        d_xml_lines.append("  <url>")
        d_xml_lines.append(f"    <loc>{escaped_u}</loc>")
        d_xml_lines.append(f"    <lastmod>{current_date}</lastmod>")
        d_xml_lines.append("    <changefreq>monthly</changefreq>")
        d_xml_lines.append(f"    <priority>{priority}</priority>")
        d_xml_lines.append("  </url>")
    d_xml_lines.append("</urlset>\n")

    d_xml_content = "\n".join(d_xml_lines)
    ET.fromstring(d_xml_content.encode("utf-8"))

    with open(direct_sitemap_path, "w", encoding="utf-8") as f:
        f.write(d_xml_content)
    with open(direct_urls_path, "w", encoding="utf-8") as f:
        for u in direct_urls:
            f.write(f"{u}\n")
    print(f"[+] Successfully wrote direct sitemap: {direct_sitemap_path} ({len(direct_urls)} URLs)")

    # 3. Write raw JSON Lines for offline / API ingestion
    jsonl_path = os.path.join(output_dir, "llis_lessons.jsonl")
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for item in lessons:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"[+] Successfully wrote JSON Lines database: {jsonl_path}")


def main():
    print("=" * 70)
    print(" NASA Lessons Learned Information System (LLIS) Generator")
    print(" (Harvesting Backend API & Pre-Rendering Static HTML for Onyx)")
    print("=" * 70)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    current_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    session = requests.Session()
    session.headers.update(HEADERS)

    hits = fetch_all_lessons(session)
    if len(hits) < MINIMUM_EXPECTED_LESSONS:
        print(f"[!] FATAL: Retrieved {len(hits)} lessons, below minimum expected threshold {MINIMUM_EXPECTED_LESSONS}.")
        sys.exit(1)

    print(f"[*] Pre-rendering static HTML pages for {len(hits)} lessons...")
    lessons = generate_static_pages(hits, script_dir, current_date)
    print(f"[+] Successfully generated {len(lessons)} HTML lesson pages in lessons/")

    print("[*] Generating catalog index and XML sitemaps...")
    generate_index_page(lessons, script_dir, current_date)
    write_sitemaps(lessons, script_dir, current_date)

    print("\n" + "=" * 70)
    print("[+] COMPLETE:")
    print(f"    - Lessons Harvested:          {len(lessons)}")
    print(f"    - Static HTML Pages Created:  {len(lessons)} (in lessons/*.html)")
    print(f"    - Primary Onyx Sitemap:       llis_sitemap.xml")
    print(f"    - Direct LLIS Sitemap:        llis_direct_sitemap.xml")
    print(f"    - Offline JSON Lines File:    llis_lessons.jsonl")
    print("=" * 70)


if __name__ == "__main__":
    main()
