# app.py
from flask import Flask, render_template, request, send_file
import asyncio
from main import crawl_data
from config import DATA_MODEL, DATA_MODEL_CLASS

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/configure', methods=['POST'])
def configure():
    global DATA_MODEL, DATA_MODEL_CLASS
    
    # Update configuration from form
    DATA_MODEL = request.form.get('data_model', 'mobile_service_provider')
    # (Add other configuration parameters)
    
    return "Configuration updated!"

@app.route('/start-crawl')
def start_crawl():
    # Run crawling in background
    asyncio.run(crawl_data())
    return "Crawling started!"

@app.route('/download')
def download():
    filename = f"{DATA_MODEL}_data_*.csv"
    return send_file(filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)