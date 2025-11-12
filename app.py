from flask import Flask, render_template, request, send_file, jsonify
from dotenv import load_dotenv
import os
import requests
import re
import pandas as pd
import io
import pdfkit

# Load .env file
load_dotenv()

app = Flask(__name__)

# Regex for emails and phones
EMAIL_RE = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
PHONE_RE = re.compile(r'\+?\d[\d\-\s]{7,}\d')

# Get Credentials from environment variables
API_KEY = os.environ.get("GOOGLE_API_KEY")
CSE_ID = os.environ.get("GOOGLE_CSE_ID")

# ====================================

def google_search(query, num=10):
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": API_KEY,
        "cx": CSE_ID,
        "q": query,
        "num": min(num, 10)
    }
    response = requests.get(url, params=params)
    data = response.json()

    results = []
    items = data.get("items", [])
    for item in items:
        title = item.get("title", "")
        link = item.get("link", "")
        snippet = item.get("snippet", "")

        emails = list(set(EMAIL_RE.findall(snippet)))
        phones = list(set(PHONE_RE.findall(snippet)))

        results.append({
            "title": title,
            "link": link,
            "snippet": snippet,
            "emails": emails,
            "phones": phones
        })
    return results

@app.route("/", methods=["GET", "POST"])
def index():
    results = []
    query = ""
    if request.method == "POST":
        query = request.form.get("query")
        results = google_search(query)
    return render_template("index.html", results=results, query=query)

@app.route("/download", methods=["POST"])
def download():
    data_format = request.form.get("format")
    query = request.form.get("query")
    results = google_search(query)
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