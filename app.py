import streamlit as st
import subprocess
import json
import os
import re
import requests
import platform
import copy
import pandas as pd
from openai import OpenAI
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin

# --- Configuration & Initialization ---
st.set_page_config(
    page_title="AI Website Auditor Pro",
    page_icon="🚀",
    layout="wide",
)

# Initialize OpenAI client
try:
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    OPENAI_ENABLED = True
except Exception:
    OPENAI_ENABLED = False
    st.sidebar.warning("OpenAI API key not found. AI Recommendations will be disabled.", icon="⚠️")

# --- Core Audit Functions ---

def run_single_lighthouse_audit(url, device='desktop'):
    """Runs a single Lighthouse audit for a specific device."""
    st.write(f"🏃‍♂️ Running Lighthouse audit for **{device.capitalize()}**...")

    command = [
        "lighthouse",
        url,
        "--output=json",
        "--output-path=stdout",
        "--only-categories=performance,seo,accessibility,best-practices",
        "--chrome-flags=--headless --no-sandbox --disable-dev-shm-usage",
    ]

    # The default lighthouse run is mobile. We only need to add a flag for desktop.
    if device == 'desktop':
        command.append("--preset=desktop")

    use_shell = platform.system() == "Windows"
    
    try:
        result = subprocess.run(
            command, 
            capture_output=True, 
            text=True, 
            check=True, 
            shell=use_shell,
            timeout=120  # Add a 2-minute timeout
        )
    except subprocess.TimeoutExpired:
        st.error(f"Lighthouse audit for {device} timed out after 2 minutes.")
        return {"error": "Timeout"}
    except subprocess.CalledProcessError as e:
        st.error(f"Lighthouse audit for {device} failed.")
        st.code(f"Error details from Lighthouse:\n{e.stderr}", language="bash")
        return {"error": str(e), "stderr": e.stderr}

    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        st.error(f"Failed to parse Lighthouse JSON output for {device}")
        return {"error": f"JSON parsing error: {str(e)}"}
    
    audits = report.get('audits', {})
    categories = report.get('categories', {})
    
    def get_metric(metric_id):
        return audits.get(metric_id, {}).get('displayValue', 'N/A')

    def get_score(category_name):
        score = categories.get(category_name, {}).get('score')
        return f"{score * 100:.0f}" if score is not None else "0"

    return {
        "performance_score": get_score('performance'),
        "seo_score": get_score('seo'),
        "accessibility_score": get_score('accessibility'),
        "best_practices_score": get_score('best-practices'),
        "metrics": {
            'First Contentful Paint': get_metric('first-contentful-paint'),
            'Largest Contentful Paint': get_metric('largest-contentful-paint'),
            'Total Blocking Time': get_metric('total-blocking-time'),
            'Cumulative Layout Shift': get_metric('cumulative-layout-shift'),
            'Speed Index': get_metric('speed-index'),
        },
        "full_report": report
    }

def run_lighthouse_audits(url):
    """Runs both desktop and mobile Lighthouse audits."""
    results = {}
    try:
        results['desktop'] = run_single_lighthouse_audit(url, 'desktop')
        results['mobile'] = run_single_lighthouse_audit(url, 'mobile')
    except Exception as e:
        st.error(f"A critical error occurred during Lighthouse audits: {e}")
        return {"error": str(e)}
    return results

def analyze_seo(soup):
    """Analyzes on-page SEO factors and returns structured data."""
    st.write("🔎 Analyzing SEO factors...")
    
    title = soup.find('title')
    desc = soup.find('meta', attrs={'name': 'description'})
    images = soup.find_all('img')
    images_without_alt = [img for img in images if not img.get('alt', '').strip()]
    
    return {
        "title": {
            "text": title.text.strip() if title else "Not Found",
            "length": len(title.text.strip()) if title else 0
        },
        "meta_description": {
            "present": bool(desc),
            "text": desc.get('content', '').strip() if desc else "Not Found",
            "length": len(desc.get('content', '').strip()) if desc else 0
        },
        "headings": {
            "h1": len(soup.find_all('h1')),
            "h2": len(soup.find_all('h2')),
            "h3": len(soup.find_all('h3')),
            "h4": len(soup.find_all('h4')),
        },
        "images": {
            "total": len(images),
            "missing_alt": len(images_without_alt),
            "coverage_percent": f"{(len(images) - len(images_without_alt)) / len(images) * 100:.1f}" if images else "100.0"
        }
    }

