#!/usr/bin/env python3
from flask import Flask, render_template, request, redirect, url_for, session
import requests, datetime, os, pandas as pd
from apscheduler.schedulers.background import BackgroundScheduler
import plotly.express as px

app = Flask(__name__)
app.secret_key = 'your_secure_secret_key'  # Change this

# --- Load API Keys from keys.txt ---
def load_api_keys():
    keys = {}
    with open('keys.txt', 'r') as f:
        for line in f:
            if '=' in line:
                key, val = line.strip().split('=', 1)
                keys[key.strip()] = val.strip()
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
    r = requests.post(url, data=payload, headers=headers)
    if r.status_code == 200:
        return r.json().get("access_token")
    return None

def search_flights(origin, destination, depart_date, return_date):
    token = get_amadeus_token()
    if not token:
        print("Failed to retrieve token")
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
    r = requests.get(url, params=params, headers=headers)
    print("Request URL:", r.url)
    print("Status Code:", r.status_code)
    print("Response:", r.text)
    if r.status_code == 200:
        return r.json().get("data", [])
    return []

# --- Global Storage for Latest Deals ---
latest_deals = []

# --- Scheduler Job: Update Flight Deals Every 5 Minutes ---
def update_deals():
    criteria = app.config.get("SEARCH_CRITERIA")
    if not criteria:
        return
    origin = criteria.get("origin")
    destination = criteria.get("destination")
    depart_date = criteria.get("depart_date")
    return_date = criteria.get("return_date")
    deals = search_flights(origin, destination, depart_date, return_date)
    # Sort by total price and take top 5
    def get_price(offer):
        try:
            return float(offer['price']['total'])
        except:
            return float('inf')
    deals_sorted = sorted(deals, key=get_price)
    global latest_deals
    latest_deals = deals_sorted[:5]

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

if __name__ == "__main__":
    app.run(debug=True)

