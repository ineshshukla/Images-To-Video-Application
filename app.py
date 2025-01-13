# from flask import Flask, render_template, request, redirect
from flask import *
import os
import psycopg2 as sql
from flask_jwt_extended import JWTManager, create_access_token, get_jwt_identity, jwt_required, set_access_cookies
import base64
import json
from moviepy.editor import AudioFileClip, ImageClip, concatenate_videoclips
from moviepy.video.fx.all import fadein, fadeout
import io
import tempfile
import cv2
import numpy as np
import requests
from datetime import timedelta

# Download the certificate
cert_url = 'https://cockroachlabs.cloud/clusters/13616b57-985f-46bd-bf8e-a0fb8b5e2944/cert'
response = requests.get(cert_url)

# Save the certificate
cert_path = os.path.join(os.getenv('HOME'), '.postgresql', 'root.crt')
os.makedirs(os.path.dirname(cert_path), exist_ok=True)
with open(cert_path, 'wb') as cert_file:
    cert_file.write(response.content)

# initialise the table
conn = sql.connect(
    os.environ["DATABASE_URL"],
    sslmode='require',
    sslrootcert=cert_path
)
cursor = conn.cursor()

audio_files = ['static/cityOfStars.mp3', 'static/Evergreen.mp3', 'static/Freaks.mp3'] 

# with open('project.sql') as f:
#     cursor.execute(f.read().replace('\n', ' '))

create_user_details_query = """
CREATE TABLE IF NOT EXISTS user_details (
    user_id SERIAL PRIMARY KEY,
    user_name VARCHAR(50) NOT NULL,
    user_email VARCHAR(50) NOT NULL,
    user_password VARCHAR(50) NOT NULL
)
"""
cursor.execute(create_user_details_query)
conn.commit()

create_images_query = """
CREATE TABLE IF NOT EXISTS images (
    image_id SERIAL PRIMARY KEY,
    user_id INT,
    image BYTEA,
    image_metadata VARCHAR(150),
    FOREIGN KEY (user_id) REFERENCES user_details(user_id)
)
"""
cursor.execute(create_images_query)
conn.commit()

create_audio_query = """
CREATE TABLE IF NOT EXISTS audio (
    audio_id SERIAL PRIMARY KEY,
    audio BYTEA,
    audio_metadata VARCHAR(50)
)
"""
cursor.execute(create_audio_query)
conn.commit()

cursor.execute("SHOW TABLES")
print(cursor.fetchall())

# check if table audio exists
cursor.execute("SELECT audio_id FROM audio")
exists = cursor.fetchall()
print(exists)
if not exists:
    for audio_file in audio_files:
        with open(audio_file, 'rb') as file:
            audio_data = file.read()
        insert_query = "INSERT INTO audio (audio, audio_metadata) VALUES (%s, %s)"
        cursor.execute(insert_query, (audio_data, audio_file))
        conn.commit()

def resize_with_black_fill(frame, output_width, output_height):
    h, w = frame.shape[:2]
    aspect_ratio = w / h
    
    if aspect_ratio > output_width / output_height:
        new_w = output_width
        new_h = int(new_w / aspect_ratio)
    else:
        new_h = output_height
        new_w = int(new_h * aspect_ratio)
    
    resized_frame = cv2.resize(frame, (new_w, new_h))
    black_filled_frame = np.zeros((output_height, output_width, 3), dtype=np.uint8)
    y_offset = (output_height - new_h) // 2
    x_offset = (output_width - new_w) // 2
    black_filled_frame[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = resized_frame
    
    return black_filled_frame

def create_video(image_transitions, audio, height, width, quality):
    # Create a list to hold the clips
    clips = []
    # Loop through each item in the list
    for i, item in enumerate(image_transitions):
        # Split the item into type and value
        item_type, item_value = item.split(':', 1)

        # If the item is an image, create an ImageClip
        if item_type == 'img':
            image_id, duration = item_value.split(':')
            duration = int(duration[:-1])  # Remove the 's' and convert to int
            cursor.execute('select image from images where image_id = %s', (image_id,))
            image_data = cursor.fetchone()[0]
            # Create a byte stream from the blob data
            byte_stream = io.BytesIO(image_data)

            # Create a temporary file and write the byte stream to it
            temp_file = tempfile.NamedTemporaryFile(delete=False)
            temp_file.write(byte_stream.read())
            temp_file.close()

            # Create the ImageClip object
            img = cv2.imread(temp_file.name)
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)  # Convert color space from BGR to RGB
            img_resized = resize_with_black_fill(img, width, height)  # Assuming the output video size is 1920x1080
            clip = ImageClip(img_resized, duration=duration)
            # If the previous item was a 'fadein' transition, apply it to this clip
            if i > 0: 
                if image_transitions[i-1] == 'trn:FadeIn':
                    clip = fadein(clip, 0.5)  # 0.5 second fade-in
                # elif image_transitions[i-1] == 'trn:CrossFadeIn':
                #     clips[-1] = clips[-1].crossfadein(0.5)
            clips.append(clip)

        # If the item is a transition, apply it to the last clip
        elif item_type == 'trn' and clips:
            if item_value == 'FadeOut':
                clips[-1] = fadeout(clips[-1], 0.5)  # 0.5 second fade-out
            # elif item_value == 'CrossFadeOut':
            #     clips[-1] = clips[-1].crossfadeout(0.5)

    # Concatenate all clips into a single video
    final_clip = concatenate_videoclips(clips)

    # Add background music
    # audio = AudioFileClip('cityOfStars.mp3')

    if audio:
        # If the audio duration is longer than the video duration, subclip the audio
        if audio.duration > final_clip.duration:
            audio = audio.subclip(0, final_clip.duration)

        final_clip = final_clip.set_audio(audio)

    # # Write the video file
    # final_clip.write_videofile('output_video.mp4', codec='libx264', fps=24)

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=True) as temp:
        final_clip.write_videofile(temp.name, fps=24, bitrate=quality)  # specify fps according to your needs
        temp.seek(0)  # go back to the beginning of the file
        video_bytes = temp.read()

    return video_bytes


