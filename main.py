import os
import time
import gspread
import requests
from openai import OpenAI
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify
from oauth2client.service_account import ServiceAccountCredentials

# Setup
app = Flask(__name__)
openai.api_key = os.getenv("OPENAI_API_KEY")
# client = OpenAI(api_key=api_key)  # Create OpenAI client instance

# Print debug info at startup
print(f"API key available: {'Yes' if api_key else 'No'}")
if not api_key:
    print("WARNING: OpenAI API key not found in environment variables")

# Google Sheets setup
SPREADSHEET_NAME = "JobindexScraper"  # The name of the Google Sheet
SE_JOBBET_COL = "Se jobbet"
RELEVANT_COL = "Relevant job"

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_name("/etc/secrets/credentials.json", scope)
gc = gspread.authorize(credentials)

# Update sheet reference with the correct sheet name (case-sensitive)
sheet = gc.open(SPREADSHEET_NAME).worksheet("Sheet1")  # Replace "Sheet1" with the actual sheet name if needed

# Helper functions
def fetch_job_text(link):
    try:
        print(f"Fetching job text from: {link}")
        response = requests.get(link, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        body = soup.find("body")
        text = body.get_text(separator=" ", strip=True) if body else ""
        
        print(f"Fetched text length: {len(text)} characters")
        if not text:
            print("Warning: Empty text fetched from job posting")
            
        return text
    except Exception as e:
        print(f"Error fetching job text: {str(e)}")
        return ""

def analyze(job_text, prompt_instruks):
    if not job_text or len(job_text) < 10:
        print("Job text too short to analyze meaningfully")
        return "fejl"
        
    try:
        print(f"Processing job text: {job_text[:100]}...")  # Print first 100 chars
        print(f"Using prompt instructions: {prompt_instruks[:100]}...")
        
        # Using the client instance properly with the new SDK
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": prompt_instruks},
                {"role": "user", "content": job_text}
            ],
            max_tokens=50  # Limit response size for efficiency
        )
        
        output = response.choices[0].message.content.strip().lower()
        print(f"Analysis output: {output}")
        
        # More robust detection of "ja"
        if "ja" in output or "yes" in output or "relevant" in output:
            return "ja"
        else:
            return "nej"
            
    except Exception as e:
        print(f"Error analyzing job posting: {type(e).__name__}: {str(e)}")
        return "fejl"
        
# Routes
@app.route("/")  
def home():
    return "Jobindex Analyzer kører!"  
    
@app.route("/check-env")
def check_env():
    api_key = os.getenv("OPENAI_API_KEY")
    return jsonify({
        "api_key_available": bool(api_key),
        "api_key_preview": api_key[:3] + "..." if api_key else None
    })
    
@app.route("/docs")
def docs():
    return jsonify({"message": "API documentation will be here."})
                
@app.route("/analyze", methods=["POST"])
def analyze_jobs():
    data = request.get_json()
    print(f"Received data: {data}")
    
    prompt_instruks = data.get("instructions")
    if not prompt_instruks:
        print("Warning: Empty instructions received")
        return jsonify({"error": "No instructions provided"}), 400
        
    print(f"Received instructions: {prompt_instruks}")
    
    rows = sheet.get_all_records()
    print(f"Found {len(rows)} rows in sheet")
    updates = []
        
    for i, row in enumerate(rows, start=2):
        link = row.get(SE_JOBBET_COL)
        if not link or row.get(RELEVANT_COL):
            continue
            
        print(f"\n{i-1}/{len(rows)} Processing: {link}")
        job_text = fetch_job_text(link)
        
        if not job_text:
            print("Skipping due to empty job text")
            continue
            
        vurdering = analyze(job_text, prompt_instruks)
        print(f"Analysis result: {vurdering}")
        updates.append((i, vurdering))
        time.sleep(1)
    
    print(f"Updating {len(updates)} rows in sheet")
    for row_num, vurdering in updates:
        col_num = sheet.find(RELEVANT_COL).col
        print(f"Updating row {row_num}, column {col_num} with value: {vurdering}")
        sheet.update_cell(row_num, col_num, vurdering)

    return jsonify({"status": "done", "updated": len(updates)})
    
@app.route("/test-openai", methods=["GET"])
def test_openai():
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say 'ja' or 'nej' randomly."}
            ]
        )
        result = response.choices[0].message.content
        return jsonify({"status": "success", "response": result})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    
if __name__ == "__main__":
    # Ensure Flask uses the right external port for Render
    port = int(os.environ.get("PORT", 10000))  # Default to 10000 if not set
    app.run(host="0.0.0.0", port=port)  # Binding to all addresses and Render's port
