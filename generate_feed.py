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
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    
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
        "5. Title the post on the first line starting with 'Title: [Title]'.\n"
        "6. Provide 3-4 lowercase tags on the second line starting with 'Tags: tag1, tag2, tag3'.\n"
        "7. The rest should be the body content."
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

def post_to_devto(api_key, title, body, tags):
    url = "https://dev.to/api/articles"
    # DEV.to tags must be alphanumeric, no spaces, no special characters, limit is 4 tags
    sanitized_tags = []
    for tag in tags:
        clean_tag = re.sub(r'[^a-zA-Z0-9]', '', tag).lower()
        if clean_tag:
            sanitized_tags.append(clean_tag)
            
    payload = {
        "article": {
            "title": title,
            "published": True,
            "body_markdown": body,
            "tags": sanitized_tags[:4]
        }
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "api-key": api_key,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        },
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            print(f"[SUCCESS] Published directly to DEV.to! URL: {res_data.get('url')}")
            return True
    except Exception as e:
        print(f"[ERROR] Failed to publish directly to DEV.to: {e}")
        return False

def post_to_hashnode(token, publication_id, title, body, tags):
    url = "https://gql.hashnode.com"
    
    query = """
    mutation PublishPost($input: PublishPostInput!) {
      publishPost(input: $input) {
        post {
          id
          url
        }
      }
    }
    """
    
    # Map simple tags to Hashnode tags structure
    hashnode_tags = []
    for tag in tags[:5]:
        slug = "".join([c for c in tag if c.isalnum()]).lower()
        if slug:
            hashnode_tags.append({"name": tag, "slug": slug})
            
    payload = {
        "query": query,
        "variables": {
            "input": {
                "publicationId": publication_id,
                "title": title,
                "contentMarkdown": body,
                "tags": hashnode_tags,
                "disabledComments": False
            }
        }
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}" if not token.startswith("Bearer ") else token
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            if "errors" in res_data:
                print(f"[ERROR] Hashnode GraphQL returned errors: {res_data['errors']}")
                return False
            post_url = res_data.get("data", {}).get("publishPost", {}).get("post", {}).get("url")
            print(f"[SUCCESS] Published directly to Hashnode! URL: {post_url}")
            return True
    except Exception as e:
        print(f"[ERROR] Failed to publish directly to Hashnode: {e}")
        return False

def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[ERROR] GEMINI_API_KEY variable is missing. Exiting.")
        return
        
    print("[*] Generating new daily article content...")
    raw_content = call_gemini(api_key)
    if not raw_content:
        return
        
    # Extract Title, Tags, and Body
    lines = raw_content.split("\n")
    title = "Daily Backend Tip"
    tags = ["programming", "backend", "java"]
    body_lines = []
    
    for line in lines:
        if line.lower().startswith("title:"):
            title = line.split(":", 1)[1].strip()
        elif line.lower().startswith("tags:"):
            tags_str = line.split(":", 1)[1].strip()
            tags = [t.strip() for t in tags_str.split(",") if t.strip()]
        else:
            body_lines.append(line)
            
    body = "\n".join(body_lines).strip()
    
    print(f"[*] Title: {title}")
    print(f"[*] Tags: {tags}")
    print(f"[*] Body Length: {len(body)} chars")
    
    # 1. Update RSS feed
    new_item = build_rss_item(title, body)
    update_rss_feed(new_item)
    
    # 2. Publish to DEV.to directly if API Key is set
    devto_key = os.environ.get("DEVTO_API_KEY")
    if devto_key:
        print("[*] Publishing directly to DEV.to via API...")
        post_to_devto(devto_key, title, body, tags)
        
    # 3. Publish to Hashnode directly if Token & Publication ID are set
    hashnode_token = os.environ.get("HASHNODE_TOKEN")
    hashnode_pub_id = os.environ.get("HASHNODE_PUBLICATION_ID")
    if hashnode_token and hashnode_pub_id:
        print("[*] Publishing directly to Hashnode via GraphQL API...")
        post_to_hashnode(hashnode_token, hashnode_pub_id, title, body, tags)

if __name__ == "__main__":
    main()
