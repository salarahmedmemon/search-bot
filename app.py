from flask import Flask, render_template, request, send_file, jsonify
from dotenv import load_dotenv
import os
import requests
import re
import pandas as pd
import io
import pdfkit
from bs4 import BeautifulSoup

# Load .env file
load_dotenv()

app = Flask(__name__)

# Global Email Pattern
EMAIL_RE = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')

# Global Phone Number Patterns (International)
PHONE_PATTERNS = [
    # Pakistan specific: 0331 3591099 (with leading 0)
    re.compile(r'\b0\d{3}[\s-]?\d{7}\b'),
    
    # Pakistan: +92 331 3591099
    re.compile(r'\+92[\s-]?\d{3}[\s-]?\d{7}\b'),
    
    # International format with country code: +92 300 1234567, +91-98765-43210
    re.compile(r'\+\d{1,4}[\s.-]?\(?\d{1,4}\)?[\s.-]?\d{1,4}[\s.-]?\d{1,4}[\s.-]?\d{1,9}'),
    
    # US/Canada: +1-914-478-4814, (914) 478-4814, 914-478-4814
    re.compile(r'\+?1?[\s.-]?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b'),
    
    # India: +91 98765 43210, 091-9876543210, 9876543210
    re.compile(r'\+?91[\s.-]?\d{5}[\s.-]?\d{5}|\+?91[\s.-]?\d{10}|0\d{2,4}[\s.-]?\d{6,8}'),
    
    # UK: +44 20 7123 4567, 020 7123 4567
    re.compile(r'\+?44[\s.-]?\d{2,4}[\s.-]?\d{4}[\s.-]?\d{4}|0\d{2,4}[\s.-]?\d{4}[\s.-]?\d{4}'),
    
    # Australia: +61 4 1234 5678, (02) 1234 5678
    re.compile(r'\+?61[\s.-]?\d{1}[\s.-]?\d{4}[\s.-]?\d{4}|\(0\d\)[\s.-]?\d{4}[\s.-]?\d{4}'),
    
    # Generic international: any phone with 7-15 digits
    re.compile(r'\b\d{4}[\s.-]?\d{3,4}[\s.-]?\d{3,4}\b'),
    re.compile(r'\b\d{3}[\s.-]?\d{3,4}[\s.-]?\d{4}\b'),
]

