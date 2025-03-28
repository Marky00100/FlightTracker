#!/usr/bin/env python3
import os
import requests, datetime, pandas as pd
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
import plotly.express as px

# Optionally load environment variables from a .env file (install python-dotenv if needed)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = Flask(__name__)
app.secret_key = os.environ.get("APP_SECRET", "your_secure_secret_key")  # Change this!

# Global log list for active readout
log_messages = []

def add_log(message):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] {message}"
    log_messages.append(entry)
    # Limit logs to last 100 entries
    if len(log_messages) > 100:
        del log_messages[0:len(log_messages)-100]
    print(entry)

# --- Load API Keys from keys.txt ---
def load_api_keys():
    keys = {}
    try:
        with open('keys.txt', 'r') as f:
            for line in f:
                if '=' in line:
                    key, val = line.strip().split('=', 1)
                    keys[key.strip()] = val.strip()
        add_log("Loaded API keys from keys.txt.")
    except Exception as e:
        add_log(f"Error loading keys.txt: {e}")
    return keys

api_keys = load_api_keys()
AMADEUS_API_KEY = api_keys.get('AMADEUS_API_KEY')
AMADEUS_API_SECRET = api_keys.get('AMADEUS_API_SECRET')

# --- Amadeus Token & Flight Search ---
def get_amadeus_token():
    url = "https://test.api.amadeus.com/v1/security/oauth2/token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": AMADEUS_API_KEY,
        "client_secret": AMADEUS_API_SECRET
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    try:
        r = requests.post(url, data=payload, headers=headers)
        add_log(f"Token request status: {r.status_code}")
        if r.status_code == 200:
            token = r.json().get("access_token")
            add_log("Retrieved Amadeus token.")
            return token
        else:
            add_log(f"Failed to get token: {r.text}")
    except Exception as e:
        add_log(f"Exception in get_amadeus_token: {e}")
    return None

def search_flights(origin, destination, depart_date, return_date):
    token = get_amadeus_token()
    if not token:
        add_log("Token retrieval failed in search_flights.")
        return []
    url = "https://test.api.amadeus.com/v2/shopping/flight-offers"
    params = {
        "originLocationCode": origin,
        "destinationLocationCode": destination,
        "departureDate": depart_date,
        "returnDate": return_date,
        "adults": 1,
        "max": 50
    }
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(url, params=params, headers=headers)
        add_log(f"Flight search: {r.url} Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json().get("data", [])
            add_log(f"Found {len(data)} flight offers.")
            return data
        else:
            add_log(f"Flight search error: {r.text}")
    except Exception as e:
        add_log(f"Exception in search_flights: {e}")
    return []

# --- Global Storage for Latest Deals ---
latest_deals = []

# --- Scheduler Job: Update Flight Deals Every 5 Minutes ---
def update_deals():
    criteria = app.config.get("SEARCH_CRITERIA")
    if not criteria:
        add_log("No search criteria set; skipping update.")
        return
    origin = criteria.get("origin")
    destination = criteria.get("destination")
    depart_date = criteria.get("depart_date")
    return_date = criteria.get("return_date")
    add_log(f"Updating deals for {origin} -> {destination} from {depart_date} to {return_date}.")
    deals = search_flights(origin, destination, depart_date, return_date)
    def get_price(offer):
        try:
            return float(offer['price']['total'])
        except:
            return float('inf')
    deals_sorted = sorted(deals, key=get_price)
    global latest_deals
    latest_deals = deals_sorted[:5]
    add_log(f"Updated latest deals: {len(latest_deals)} deals stored.")

scheduler = BackgroundScheduler()
scheduler.add_job(func=update_deals, trigger="interval", minutes=5)
scheduler.start()

# --- Routes ---
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        origin_country = request.form.get("origin_country")
        destination_country = request.form.get("destination_country")
        depart_date = request.form.get("depart_date")
        return_date = request.form.get("return_date")
        # Map countries to default airport codes
        airport_map = {
            "USA": "CLE",
            "Ireland": "DUB",
            "United Kingdom": "EDI",
            "France": "CDG",
            "Germany": "FRA"
        }
        origin = airport_map.get(origin_country, "CLE")
        destination = airport_map.get(destination_country, "DUB")
        app.config["SEARCH_CRITERIA"] = {
            "origin": origin,
            "destination": destination,
            "depart_date": depart_date,
            "return_date": return_date
        }
        add_log(f"Search criteria set: {origin} -> {destination} from {depart_date} to {return_date}.")
        update_deals()  # Immediate update on form submit
        return redirect(url_for("results"))
    return render_template("index.html")

@app.route("/results")
def results():
    deals = latest_deals
    if deals:
        rows = []
        for offer in deals:
            price = offer.get("price", {}).get("total", "N/A")
            itin = offer.get("itineraries", [])
            layovers = []
            dep_time = "N/A"
            if itin and itin[0].get("segments"):
                segments = itin[0]["segments"]
                for seg in segments:
                    layovers.append(seg.get("departure", {}).get("iataCode", ""))
                dep_time = segments[0].get("departure", {}).get("at", "N/A")
            rows.append({"Price": float(price) if price != "N/A" else None,
                         "Layovers": ", ".join(layovers),
                         "Departure": dep_time})
        df = pd.DataFrame(rows)
        fig = px.scatter(df, x="Price", y=[0]*len(df), hover_data=["Layovers", "Departure"])
        plot_div = fig.to_html(full_html=False)
    else:
        df = pd.DataFrame()
        plot_div = ""
    return render_template("results.html", table=df.to_html(classes="table table-striped"), plot_div=plot_div)

@app.route("/logs")
def logs():
    # Return the current log messages as JSON
    return jsonify(log_messages)

@app.route("/manual_refresh")
def manual_refresh():
    update_deals()
    return redirect(url_for("results"))

@app.route("/test_api")
def test_api():
    # Hardcoded test values for API testing
    origin = "CLE"
    destination = "DUB"
    depart_date = "2025-06-15"
    return_date = "2025-06-20"
    results = search_flights(origin, destination, depart_date, return_date)
    return {"results": results}

if __name__ == "__main__":
    app.run(debug=True)

