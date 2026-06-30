import os
import re
import json
import urllib.request
import time
from playwright.sync_api import sync_playwright

# Helper to strip Oxford commas
_OXFORD_COMMA_RE = re.compile(r',\s+and\b')
def strip_oxford_comma(text):
    return _OXFORD_COMMA_RE.sub(' and', text)

def call_gemini(api_key, prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    
    system_instruction = (
        "You are Shubham Bhati, a Java Spring Boot Developer and backend engineer. "
        "Write a short, intelligent, and helpful comment on a developer's blog post. "
        "Keep it positive, professional, and conversational. State your technical view, "
        "ask a relevant follow-up question, or share a brief insight."
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
        print(f"[ERROR] Failed to generate comment from Gemini: {e}")
        return None

def load_env(env_path):
    config = {}
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    config[k.strip()] = v.strip()
    return config

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(script_dir, ".env")
    env = load_env(env_path)
    
    gemini_key = env.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not gemini_key:
        print("[ERROR] Missing GEMINI_API_KEY environment variable.")
        return
        
    processed_file = "processed_articles.txt"
    auth_file = "auth.json"
    
    # Write auth.json from environment secret if running in CI
    auth_json_content = os.environ.get("DEVTO_AUTH_JSON")
    if auth_json_content:
        with open(auth_file, "w", encoding="utf-8") as f:
            f.write(auth_json_content)
            
    # Read processed article IDs
    processed_ids = set()
    if os.path.exists(processed_file):
        with open(processed_file, "r") as f:
            for line in f:
                if line.strip():
                    processed_ids.add(line.strip())
                    
    target_tags = ["springboot", "systemdesign", "java"]
    
    # Check if we are running in headless CI mode or interactive local mode
    is_ci = os.environ.get("GITHUB_ACTIONS") == "true"
    
    with sync_playwright() as p:
        if is_ci:
            # Headless mode for GitHub Actions (expects existing auth.json)
            if not os.path.exists(auth_file):
                print("[ERROR] auth.json session file is missing in GitHub repository. Please commit it first.")
                return
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(storage_state=auth_file)
        else:
            # Interactive local mode for initial login setup
            browser = p.chromium.launch(headless=False)
            if os.path.exists(auth_file):
                context = browser.new_context(storage_state=auth_file)
            else:
                print("[INFO] No session found. Opening login page. Please login manually in the opened browser window...")
                context = browser.new_context()
                page = context.new_page()
                page.goto("https://dev.to/enter")
                # Wait for user to login (wait until user is redirected to home feed or dashboard)
                page.wait_for_url(re.compile(r"https://dev\.to/(?!\benter\b).*"), timeout=300000)
                # Save storage state
                context.storage_state(path=auth_file)
                print("[SUCCESS] Login session saved locally as auth.json!")
                
        page = context.new_page()
        comments_count = 0
        
        for tag in target_tags:
            if comments_count >= 3:
                break
                
            print(f"[*] Checking tag: #{tag}...")
            page.goto(f"https://dev.to/t/{tag}/latest")
            page.wait_for_timeout(3000)
            
            # Extract links to the top 3 latest articles
            articles = page.query_selector_all("a.crayons-story__hidden-navigation-link")
            article_urls = []
            for art in articles[:4]:
                href = art.get_attribute("href")
                if href and href.startswith("/"):
                    article_urls.append("https://dev.to" + href)
                    
            for url in article_urls:
                if comments_count >= 3:
                    break
                    
                # Extract article ID from URL
                match = re.search(r'-([a-z0-9]+)$', url)
                if not match:
                    continue
                article_id = match.group(1)
                
                if article_id in processed_ids:
                    continue
                    
                print(f"[*] Navigating to article: {url}")
                page.goto(url)
                page.wait_for_timeout(3000)
                
                # Fetch article details
                title_el = page.query_selector("h1")
                title = title_el.inner_text() if title_el else "Backend development topic"
                
                desc_el = page.query_selector("div.crayons-article__body")
                description = desc_el.inner_text()[:400] if desc_el else ""
                
                # Verify we are logged in by checking for the comment text box
                comment_box = page.query_selector("textarea.crayons-textfield")
                if not comment_box:
                    print("[WARNING] Could not locate comment box. Make sure your session in auth.json is active!")
                    continue
                    
                print(f"[*] Generating AI comment for: {title}")
                prompt = (
                    f"Create a short, engaging, and professional technical reply comment for the post:\n"
                    f"Title: {title}\n"
                    f"Description: {description}\n\n"
                    f"Requirements:\n"
                    f"1. Make it encouraging and technically sound.\n"
                    f"2. Keep it brief (2 to 3 sentences max).\n"
                    f"3. Do NOT use emojis, hashtags, or Oxford commas (comma before 'and')."
                )
                
                comment = call_gemini(gemini_key, prompt)
                if not comment:
                    continue
                    
                print(f"[*] Posting Comment: {comment}")
                
                # Click and type comment
                comment_box.click()
                comment_box.fill(comment)
                page.wait_for_timeout(1000)
                
                # Submit comment
                submit_btn = page.query_selector("button.crayons-btn[type='submit']")
                if submit_btn:
                    submit_btn.click()
                    page.wait_for_timeout(3000)
                    print(f"[SUCCESS] Auto-comment posted successfully on {url}!")
                    
                    # Log processed ID
                    processed_ids.add(article_id)
                    with open(processed_file, "a") as f:
                        f.write(article_id + "\n")
                    comments_count += 1
                else:
                    print("[ERROR] Could not locate submit button.")
                    
        browser.close()
        print(f"[FINISHED] Process completed. Made {comments_count} comments.")

if __name__ == "__main__":
    main()