app = Flask(__name__)

# initialise jwt
app.config['JWT_SECRET_KEY'] = 'b7d2c83e86f44a8f8b8e33ba26c8c82c'
app.config['JWT_TOKEN_LOCATION'] = ['cookies']
app.config['ACCESS_COOKIE_PATH'] = '/app/'
app.config['JWT_COOKIE_CSRF_PROTECT'] = False
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)

jwt = JWTManager(app)


@app.route('/')
def index():
    return render_template('login/index.html')

@app.route('/login')
def login():
    return render_template('login/loginPage.html')

@app.route('/signup')
def signup():
    return render_template('login/signupPage.html')

@app.route('/login', methods=['POST'])
def login_post():
    email = request.form['username']
    password = request.form['password']
    cursor.execute('select * from user_details where user_name = %s AND user_password = %s', (email, password))
    user = cursor.fetchone()
    # check if user is admin
    print(user)
    if user and user[1] == 'admin':
        access_token = create_access_token(identity=user[0])
        response = make_response(redirect('/app/admin'))
        set_access_cookies(response, access_token)
        response.set_cookie('access_token', access_token, httponly=True)
        return response
    elif user:
        access_token = create_access_token(identity=user[0])
        response = make_response(redirect('/app/home'))
        set_access_cookies(response, access_token)
        response.set_cookie('access_token', access_token, httponly=True)
        return response
    else:
        return redirect('/')

@app.route('/signup', methods=['POST'])
def signup_post():
    email = request.form['email']
    user_name = request.form['username']
    password = request.form['password']
    # cursor.execute('insert into users(user_email, user_name, user_password) values(%s, %s, %s)', (email, user_name, password))
    # conn.commit()
    insert_query = """
    INSERT INTO user_details (user_name, user_email, user_password)
    VALUES (%s, %s, %s)
    """
    user_data = (user_name, email, password)
    cursor.execute(insert_query, user_data)
    conn.commit()

    return redirect('/login')

@app.route('/app/admin')
@jwt_required()
def admin():
    if 'access_token' in request.cookies:
        # get user id from access token
        user_id = get_jwt_identity()
        if user_id == 1:
            cursor.execute('select * from user_details')
            users = cursor.fetchall()
            output = ''
            for user in users:
                output += f'<div class="w-full p-4"><div class="bg-white p-4 rounded-lg shadow-lg"><h2 class="text-2xl font-bold text-gray-800">{user[1]}</h2><h2 class="text-1xl font-bold text-gray-800">{user[2]}</h2></div></div>'
            return render_template('admin/index.html', users=output)
        else:
            return redirect('/app/home')
    else:
        return redirect('/login')

