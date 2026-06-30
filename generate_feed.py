import os
import urllib.request
import json
import re
from datetime import datetime

# Enforce no Oxford comma rule
_OXFORD_COMMA_RE = re.compile(r',\s+and\b')
def strip_oxford_comma(text):
    return _OXFORD_COMMA_RE.sub(' and', text)

def call_gemini(api_key):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    
    system_instruction = (
        "You are Shubham Bhati, a Java Spring Boot Developer. You write extremely crisp, "
        "intelligent, and practical backend engineering tips. "
        "Focus on Spring Boot, microservices, databases (PostgreSQL, Redis), data streaming (Kafka), "
        "API performance, or system design."
    )
    
    prompt = (
        "Write a short, engaging technical backend tip or micro-article. "
        "Requirements:\n"
        "1. Write strictly in a human-like, conversational tone (no 'Dear readers' or 'In this post').\n"
        "2. Include a specific Java/Spring Boot code snippet or system design explanation where relevant.\n"
        "3. Do NOT use hashtags, emojis, or Oxford commas (never put a comma before 'and').\n"
        "4. Avoid formal lectures. Keep it short (under 200 words).\n"
        "5. Title the post in the first line, starting with 'Title: [Your Title Here]'. The rest should be the body."
    )
    
    payload = {
        "contents": [{
            "parts": [{
                "text": f"{system_instruction}\n\nPrompt: {prompt}"
            }]
        }]
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            raw_text = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
            return strip_oxford_comma(raw_text)
    except Exception as e:
        print(f"[ERROR] Failed to fetch content from Gemini: {e}")
        return None

def build_rss_item(title, body):
    pub_date = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")
    # Generate a deterministic unique link for the post item
    slug = re.sub(r'[^a-zA-Z0-9]+', '-', title.lower()).strip('-')
    link = f"https://shubhambhati.is-a.dev/posts/{slug}"
    
    # HTML escape the body text to make RSS valid XML
    escaped_body = body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;")
    escaped_title = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    
    item = f"""    <item>
      <title>{escaped_title}</title>
      <link>{link}</link>
      <description>{escaped_body}</description>
      <pubDate>{pub_date}</pubDate>
      <guid isPermaLink="false">{slug}-{int(datetime.utcnow().timestamp())}</guid>
    </item>"""
    return item

def update_rss_feed(new_item):
    feed_path = "rss.xml"
    
    header = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Shubham Bhati | Backend Developer Feed</title>
    <link>https://shubhambhati.is-a.dev</link>
    <description>Daily micro-articles and technical tips on Spring Boot, Java and Microservices</description>
    <language>en-us</language>
    <lastBuildDate>{build_date}</lastBuildDate>
"""
    
    footer = """  </channel>
</rss>"""

    existing_items = []
    
    # Read existing items if rss.xml exists
    if os.path.exists(feed_path):
        with open(feed_path, "r", encoding="utf-8") as f:
            content = f.read()
            # Extract existing <item> blocks
            existing_items = re.findall(r'<item>.*?</item>', content, re.DOTALL)
            
    # Add new item at the top, keep maximum 10 items to prevent huge file sizes
    all_items = [new_item] + existing_items
    all_items = all_items[:10]
    
    build_date = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")
    formatted_header = header.format(build_date=build_date)
    
    with open(feed_path, "w", encoding="utf-8") as f:
        f.write(formatted_header)
        for item in all_items:
            f.write("\n" + item + "\n")
        f.write(footer)
    print("[*] rss.xml feed updated successfully.")

def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[ERROR] GEMINI_API_KEY variable is missing. Exiting.")
        return
        
    print("[*] Generating new daily article content...")
    raw_content = call_gemini(api_key)
    if not raw_content:
        return
        
    # Extract Title and Body
    lines = raw_content.split("\n")
    title = "Daily Backend Tip"
    body_lines = []
    
    for line in lines:
        if line.lower().startswith("title:"):
            title = line.split(":", 1)[1].strip()
        else:
            body_lines.append(line)
            
    body = "\n".join(body_lines).strip()
    
    print(f"[*] Title: {title}")
    print(f"[*] Body Length: {len(body)} chars")
    
    new_item = build_rss_item(title, body)
    update_rss_feed(new_item)

if __name__ == "__main__":
    main()
