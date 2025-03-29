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
credentials = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(credentials)
sheet = client.open(SPREADSHEET_NAME).sheet1

# Helper functions
def fetch_job_text(link):
    try:
        response = requests.get(link, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        body = soup.find("body")
        return body.get_text(separator=" ", strip=True) if body else ""
    except Exception as e:
        print(f"Error fetching job text: {e}")
        return ""

def analyze(job_text, prompt_instruks):
    try:
        # Using the correct method for GPT-4 and setting the prompt
        response = openai.ChatCompletion.create(
            model="gpt-4",  # Make sure to use the GPT-4 model
            messages=[
                {"role": "system", "content": "You are a job evaluator."},
                {"role": "user", "content": f"{prompt_instruks}\n\nJob Posting:\n{job_text}"}
            ],
            temperature=0.5,  # Adjust the randomness level
            max_tokens=150  # Adjust this to control response length
        )
        # Extracting and formatting the response
        output = response['choices'][0]['message']['content'].strip().lower()
        return "Ja" if "ja" in output else "Nej"
    except Exception as e:
        print(f"Error analyzing job posting: {e}")
        return "Fejl"

def start_analyse(prompt_instruks):
    links = sheet.col_values(sheet.find(SE_JOBBET_COL).col)[1:]  # Drop header
    relevant_col = sheet.find(RELEVANT_COL).col
    updates = []

    for idx, link in enumerate(links):
        job_text = fetch_job_text(link)
        vurdering = analyze(job_text, prompt_instruks)
        updates.append([vurdering])
        print(f"{idx+1}/{len(links)} ✅ {link} => {vurdering}")
        time.sleep(1.1)  # Avoid OpenAI throttling

    # Skriv til sheet (batch)
    cell_range = f"{gspread.utils.rowcol_to_a1(2, relevant_col)}:{gspread.utils.rowcol_to_a1(len(updates)+1, relevant_col)}"
    cell_list = sheet.range(cell_range)
    for i, cell in enumerate(cell_list):
        cell.value = updates[i][0]
    sheet.update_cells(cell_list)

    return "Analyse færdig og ark opdateret."

# Endpoint til GPT action
@app.route("/analyser", methods=["POST"])
def analyser():
    data = request.get_json()
    print("🔍 Modtaget data:", data)
    instruks = data.get("instruks", "")
    print(f"Modtog instruks: {instruks}")

    try:
        resultat = start_analyse(instruks)
    except Exception as e:
        import traceback
        print("🚨 Fejl i start_analyse:")
        traceback.print_exc()
        error_response = jsonify({"resultat": "Fejl under analyse"})
        error_response.headers["Content-Type"] = "application/json"
        return error_response, 500

    response = jsonify({"resultat": resultat})
    response.headers["Content-Type"] = "application/json"
    return response

# Flask start
if __name__ == "__main__":
    print("✅ Klar til at modtage instruktioner og analysere jobopslag.")
    app.run(host="0.0.0.0", port=10000)  # Use 10000 to match Render's port binding
