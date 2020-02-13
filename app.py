# Python standard libraries
import json
import os
import sqlite3

# Third-party libraries
from flask import Flask, redirect, request, url_for, render_template
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from oauthlib.oauth2 import WebApplicationClient
import requests

# Internal imports
from db import init_db_command
from user import User

GOOGLE_CLIENT_ID = "409454875993-j40006ejaf85rrpiiasgkd1edab0m63c.apps.googleusercontent.com"

GOOGLE_CLIENT_SECRET = "3zulskJ6lpjzdcZwl8JXykax"

GOOGLE_DISCOVERY_URL = (
    "https://accounts.google.com/.well-known/openid-configuration")

app = Flask(__name__)

app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(24)

# User session management setup
# https://flask-login.readthedocs.io/en/latest
login_manager = LoginManager()
login_manager.init_app(app)

# Naive database setup
try:
    init_db_command()
except sqlite3.OperationalError:
    # Assume it's already been created
    pass

# OAuth 2 client setup
client = WebApplicationClient(GOOGLE_CLIENT_ID)

@app.context_processor
def override_url_for():
    return dict(url_for=dated_url_for)

def dated_url_for(endpoint, **values):
    if endpoint == 'static':
        filename = values.get('filename', None)
        if filename:
            file_path = os.path.join(app.root_path,
                                 endpoint, filename)
            values['q'] = int(os.stat(file_path).st_mtime)
    return url_for(endpoint, **values)

@app.route("/", methods=['Get', 'Post'])
def main():
    return render_template('index.html')


@app.route("/signUp", methods=['Get', 'Post'])
def signUp():
    return render_template('index.html')


@app.route("/logIn", methods=['Get', 'Post'])
def logIn():
    if current_user.is_authenticated:
        return ("<p>Hello, {}! You're logged in! Email: {}</p>"
                "<div><p>Google Profile Picture:</p>"
                '<img src="{}" alt="Google profile pic"></img></div>'
                '<a class="button" href="/logout">Logout</a>'.format(
                    current_user.name, current_user.email,
                    current_user.profile_pic))
    else:
        # Find out what URL to hit for Google login
        google_provider_cfg = get_google_provider_cfg()
        authorization_endpoint = google_provider_cfg["authorization_endpoint"]
        # Use library to construct the request for Google login and provide
        # scopes that let you retrieve user's profile from Google
        request_uri = client.prepare_request_uri(
            authorization_endpoint,
            redirect_uri=request.base_url + "/CallBack",
            scope=["openid", "email", "profile"],
        )
        return redirect(request_uri)


@app.route("/logIn/CallBack")
def callback():
	# Get authorization code Google sent back to you
	code = request.args.get("code")
	google_provider_cfg = get_google_provider_cfg()
	token_endpoint = google_provider_cfg["token_endpoint"]
    # Prepare and send a request to get tokens! Yay tokens!
	token_url, headers, body = client.prepare_token_request(
		token_endpoint,
		authorization_response=request.url,
		redirect_url=request.base_url,
		code=code
	)
	print(token_url)
	token_response = requests.post(
		token_url,
		headers=headers,
		data=body,
		auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
	)
    # Parse the tokens!
	client.parse_request_body_response(json.dumps(token_response.json()))
    # Now that you have tokens (yay) let's find and hit the URL
    # from Google that gives you the user's profile information,
    # including their Google profile image and email
	userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
	uri, headers, body = client.add_token(userinfo_endpoint)
	userinfo_response = requests.get(uri, headers=headers, data=body)
    # You want to make sure their email is verified.
    # The user authenticated with Google, authorized your
    # app, and now you've verified their email through Google!
	if userinfo_response.json().get("email_verified"):
		unique_id = userinfo_response.json()["sub"]
		users_email = userinfo_response.json()["email"]
		picture = userinfo_response.json()["picture"]
		users_name = userinfo_response.json()["given_name"]
	else:
		return "User email not available or not verified by Google.", 400
	# Create a user in your db with the information provided
	# by Google
	user = User(
		id_=unique_id, name=users_name, email=users_email, profile_pic=picture)
	# Doesn't exist? Add it to the database.
	if not User.get(unique_id):
		User.create(unique_id, users_name, users_email, picture)
	# Begin user session by logging the user in
	login_user(user)
	# Send user back to homepage
	return redirect(url_for("logIn"))

@app.route('/classOverview', methods = ['Get', 'Post'])
def stats():
	if request.method == 'POST':
		classes = User.get()
		return render_template('classOverview.html', CLASSES = classes)

@app.route("/privacyPolicy", methods=['Get', 'Post'])
def privPol():
    return render_template('privPol.html')


# Flask-Login helper to retrieve a user from our db
@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)


def get_google_provider_cfg():
    return requests.get(GOOGLE_DISCOVERY_URL).json()


app.run(host='0.0.0.0', port=8080, debug=True)
"""ssl_context='adhoc',"""