# Global Address Patterns - More comprehensive
ADDRESS_PATTERNS = [
    # Pakistan specific: unit no 3 akbar cng, main Auto Bahn Rd, Latifabad Unit 3 Hyderabad
    re.compile(r'(?:unit|shop|office|house|plot|flat)\s*(?:no\.?|#)?\s*\d+[,\s]+[^,\n]{10,100}[,\s]+[A-Za-z\s]+(?:Hyderabad|Karachi|Lahore|Islamabad|Rawalpindi|Faisalabad|Multan|Peshawar|Quetta)', re.IGNORECASE),
    
    # US Format with suite/apt: 145 Palisade St #231, Dobbs Ferry, NY 10522
    re.compile(r'\d+\s+[A-Za-z0-9\s]+(?:Street|St\.?|Avenue|Ave\.?|Road|Rd\.?|Boulevard|Blvd\.?|Lane|Ln\.?|Drive|Dr\.?|Court|Ct\.?|Circle|Cir\.?|Way|Place|Pl\.?|Parkway|Pkwy\.?)[\s,]+(?:#|Suite|Ste\.?|Apt\.?|Unit|Building|Bldg\.?)?\s*\d*[A-Za-z]*[\s,]+[A-Za-z\s]+[\s,]+[A-Z]{2}\s+\d{5}(?:-\d{4})?', re.IGNORECASE),
    
    # US Format simple: 145 Palisade St, Dobbs Ferry, NY 10522
    re.compile(r'\d+\s+[A-Za-z0-9\s\.]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Way|Place|Parkway)[\s,]+[A-Za-z\s]+[\s,]+[A-Z]{2}\s+\d{5}(?:-\d{4})?', re.IGNORECASE),
    
    # UK Format: 10 Downing Street, London SW1A 2AA or London, SW1A 2AA
    re.compile(r'\d+\s+[A-Za-z\s]+(?:Street|Road|Avenue|Lane|Close|Drive|Way|Square|Gardens|Place|Terrace)[\s,]+[A-Za-z\s]+[\s,]+(?:London|[A-Z][a-z]+)[\s,]*[A-Z]{1,2}\d{1,2}\s?\d?[A-Z]{2}', re.IGNORECASE),
    
    # UK postcode focused: Complete address with postcode
    re.compile(r'[A-Za-z0-9\s,]+[A-Z]{1,2}\d{1,2}\s?\d?[A-Z]{2}', re.IGNORECASE),
    
    # India Format: 123, MG Road, Bangalore, Karnataka 560001
    re.compile(r'\d+[,\s]+[A-Za-z0-9\s]+(?:Road|Street|Avenue|Lane|Marg|Nagar|Colony|Layout|Cross|Main|Extension|Sector)[\s,]+[A-Za-z\s]+[\s,]+[A-Za-z\s]+[\s,]+\d{6}', re.IGNORECASE),
    
    # Pakistan Format: House 123, Street 45, F-7, Islamabad
    re.compile(r'(?:House|Plot|Flat|Shop)[\s#]*\d+[\s,]+(?:Street|Road|Lane|Block)[\s#]*\d+[\s,]+[A-Za-z0-9\s-]+[\s,]+[A-Za-z\s]+', re.IGNORECASE),
    
    # Canada Format: 123 Main St, Toronto, ON M5H 2N2
    re.compile(r'\d+\s+[A-Za-z0-9\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Lane)[\s,]+[A-Za-z\s]+[\s,]+(?:ON|BC|AB|QC|MB|SK|NS|NB|PE|NL|NT|YT|NU)\s+[A-Z]\d[A-Z]\s?\d[A-Z]\d', re.IGNORECASE),
    
    # Australia Format: 123 George Street, Sydney NSW 2000
    re.compile(r'\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln)[\s,]+[A-Za-z\s]+\s+(?:NSW|VIC|QLD|SA|WA|TAS|NT|ACT)\s+\d{4}', re.IGNORECASE),
    
    # Generic: address with major cities
    re.compile(r'[^,\n]{15,100}[,\s]+(?:Hyderabad|Karachi|Lahore|Mumbai|Delhi|Bangalore|Islamabad|New York|London|Sydney|Toronto|Dubai)', re.IGNORECASE),
    
    # Generic street address with postal code
    re.compile(r'\d+\s+[A-Za-z0-9\s,\.#-]+\s+\d{4,6}(?:-\d{4})?'),
]

# Get Credentials from environment variables
API_KEY = os.environ.get("GOOGLE_API_KEY")
CSE_ID = os.environ.get("GOOGLE_CSE_ID")

# ====================================

def extract_phones(text):
    """Extract valid phone numbers from text (Global)"""
    phones = set()
    
    for pattern in PHONE_PATTERNS:
        matches = pattern.findall(text)
        for match in matches:
            if isinstance(match, tuple):
                # Skip if it's tuple (from capturing groups)
                continue
            else:
                # Clean up the phone number
                phone = match.strip()
                # Remove extra spaces
                phone = re.sub(r'\s+', ' ', phone)
                
                # Basic validation: must have at least 7 digits
                digit_count = len(re.findall(r'\d', phone))
                if digit_count >= 7 and digit_count <= 15:
                    # Avoid numbers that are too long (likely not phones)
                    if len(phone) <= 25:
                        # Skip common false positives
                        # Skip if it's a date (contains year like 2020, 2024)
                        if not re.search(r'20\d{2}', phone):
                            # Skip if it looks like an ID or code (too many repeating digits)
                            if not re.search(r'(\d)\1{5,}', phone):
                                phones.add(phone)
    
    return list(phones)

