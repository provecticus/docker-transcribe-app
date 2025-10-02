from flask import Flask, request, render_template, send_file, url_for
import os
import tempfile
from faster_whisper import WhisperModel  # Faster than base Whisper

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Load model once (base.en for English; swap to 'small' for better accuracy, slower)
model = WhisperModel("base.en", device="cpu", compute_type="int8")

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'file' not in request.files:
            return render_template('index.html', error="No file selected")
        file = request.files['file']
        if file.filename == '':
            return render_template('index.html', error="No file selected")
        
        # Supported formats
        if not file.filename.lower().endswith(('.mp3', '.wav', '.flac', '.m4a', '.ogg')):
            return render_template('index.html', error="Unsupported format. Use MP3, WAV, FLAC, M4A, or OGG.")
        
        # Save temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp_file:
            file.save(temp_file.name)
            audio_path = temp_file.name
        
        try:
            # Transcribe (segments for timestamps if needed; here full text)
            segments, info = model.transcribe(audio_path, beam_size=5, language="en")
            text = ' '.join(segment.text for segment in segments)
            detected_lang = info.language if info.language else "en"
            
            # Save TXT for download
            txt_path = os.path.join(app.config['UPLOAD_FOLDER'], 'transcription.txt')
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(text)
            
            # Cleanup temp
            os.unlink(audio_path)
            
            return render_template('result.html', text=text, lang=detected_lang, txt_path=txt_path)
        except Exception as e:
            os.unlink(audio_path)
            return render_template('index.html', error=f"Transcription failed: {str(e)}")
    
    return render_template('index.html')

@app.route('/download')
def download():
    if os.path.exists('uploads/transcription.txt'):
        return send_file('uploads/transcription.txt', as_attachment=True, download_name='transcription.txt')
    return "No file to download", 404

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)