@app.route('/app/home')
@jwt_required()
def home():
    if 'access_token' in request.cookies:
        # get user id from access token
        user_id = get_jwt_identity()
        # get image_id's, image_metadata, image_metadata from images where user_id matches
        cursor.execute('select * from images where user_id = %s', (user_id,))
        images = cursor.fetchall()

        cursor.execute('select user_name, user_email from user_details where user_id = %s', (user_id,))
        username, email = cursor.fetchone()

        images_code = ''
        for image in images:
            format_image = image[3].split('.')[-1]
            blob_data = base64.b64encode(image[2]).decode('utf-8')
            # get blob data from image[2] and metadata from image[3]
            images_code += f'<div class="img-container"><input id="{image[0]}" class="checkbox" type="checkbox" name="photo"><label for="photo"><img src="data:image/{format_image};base64,{blob_data}" alt="{image[3]}" id="{image[0]}"></label></div>'
        return render_template('home-page/index.html', images=images_code, username=username, email=email)
    else:
        return redirect('/login')

@app.route('/app/upload', methods=['POST'])
@jwt_required()
def upload():
    if 'access_token' in request.cookies:
        user_id = get_jwt_identity()
        file = request.files['file']
        file_data = file.read()
        cursor.execute('insert into images(user_id, image, image_metadata) values(%s, %s, %s)', (user_id, file_data, file.filename))
        conn.commit()
        # get image_id's, image_metadata, image_metadata from images where user_id matches
        cursor.execute('select * from images where user_id = %s', (user_id,))
        images = cursor.fetchall()

        cursor.execute('select user_name, user_email from user_details where user_id = %s', (user_id,))
        username, email = cursor.fetchone()

        images_code = ''
        for image in images:
            format_image = image[3].split('.')[-1]
            blob_data = base64.b64encode(image[2]).decode('utf-8')
            # get blob data from image[2] and metadata from image[3]
            images_code += f'<div class="img-container"><label for="photo"><img src="data:image/{format_image};base64,{blob_data}" alt="{image[3]}" id="{image[0]}"></label><input id="{image[0]}" class="checkbox" type="checkbox" name="photo"></div>'
        return render_template('home-page/index.html', images=images_code, username=username, email=email)
    else:
        return redirect('/login')
    
@app.route('/app/logout')
@jwt_required()
def logout():
    access_token = create_access_token(identity="")
    response = make_response(redirect('/app/home'))
    response.set_cookie('access_token', access_token, httponly=True, max_age=0)
    return response

@app.route('/app/create', methods=['POST'])
@jwt_required()
def create():
    if 'access_token' in request.cookies:
        user_id = get_jwt_identity()
        ids = json.loads(request.form['images'])
        images_code = ''
        for i in ids:
            cursor.execute('select * from images where image_id = %s and user_id = %s', (str(i),user_id))
            image = cursor.fetchone()
            if image: 
                format_image = image[3].split('.')[-1]
                blob_data = base64.b64encode(image[2]).decode('utf-8')
                images_code += f"<img src='data:image/{format_image};base64,{blob_data}' alt='{image[3]}' id='{image[0]}' class='h-auto rounded aspect-square min-w-full' draggable='true'>"
        return render_template('editor/index.html', images=images_code)
    else:
        return redirect('/login')

@app.route('/app/preview', methods=['POST'])
@jwt_required()
def preview():
    if 'access_token' in request.cookies:
        timeline = request.form['timeline']
        timeline = json.loads(timeline)
        audio_id = request.form['audio']
        height = int(request.form['height'])
        width = int(request.form['width'])
        quality = request.form['quality']
        if int(audio_id) > 0:
            cursor.execute('select audio from audio where audio_id = %s', (audio_id,))
            audio_data = cursor.fetchone()[0]
            # Create a byte stream from the blob data
            byte_stream = io.BytesIO(audio_data)

            # Create a temporary file and write the byte stream to it
            temp_file = tempfile.NamedTemporaryFile(delete=True)
            temp_file.write(byte_stream.read())

            # Create the AudioFileClip object
            audio_clip = AudioFileClip(temp_file.name)
            temp_file.close()
        else: audio_clip = None

        video = create_video(timeline, audio_clip, height, width, quality)
        return Response(video, mimetype='video/mp4')
    else:
        return redirect('/login')

@app.route('/templates/<path:path>')
def send_template(path):
    return send_from_directory('templates', path)

@app.route('/app/get_audio_files')
@jwt_required()
def get_audio_files():
    cursor = conn.cursor()
    cursor.execute("SELECT audio_id, audio_metadata FROM audio")
    audio_files = cursor.fetchall()
    print(audio_files[0])
    audio_options = [{'id': str(audio[0]), 'name': audio[1].split('/')[1].split('.')[0]} for audio in audio_files]
    return jsonify(audio_options)

if __name__ == '__main__':
    app.run(debug=False, port=5000)