def extract_addresses(text):
    """Extract valid addresses from text with improved accuracy (Global)"""
    addresses = set()
    
    # First, try all regex patterns
    for pattern in ADDRESS_PATTERNS:
        matches = pattern.findall(text)
        for match in matches:
            address = match.strip()
            address = re.sub(r'\s+', ' ', address)
            address = address.strip(',').strip()
            
            if 15 <= len(address) <= 200:
                addresses.add(address)
    
    # Enhanced extraction: Look for common address patterns in structured data
    # Schema.org markup
    schema_address = re.findall(r'"streetAddress"\s*:\s*"([^"]+)"[^}]*"addressLocality"\s*:\s*"([^"]+)"[^}]*"addressRegion"\s*:\s*"([^"]+)"[^}]*"postalCode"\s*:\s*"([^"]+)"', text)
    for addr in schema_address:
        full_addr = f"{addr[0]}, {addr[1]}, {addr[2]} {addr[3]}"
        addresses.add(full_addr)
    
    # Microdata format
    microdata_address = re.findall(r'itemprop="streetAddress">([^<]+)</.*?itemprop="addressLocality">([^<]+)</.*?itemprop="addressRegion">([^<]+)</.*?itemprop="postalCode">([^<]+)</span', text, re.DOTALL)
    for addr in microdata_address:
        full_addr = f"{addr[0].strip()}, {addr[1].strip()}, {addr[2].strip()} {addr[3].strip()}"
        addresses.add(full_addr)
    
    # Look for address: label patterns (more aggressive)
    label_patterns = [
        r'(?:Address|Location|Visit us|Find us|Our location|Office|Locate us|Where to find us|Visit|Contact us at|Reach us|Find us at|Our office)[\s:]+([^\n<]{15,200})',
        r'(?:Address|Location)[\s:]+<[^>]*>([^<]{15,200})</[^>]*>',
    ]
    
    for pattern in label_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            address = match.strip()
            address = re.sub(r'\s+', ' ', address)
            address = re.sub(r'<[^>]+>', '', address)  # Remove HTML tags
            
            # Check if it looks like a real address (has number or location keywords)
            if (re.search(r'\d', address) or 
                re.search(r'(?:unit|plot|house|floor|building|shop|office)', address, re.IGNORECASE)) and len(address) > 15:
                addresses.add(address)
    
    # NEW: Look for addresses in common website patterns
    # Pattern: unit/house/shop number + location + city
    location_patterns = [
        r'(?:unit|shop|office|house|plot|flat)\s*(?:no\.?|#)?\s*\d+[,\s]+[^,\n]{10,100}[,\s]+[A-Za-z\s]+(?:Hyderabad|Karachi|Lahore|Mumbai|Delhi|Bangalore|Islamabad|Rawalpindi)',
        r'(?:unit|shop|office)\s*(?:no\.?|#)?\s*\d+[,\s]+[^,]{15,100}',
    ]
    
    for pattern in location_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            address = match.strip()
            address = re.sub(r'\s+', ' ', address)
            if 15 <= len(address) <= 200:
                addresses.add(address)
    
    # NEW: Extract complete sentences that contain location indicators
    location_keywords = r'(?:located in|located at|address is|situated at|situated in|find us at|visit us at|our location|you can find us)'
    location_sentences = re.findall(rf'{location_keywords}[\s:]+([^\n\.!?]{20,200})', text, re.IGNORECASE)
    for sentence in location_sentences:
        address = sentence.strip()
        address = re.sub(r'\s+', ' ', address)
        # Must contain some location indicators
        if re.search(r'(?:street|road|avenue|lane|unit|shop|floor|building|city|area)', address, re.IGNORECASE):
            addresses.add(address)
    
    return list(addresses)

def extract_emails(text):
    """Extract valid emails and filter out fake ones"""
    emails = EMAIL_RE.findall(text)
    # Filter out common fake/example emails
    fake_patterns = ['user@domain', 'example@', 'test@', 'email@example']
    valid_emails = []
    for email in emails:
        email_lower = email.lower()
        if not any(fake in email_lower for fake in fake_patterns):
            valid_emails.append(email)
    return list(set(valid_emails))

def extract_contact_info(text):
    """Extract contact information from text - REMOVED, not used anymore"""
    return [], []

