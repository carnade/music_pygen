import qrcode
import spotipy
import json
import os
import random
from dotenv import load_dotenv
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from spotipy.oauth2 import SpotifyClientCredentials
from reportlab.platypus import Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from flask import Flask, request, make_response, render_template
from io import BytesIO

app = Flask(__name__)

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

        results = sp.playlist_items(playlist_id, market="SE")

    random_limit = len(results.get("items")) if len(results.get("items")) < limit else limit

    results_subset = random.sample(results.get("items"), random_limit)

    for item in results_subset:
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


def create_pdf(data, filename=None, row_size=8):
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
    year_style = ParagraphStyle(
        'CustomStyle',
        parent=styles['Normal'],  # Inherit from the 'Normal' style
        fontSize=30,  # Set the font size to 12
        leading=14,  # Set the leading (space between lines) to 14
        alignment=1
    )

    margin = 5
    card_width = width/cards_per_row
    card_height = height/rows_per_page
    pdf_buffer = BytesIO()

    if filename is None:
        # Generate PDF in memory

        c = canvas.Canvas(pdf_buffer, pagesize=landscape_A4)
    else:
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
            text_y_start = y-10

            year_text = f"<b>{item['year']}</b>"
            text = f"<b>{item['artist']}</b><br/><br/>{item['song']}"
            p1 = Paragraph(year_text, style=year_style)
            p2 = Paragraph(text, style=styles["Normal"])

            p1.wrap(card_width - margin * 2, card_height)
            p1.drawOn(c, x, text_y_start)

            text_width, text_height = p2.wrap(card_width - margin*2, card_height)  # Use card_width for wrap width; height is theoretically maximum

            # Adjust y start position so text appears to start from this y and go downwards
            y_start_position = text_y_start - 40  # Example y start position
            adjusted_y_start = y_start_position - text_height  # Move starting y-coordinate up by the height of the text

            # Draw the paragraph at adjusted position
            p2.drawOn(c, x + margin, adjusted_y_start)

            # Check if it's the last item on the current page but not the last item overall
            if i == len(page_data) - 1 and page_start + i + 1 < len(data):
                c.showPage()
    c.save()

    if filename is None:
        # Move the buffer's cursor to the beginning
        pdf_buffer.seek(0)

        # Create a response
        response = make_response(pdf_buffer.getvalue())
        # Set headers to tell the browser to treat the response as a file to download
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = 'inline; filename=playlist_cards.pdf'

        pdf_buffer.close()
        return response
    else:
        pdf_buffer.close()
        return None


@app.route('/')
def home():
    return render_template('form.html')

@app.route('/generate', methods=['POST'])
def generate_cards():
    playlist_url = request.form.get('playlist_url')
    card_limit = request.form.get('card_limit')

    load_dotenv()  # This loads the variables from .env
    spotify_id = os.getenv('SPOTIFY_ID')
    spotify_secret = os.getenv('SPOTIFY_SECRET')
    playlist_data = fetch_spotify_data(spotify_id,
                                       spotify_secret,
                                       playlist_url,
                                       int(card_limit)
                                       #,"mock_data.json"
                                        )
    response = create_pdf(playlist_data, row_size=6)

    return response

if __name__ == '__main__':
    app.run(debug=True)