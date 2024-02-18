import qrcode
import spotipy
import json
import os
from dotenv import load_dotenv
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from spotipy.oauth2 import SpotifyClientCredentials
from reportlab.platypus import Paragraph
from reportlab.lib.styles import getSampleStyleSheet


def generate_qr_code(url, filename):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=0,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    img.save(filename)

def fetch_spotify_data(client_id, client_secret, playlist_url, limit=100, mock_filename=None):
    songs_data = []
    if mock_filename is not None:
        with open(mock_filename, 'r') as file:
            results = json.load(file)
    else:
        client_credentials_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
        #sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=client_id, client_secret=client_secret, scope="playlist-read-private"))
        sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)

        playlist_id = playlist_url.split("/")[-1].split("?")[0]  # Adjust based on your playlist URL format

        results = sp.playlist_items(playlist_id, market="SE", limit=limit)

    for item in results['items']:
        track = item['track']
        artist_name = track['artists'][0]['name']  # Assuming the first artist if there are multiple
        song_title = track['name']
        release_date = track['album']['release_date']  # This gives the release date; you might want just the year
        release_year = release_date.split("-")[0]  # Assuming the format is YYYY-MM-DD

        songs_data.append({
            "artist": artist_name,
            "song": song_title,
            "year": release_year,
            "link": track['external_urls']['spotify']  # Link to the song on Spotify
        })


    return songs_data


def create_pdf(data, filename, row_size=8,):
    # A4 dimensions in landscape
    landscape_A4 = A4[1], A4[0]
    width, height = landscape_A4
    qr_size=30

    # Determine layout
    cards_per_row = row_size
    rows_per_page = 3 # Adjust based on your layout to fit both QR and text comfortably
    cards_per_page = cards_per_row * rows_per_page

    styles = getSampleStyleSheet()
    styles["Normal"].alignment = 1  # 1 is for center alignment

    margin = 5
    card_width = width/cards_per_row
    card_height = height/rows_per_page


    c = canvas.Canvas(filename, pagesize=landscape_A4)

    # Generate pages
    for page_start in range(0, len(data), cards_per_page):
        page_data = data[page_start:page_start + cards_per_page]
        # Front side (QR codes)
        for i, item in enumerate(page_data):
            img_filename = f"tmp/temp_qr_{page_start + i}.png"
            generate_qr_code(item['link'], img_filename)

            x = 0 + (i % cards_per_row) * (width / cards_per_row)
            y = height - 35 - (i // cards_per_row) * card_height
            c.drawImage(img_filename, x + card_width/2 - qr_size*mm/2, y - card_height/2 + qr_size/2, width=qr_size*mm, height=qr_size*mm)
            c.rect(x, y - 150, card_width, card_height)  # Adjust rectangle size for layout

        c.showPage()

        transformed_data = [item for sublist in [page_data[i:i + cards_per_row][::-1] for i in range(0, len(page_data), cards_per_row)]
                            for item in sublist]

        # Back side (Text)
        for i, item in enumerate(transformed_data):
            x = 0 + (i % cards_per_row) * (width / cards_per_row)
            y = height - 35 - (i // cards_per_row) * card_height
            c.rect(x, y - 150, card_width, card_height)  # Adjust rectangle size for layout
            text_lines = [
                f"{item['year']}",
                f"{item['artist']}",
                f"{item['song']}"
            ]
            text_y_start = y - 30

            c.setFontSize(size=30)
            c.drawString(x + 15, text_y_start, item['year'])

            text = f"<b>{item['artist']}</b><br/><br/>{item['song']}"
            p = Paragraph(text, style=styles["Normal"])

            '''p.wrap(card_width - margin*2, card_height)  # Define the required width for wrapping
            p.drawOn(c, x + margin, y - 110)'''

            text_width, text_height = p.wrap(card_width - margin*2, card_height)  # Use card_width for wrap width; height is theoretically maximum

            # Adjust y start position so text appears to start from this y and go downwards
            y_start_position = text_y_start - 20  # Example y start position
            adjusted_y_start = y_start_position - text_height  # Move starting y-coordinate up by the height of the text

            # Draw the paragraph at adjusted position
            p.drawOn(c, x + margin, adjusted_y_start)

            # Check if it's the last item on the current page but not the last item overall
            if i == len(page_data) - 1 and page_start + i + 1 < len(data):
                c.showPage()
    c.save()


limit = 100
row_size = 8
load_dotenv()  # This loads the variables from .env
spotify_id = os.getenv('SPOTIFY_ID')
spotify_secret = os.getenv('SPOTIFY_SECRET')
playlist_data = fetch_spotify_data(spotify_id,
                                   spotify_secret,
                                   "https://open.spotify.com/playlist/37i9dQZF1DX0Ew6u9sRtTY?si=60e601795fec428b",
                                   limit,
                                   "mock_data.json")
create_pdf(playlist_data, "print_me.pdf", row_size)