def analyze_technical(soup, url, page_content):
    """Analyzes technical website features."""
    st.write("⚙️ Analyzing technical features...")
    
    try:
        robots_response = requests.get(urljoin(url, '/robots.txt'), timeout=5)
        robots_ok = robots_response.status_code == 200
    except requests.RequestException:
        robots_ok = False

    # Fixed regex for phone number detection
    phone_pattern = r'(\+\d{1,3}[-.\s]?)?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}'
    
    return {
        "https_enabled": {"value": url.startswith('https://'), "status": "✅" if url.startswith('https://') else "❌"},
        "has_contact_page": {"value": bool(soup.find('a', href=re.compile(r'contact', re.I))), "status": "✅" if bool(soup.find('a', href=re.compile(r'contact', re.I))) else "⚠️"},
        "has_email": {"value": bool(re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', page_content)), "status": "✅" if bool(re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', page_content)) else "⚠️"},
        "has_phone": {"value": bool(re.search(phone_pattern, page_content)), "status": "✅" if bool(re.search(phone_pattern, page_content)) else "⚠️"},
        "has_privacy_link": {"value": bool(soup.find('a', href=re.compile(r'privacy', re.I))), "status": "✅" if bool(soup.find('a', href=re.compile(r'privacy', re.I))) else "❌"},
        "has_robots_txt": {"value": robots_ok, "status": "✅" if robots_ok else "⚠️"}
    }
    
