#!/usr/bin/env python3
from flask import Flask, render_template, request, redirect, url_for, session
import requests, datetime, os, pandas as pd
from apscheduler.schedulers.background import BackgroundScheduler
import plotly.express as px
from flask_mail import Mail, Message

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Change this

# --- Mail Config (example using Gmail SMTP) ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USERNAME'] = 'your_email@gmail.com'
app.config['MAIL_PASSWORD'] = 'your_email_password'
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
mail = Mail(app)

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
    if r.status_code == 200:
        return r.json().get("data", [])
    return []

# --- Global Storage for Latest Deals ---
latest_deals = []

# --- Scheduler Job: Update Flight Deals Hourly ---
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
scheduler.add_job(func=update_deals, trigger="interval", hours=1)
scheduler.start()

# --- Weekly Email Alert ---
def send_weekly_email():
    alert_email = session.get("alert_email")
    if not alert_email:
        return
    deals = latest_deals
    if not deals:
        return
    rows = []
    for offer in deals:
        price = offer.get("price", {}).get("total", "N/A")
        itin = offer.get("itineraries", [])
        layovers = []
        if itin:
            segments = itin[0].get("segments", [])
            for seg in segments:
                layovers.append(seg.get("departure", {}).get("iataCode", ""))
        rows.append({"Price": float(price) if price != "N/A" else None,
                     "Layovers": ", ".join(layovers)})
    df = pd.DataFrame(rows)
    fig = px.scatter(df, x="Price", y=[0]*len(df), hover_data=["Layovers"])
    plot_html = fig.to_html(full_html=False)
    msg = Message("Weekly Flight Deals", sender=app.config['MAIL_USERNAME'], recipients=[alert_email])
    msg.body = "Your best flight deals for the week:\n" + df.to_html()
    msg.html = f"<p>Flight Deals:</p>{df.to_html()}<p>{plot_html}</p>"
    mail.send(msg)

scheduler.add_job(func=send_weekly_email, trigger="cron", day_of_week="fri", hour=17)

# --- Routes ---
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        origin_country = request.form.get("origin_country")
        destination_country = request.form.get("destination_country")
        depart_date = request.form.get("depart_date")
        return_date = request.form.get("return_date")
        email = request.form.get("email")
        password = request.form.get("password")
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
        if password == "marksentme":
            session["alert_email"] = email
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