def fetch_page_content(url):
    """Fetch content from a webpage to extract additional information"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        response = requests.get(url, timeout=15, headers=headers, allow_redirects=True)
        if response.status_code == 200:
            # Parse HTML
            soup = BeautifulSoup(response.content, 'lxml')
            
            # Remove script and style elements
            for script in soup(["script", "style", "noscript", "svg"]):
                script.decompose()
            
            # Prioritize contact-related sections
            contact_text = ""
            
            # 1. Look for Schema.org structured data (most reliable)
            schema_scripts = soup.find_all('script', type='application/ld+json')
            for script in schema_scripts:
                contact_text += " " + script.string if script.string else ""
            
            # 2. Look for meta tags with address info
            meta_tags = soup.find_all('meta', attrs={'name': re.compile(r'address|location', re.I)})
            for meta in meta_tags:
                if meta.get('content'):
                    contact_text += " " + meta['content']
            
            # 3. Look for specific address containers
            address_containers = soup.find_all(['div', 'section', 'footer', 'address', 'span', 'p'], 
                                              class_=re.compile(r'address|location|contact|footer|info|locale', re.I))
            for container in address_containers:
                contact_text += " " + container.get_text(separator=' ', strip=True)
            
            # 4. Look for address with itemprop (microdata)
            address_items = soup.find_all(attrs={'itemprop': re.compile(r'address|location', re.I)})
            for item in address_items:
                contact_text += " " + item.get_text(separator=' ', strip=True)
            
            # 5. Look for tel: and mailto: links
            for link in soup.find_all('a', href=True):
                href = link['href']
                if 'tel:' in href or 'mailto:' in href:
                    contact_text += " " + href + " " + link.get_text()
            
            # 6. Get all text as fallback
            full_text = soup.get_text(separator=' ', strip=True)
            
            # Combine prioritized content with full text
            return contact_text + " " + full_text
        return ""
    except Exception as e:
        print(f"Error fetching {url}: {str(e)}")
        return ""

def google_search(query, start=1, num=10):
    """
    Perform Google Custom Search
    start: starting index (1-based)
    num: number of results per page (max 10)
    """
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": API_KEY,
        "cx": CSE_ID,
        "q": query,
        "start": start,
        "num": min(num, 10)
    }
    response = requests.get(url, params=params)
    data = response.json()

    results = []
    items = data.get("items", [])
    total_results = int(data.get("searchInformation", {}).get("totalResults", 0))
    
    for item in items:
        title = item.get("title", "")
        link = item.get("link", "")
        snippet = item.get("snippet", "")
        
        # Initialize sets to store unique values
        all_emails = set()
        all_phones = set()
        all_addresses = set()
        
        # Extract from snippet first
        all_emails.update(extract_emails(snippet))
        all_phones.update(extract_phones(snippet))
        all_addresses.update(extract_addresses(snippet))
        
        # Fetch and parse the actual webpage for more data
        print(f"Fetching page content from: {link}")
        page_content = fetch_page_content(link)
        
        if page_content:
            # Extract from page content
            all_emails.update(extract_emails(page_content))
            all_phones.update(extract_phones(page_content))
            all_addresses.update(extract_addresses(page_content))
        
        results.append({
            "title": title,
            "link": link,
            "emails": list(all_emails)[:10],  # Limit to 10 emails
            "phones": list(all_phones)[:10],  # Limit to 10 phones
            "addresses": list(all_addresses)[:5]  # Limit to 5 addresses
        })
    
    return results, total_results

@app.route("/", methods=["GET", "POST"])
def index():
    results = []
    query = ""
    page = 1
    total_results = 0
    results_per_page = 10
    total_pages = 0
    
    if request.method == "POST":
        query = request.form.get("query")
        page = int(request.form.get("page", 1))
        
        # Calculate start index (Google uses 1-based indexing)
        start = (page - 1) * results_per_page + 1
        
        results, total_results = google_search(query, start=start, num=results_per_page)
        
        # Calculate total pages (Google allows max 100 results)
        max_results = min(total_results, 100)  # Google API limitation
        total_pages = (max_results + results_per_page - 1) // results_per_page
    
    return render_template("index.html", 
                         results=results, 
                         query=query, 
                         page=page, 
                         total_pages=total_pages,
                         total_results=total_results)

@app.route("/download", methods=["POST"])
def download():
    data_format = request.form.get("format")
    query = request.form.get("query")
    page = int(request.form.get("page", 1))
    
    # Get results for current page
    start = (page - 1) * 10 + 1
    results, _ = google_search(query, start=start, num=10)
    
    # Convert lists to strings for export
    for result in results:
        result['emails'] = ', '.join(result['emails'])
        result['phones'] = ', '.join(result['phones'])
        result['addresses'] = ', '.join(result['addresses'])
    
    df = pd.DataFrame(results)

    if data_format == "csv":
        buffer = io.StringIO()
        df.to_csv(buffer, index=False)
        buffer.seek(0)
        return send_file(
            io.BytesIO(buffer.getvalue().encode()),
            mimetype="text/csv",
            as_attachment=True,
            download_name="search_results.csv"
        )

    elif data_format == "excel":
        buffer = io.BytesIO()
        df.to_excel(buffer, index=False, engine='openpyxl')
        buffer.seek(0)
        return send_file(
            buffer,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name="search_results.xlsx"
        )

    elif data_format == "pdf":
        # Render HTML template as PDF
        html = render_template("table_pdf.html", results=results)
        pdf = pdfkit.from_string(html, False)
        return send_file(
            io.BytesIO(pdf),
            mimetype="application/pdf",
            as_attachment=True,
            download_name="search_results.pdf"
        )
    else:
        return "Invalid format", 400

if __name__ == "__main__":
    app.run(debug=True)