def generate_recommendations(audit_data):
    """Sends a summarized version of the audit data to OpenAI for recommendations."""
    if not OPENAI_ENABLED:
        return {"summary": "OpenAI API key not configured.", "actionItems": ["Enable OpenAI to get AI-powered recommendations."]}
    
    st.write("🧠 Generating AI recommendations...")

    # Create a deep copy and remove full_report to reduce payload size
    data_for_prompt = copy.deepcopy(audit_data)

    if data_for_prompt.get('performance'):
        if data_for_prompt['performance'].get('desktop'):
            data_for_prompt['performance']['desktop'].pop('full_report', None)
        if data_for_prompt['performance'].get('mobile'):
            data_for_prompt['performance']['mobile'].pop('full_report', None)
    
    prompt_data = json.dumps(data_for_prompt, indent=2)

    prompt = f"""
    You are an expert web developer and SEO specialist. Analyze the following website audit summary data.
    Provide a high-level summary of the website's health, considering the differences between mobile and desktop.
    Then, provide a prioritized list of the top 7-10 most impactful, actionable recommendations. Be specific.

    Format your response as a JSON object with two keys: "summary" (a string) and "actionItems" (an array of strings).

    Audit Summary Data:
    {prompt_data}
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a web performance and SEO expert providing actionable advice."}, 
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.6,
            max_tokens=2000
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        if "rate_limit_exceeded" in str(e) or "Request too large" in str(e):
            st.error(f"AI request failed: The audit data is still too large for the model's token limit.")
        else:
            st.error(f"Failed to get AI recommendations: {e}")
        return {"summary": "Error generating recommendations.", "actionItems": []}

@st.cache_data(ttl=3600, show_spinner=False)
def perform_full_audit(url):
    """Orchestrates the entire audit process."""
    with st.status("Performing full website audit...", expanded=True) as status:
        all_data = {"url": url}
        
        status.update(label="Fetching page content with Playwright...")
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-dev-shm-usage']
                )
                page = browser.new_page()
                page.goto(url, wait_until='networkidle', timeout=60000)
                page_content = page.content()
                browser.close()
            soup = BeautifulSoup(page_content, 'html.parser')
        except Exception as e:
            st.error(f"Failed to load the page with Playwright: {e}")
            return None

        status.update(label="Running Lighthouse audits (Desktop & Mobile)...")
        all_data['performance'] = run_lighthouse_audits(url)
        
        status.update(label="Analyzing SEO...")
        all_data['seo'] = analyze_seo(soup)
        
        status.update(label="Analyzing technical features...")
        all_data['technical'] = analyze_technical(soup, url, page_content)

        status.update(label="Generating AI recommendations...")
        all_data['recommendations'] = generate_recommendations(all_data)
        
        status.update(label="Audit Complete!", state="complete")
    return all_data

# --- UI Helper Functions ---
def display_performance_card(device_name, perf_data):
    """Creates a visually appealing card for performance results."""
    st.subheader(f"{'🖥️' if device_name == 'Desktop' else '📱'} {device_name} Performance")
    
    if perf_data.get("error"):
        st.error(f"Could not retrieve {device_name} performance data.")
        st.write(f"Error details: {perf_data.get('error', 'Unknown error')}")
        return

    cols = st.columns(4)
    cols[0].metric("Performance", f"{perf_data.get('performance_score', 'N/A')}/100")
    cols[1].metric("Accessibility", f"{perf_data.get('accessibility_score', 'N/A')}/100")
    cols[2].metric("Best Practices", f"{perf_data.get('best_practices_score', 'N/A')}/100")
    cols[3].metric("SEO", f"{perf_data.get('seo_score', 'N/A')}/100")

    st.markdown("##### Core Web Vitals & Metrics")
    vitals = perf_data.get("metrics", {})
    if vitals:
        df = pd.DataFrame.from_dict(vitals, orient='index', columns=['Value'])
        st.table(df)
    else:
        st.write("No metrics data available.")
    
    with st.expander("View Full Lighthouse JSON Report"):
        full_report = perf_data.get("full_report", {})
        if full_report:
            st.json(full_report)
        else:
            st.write("No full report available.")

# --- Streamlit Main UI ---
st.title("🚀 AI Website Auditor Pro")
st.markdown("Get a comprehensive audit of your website's **Desktop & Mobile Performance**, **SEO**, and **Technical Setup**.")

url_to_audit = st.text_input("Enter a website URL to audit", "https://www.streamlit.io", key="url_input")

if st.button("Analyze Website", type="primary"):
    if not url_to_audit.startswith("http"):
        st.error("Please enter a valid URL (e.g., https://www.example.com)")
    else:
        results = perform_full_audit(url_to_audit)
        
        if results:
            recs = results.get('recommendations', {})
            perf = results.get('performance', {})
            seo = results.get('seo', {})
            tech = results.get('technical', {})
            
            st.header("⭐ AI Analysis & Recommendations")
            st.info(recs.get('summary', "No summary available."), icon="💡")
            
            st.subheader("Top Action Items")
            action_items = recs.get('actionItems', [])
            if action_items:
                for i, item in enumerate(action_items):
                    st.markdown(f"**{i+1}.** {item}")
            else:
                st.write("No action items available.")
            st.divider()

            tab1, tab2, tab3 = st.tabs(["📊 Performance Audit", "🔎 SEO Analysis", "⚙️ Technical Checklist"])

            with tab1:
                if perf and not perf.get("error"):
                    col1, col2 = st.columns(2)
                    with col1:
                        display_performance_card("Desktop", perf.get('desktop', {}))
                    with col2:
                        display_performance_card("Mobile", perf.get('mobile', {}))
                else:
                    st.error("Performance audit could not be completed.")
                    if perf.get("error"):
                        st.write(f"Error: {perf['error']}")

            with tab2:
                st.subheader("On-Page SEO Factors")
                if seo:
                    c1, c2 = st.columns(2)
                    title_length = seo['title']['length']
                    desc_length = seo['meta_description']['length']
                    
                    c1.metric("Title Tag Length", f"{title_length} characters", 
                             "Good" if title_length <= 60 else "Too Long")
                    c1.write(f"**Title:** {seo['title']['text']}")
                    
                    c2.metric("Meta Description Length", f"{desc_length} characters", 
                             "Good" if desc_length <= 160 else "Too Long")
                    c2.write(f"**Description:** {seo['meta_description']['text']}")
                    
                    st.divider()
                    st.subheader("Content Structure")
                    c3, c4 = st.columns(2)
                    
                    heading_df = pd.DataFrame.from_dict(seo['headings'], orient='index', columns=['Count'])
                    c3.write("##### Heading Tag Distribution")
                    c3.dataframe(heading_df)

                    c4.write("##### Image SEO")
                    missing_alt = seo['images']['missing_alt']
                    total_images = seo['images']['total']
                    coverage_percent = float(seo['images']['coverage_percent'])
                    
                    c4.metric("Images Missing Alt Text", f"{missing_alt} / {total_images}", 
                             "Good" if missing_alt == 0 else "Needs Improvement")
                    c4.progress(coverage_percent / 100, text=f"{coverage_percent:.1f}% Alt Text Coverage")

            with tab3:
                st.subheader("Technical & Setup Checklist")
                if tech:
                    tech_items = [
                        {"Feature": "HTTPS Enabled", "Status": tech['https_enabled']['status'], "Details": "Site is served over a secure connection."},
                        {"Feature": "Contact Page Link", "Status": tech['has_contact_page']['status'], "Details": "A link to a contact page was found."},
                        {"Feature": "Email Address Found", "Status": tech['has_email']['status'], "Details": "An email address is present on the page."},
                        {"Feature": "Phone Number Found", "Status": tech['has_phone']['status'], "Details": "A phone number is present on the page."},
                        {"Feature": "Privacy Policy Link", "Status": tech['has_privacy_link']['status'], "Details": "A link to a privacy policy was found."},
                        {"Feature": "Robots.txt Exists", "Status": tech['has_robots_txt']['status'], "Details": "The site has a robots.txt file."},
                    ]
                    df_tech = pd.DataFrame(tech_items)
                    st.dataframe(df_tech, use_container_width=True)
        else:
            st.error("Failed to complete the audit. Please check the URL and try again.")