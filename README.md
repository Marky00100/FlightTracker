# FlightTracker
Hourly pull of flight prices to or near our destination. Get around google flights trying to upsell you. 


FlightTracker App Documentation
Overview

The FlightTracker app is a Flask-based tool that:

    Fetches flight deals from the Amadeus API.

    Updates flight deals hourly using APScheduler.

    Displays the top 5 flight options on a results page (as an HTML table and a Plotly dot plot).

    Optionally sends a weekly email alert with the best deals if the correct password ("marksentme") is provided.

Project Structure

    app.py
    The main Flask application. It contains:

        API authentication and calls to Amadeus.

        The search_flights function (with debug logging) for fetching flight offers.

        Background scheduler jobs for hourly updates and weekly email alerts.

        Routes for the homepage (/) and results page (/results).

    templates/
    A folder containing HTML templates:

        index.html: Displays the form for selecting travel criteria (origin, destination, travel window) and entering email/password.

        results.html: Shows the current top 5 flight deals as a table and an interactive Plotly dot plot.

    keys.txt
    Contains your Amadeus API credentials (API Key and API Secret). This file is added to .gitignore to keep it private.

    requirements.txt
    Lists all the Python dependencies needed for the project.

How It Works
API Keys and Authentication

    Storage: Your Amadeus API credentials are stored in keys.txt (e.g., AMADEUS_API_KEY and AMADEUS_API_SECRET).

    Authentication:
    The get_amadeus_token function sends a POST request to Amadeus’s token endpoint, using these credentials to obtain an access token. This token is then used in subsequent API calls.

Flight Search Function

    Function: search_flights(origin, destination, depart_date, return_date)

    Process:

        Retrieves an access token.

        Constructs an API call to the Amadeus /v2/shopping/flight-offers endpoint with parameters like origin, destination, departure/return dates, etc.

        Debug Logging:
        Prints the request URL, status code, and response text to help troubleshoot any issues.

        Returns flight data if successful, or an empty list otherwise.

Example code snippet:

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

Background Scheduler

    Hourly Updates:
    A job (using APScheduler) runs every hour to call update_deals(), which:

        Uses search criteria from app.config.

        Fetches flight offers.

        Sorts and stores the top 5 deals in the global variable latest_deals.

    Weekly Email Alerts:
    If the user enters the password "marksentme" on the homepage, their email is stored in the session.
    A separate scheduler job sends a weekly email with the best deals (including the final table and dot plot) using Flask-Mail.

Web Routes

    Route / (Index):
    Displays a form with:

        Dropdowns for selecting the travel-from and travel-to countries.

        Date pickers for departure and return dates.

        Fields for email and password.

    On form submission, the search criteria are saved in the app configuration and the user's email is stored for weekly alerts (if the password is correct).

    Route /results:
    Displays:

        A table with the top 5 flight deals (stored in latest_deals).

        An interactive Plotly dot plot showing the best prices (with hover details like layovers and departure times).

How to Run the App

    Clone the Repository

gh repo clone Marky00100/FlightTracker
cd FlightTracker

Create and Activate a Virtual Environment

python3 -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate

Install Dependencies

pip install -r requirements.txt

Set Up Your API Keys

    Create a file named keys.txt in the project root (if it doesn't already exist).

    Add your Amadeus API credentials:

    AMADEUS_API_KEY=PRzapSzCfvU6LyYQ4Tbyo7tsYTBu7qYu
    AMADEUS_API_SECRET=zXHcVE2C03AEbE2J

Run the Flask App

    python app.py

        The app will start in development mode at http://127.0.0.1:5000.

    Usage

        Navigate to the homepage.

        Enter your travel details, select your origin/destination, and provide your email.

        Click "Start Tracking" to begin.

        View results on the /results page.

        If you provided the password "marksentme", you'll receive a weekly email with your best deals.

Debugging and Logs

    The search_flights function prints key information (Request URL, HTTP status, and Response) to the console.
    Use these logs to identify issues with the Amadeus API calls (e.g., 404 errors).

    The console output will also display debug messages from Flask and APScheduler.

Additional Notes

    Favicon 404:
    A 404 error for /favicon.ico is normal if you haven't provided one.

    Development vs. Production:
    This app is set up for development. For production deployment, use a production WSGI server and secure your configurations (e.g., use environment variables for secrets).

    GitHub Repository:
    Your API keys are stored in keys.txt, which is listed in .gitignore so it isn’t pushed to GitHub.

This file contains detailed explanations on where everything is stored, how to run the app, and how the code works. Save this in Obsidian for future reference.
