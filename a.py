from flask import Flask, redirect, url_for, render_template, session, flash, request, jsonify
import requests

from datetime import datetime
import urllib.parse

app = Flask(__name__)
app.secret_key = 'vp'


CLIENT_ID ='93f8fe1ef0bf46358b35036ff3cdd731'
CLIENT_SECRET = '18f97ca20a8549b39039e5f452a4e11c'
REDIRECT_URI = 'http://127.0.0.1:5000/callback'

AUTH_URL = 'https://accounts.spotify.com/authorize'
TOKEN_URL = 'https://accounts.spotify.com/api/token'
API_BASE_URL = 'https://api.spotify.com/v1/'




@app.route("/login")
def login():
    scope = 'user-read-private user-read-email playlist-read-collaborative playlist-modify-public playlist-modify-private user-top-read'    

    params = {
        'client_id': CLIENT_ID,
        'response_type' : 'code',
        'scope': scope, 
        'redirect_uri' : REDIRECT_URI,
        'show_dialog' : True  
    }

    auth_url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"

    return redirect(auth_url)
   
@app.route('/refresh-token')
def refresh_token():
    if 'refresh_token' not in session:
        return redirect('/login')

    req_body = {
        'grant_type': 'refresh_token',
        'refresh_token': session['refresh_token'],
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET
    }

    response = requests.post(TOKEN_URL, data=req_body)
    
    if response.status_code != 200:
        return f"Failed to refresh token: {response.status_code} - {response.text}", 500

    new_token_info = response.json()

    if 'access_token' in new_token_info:
        session['access_token'] = new_token_info['access_token']
        session['expires_at'] = datetime.now().timestamp() + new_token_info.get('expires_in', 3600)

    return redirect('/playlists')  

@app.route("/callback")
def callback():
    if 'error' in request.args: #if there is an issue in spotify request, return error
        return jsonify({'error': request.args['error']})

    if 'code' in request.args: 
        req_body = {
            'code' : request.args['code'],
            'grant_type' : 'authorization_code',
            'redirect_uri' : REDIRECT_URI,
            'client_id' : CLIENT_ID,
            'client_secret' : CLIENT_SECRET
        }

        response = requests.post(TOKEN_URL, data=req_body)
        token_info = response.json()

        session['access_token'] = token_info['access_token'] #used to make requests to spotify 
        session['refresh_token'] = token_info['refresh_token'] #used to refresh access token when it expires
        session['expires_at'] = datetime.now().timestamp() + token_info['expires_in'] #how long token lasts for (1 day).

        return redirect('/home')

@app.route('/logout') 
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route('/home')
def home():
    return render_template('home.html')

    
@app.route('/playlists')
def get_playlists():
    
    if 'access_token' not in session:# Check if token exists
        return redirect('/login')

    if datetime.now().timestamp() > session['expires_at']: #Check if token is expired
        return redirect('/refresh-token')

    headers = {
        'Authorization': f"Bearer {session['access_token']}"
    }
    response = requests.get(API_BASE_URL + 'me/playlists', headers=headers)

    
    if response.status_code != 200: # Handles errors
        return f"Spotify API error: {response.status_code} - {response.text}", 500

    data = response.json()

   
    playlists = [ #Get playlist info
        {
        'name': pl['name'], 
        'url': pl['external_urls']['spotify'],
        'image': pl['images'][0]['url'] if pl['images'] else None
        }
        for pl in data.get('items', [])
    ]

    return render_template('playlists.html', playlists=playlists)

    
@app.route("/play", methods=['GET', 'POST'])
def play():
    if 'access_token' not in session:
        return redirect('/login')

    if datetime.now().timestamp() > session['expires_at']:
        return redirect('/refresh-token')

    token = session["access_token"]
    headers = {
        "Authorization": f"Bearer {token}",
    }
    limit= 5
    resp = requests.get(f'https://api.spotify.com/v1/me/top/artists?limit={limit}', headers=headers)
    top_artists= resp.json()
    return render_template('play.html', favs=top_artists['items'])


@app.route("/create", methods=['GET', 'POST'])
def create_playlist():
    if 'access_token' not in session:
        return redirect('/login')

    if datetime.now().timestamp() > session['expires_at']:
        return redirect('/refresh-token')

    token = session["access_token"]

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    if request.method == 'POST':
        # Grabbing info from user input
        playlist_name = request.form.get("playlist_name", "").strip()
        description = request.form.get("description", "").strip()
        public = "public" in request.form

        if not playlist_name:
            return render_template("create.html", message="Playlist name is required.")

        # Get user ID from Spotify
        user_resp = requests.get("https://api.spotify.com/v1/me", headers=headers)
        if user_resp.status_code != 200:
            return f"Failed to get user profile: {user_resp.status_code} - {user_resp.text}"

        user_id = user_resp.json().get("id")
        if not user_id:
            return "Failed to retrieve Spotify user ID."

        # Create playlist
        url = f"https://api.spotify.com/v1/users/{user_id}/playlists"
        data = {
            "name": playlist_name,
            "public": public,
            "description": description
        }

        response = requests.post(url, headers=headers, json=data)

        if response.status_code == 201:
            return render_template('create.html', message="Playlist created!")
        else:
            return redirect('/login')
            # return f"Error: {response.status_code} - {response.text}"

    return render_template("create.html")



if __name__ == "__main__":
    app.run(debug=True)
