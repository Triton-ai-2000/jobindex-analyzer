import os
import time
import openai
import gspread
import requests
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify
from oauth2client.service_account import ServiceAccountCredentials

# Setup
app = Flask(__name__)
openai.api_key = os.getenv("OPENAI_API_KEY")

# Google Sheets setup
SPREADSHEET_NAME = "JobindexScraper"
SE_JOBBET_COL = "Se jobbet"
RELEVANT_COL = "Relevant job"

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_name("/etc/secrets/credentials.json", scope)
client = gspread.authorize(credentials)
sheet = client.open(SPREADSHEET_NAME).sheet1

# Helper functions
def fetch_job_text(link):
    try:
        response = requests.get(link, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        body = soup.find("body")
        return body.get_text(separator=" ", strip=True) if body else ""
    except Exception:
        return ""

def analyze(job_text, prompt_instruks):
    try:
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": prompt_instruks},
                {"role": "user", "content": job_text}
            ]
        )
        output = response.choices[0].message.content.strip().lower()
        return "ja" if "ja" in output else "nej"
    except Exception:
        return "fejl"

# Routes
@app.route("/")
def home():
    return "Jobindex Analyzer kører!"

@app.route("/docs")
def docs():
    return jsonify({"message": "API documentation will be here."})

@app.route("/analyze", methods=["POST"])
def analyze_jobs():
    data = request.get_json()
    prompt_instruks = data.get("instructions")
    rows = sheet.get_all_records()
    updates = []

    for i, row in enumerate(rows, start=2):
        link = row.get(SE_JOBBET_COL)
        if not link or row.get(RELEVANT_COL):
            continue
        job_text = fetch_job_text(link)
        vurdering = analyze(job_text, prompt_instruks)
        updates.append((i, vurdering))
        time.sleep(1)

    for row_num, vurdering in updates:
        sheet.update_cell(row_num, sheet.find(RELEVANT_COL).col, vurdering)

    return jsonify({"status": "done", "updated": len(updates)})

if __name__ == "__main__":
    # Ensure Flask uses the right external port for Render
    port = int(os.environ.get("PORT", 5000))  # Default to 5000 if not set
    app.run(host="0.0.0.0", port=port)  # Binding to all addresses and Render's port
