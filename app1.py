from flask import Flask, render_template, request, jsonify
import os
import asyncio

from env_setup import load_env_variables, configure_genai
from text_extraction import extract_text_from_pdf, extract_text_from_docx, extract_text_from_csv, extract_text_from_txt, extract_text_from_excel
from text_chunking import get_text_chunks
from vector_store import get_vector_store
from conversational_chain import user_input

# Load environment variables
google_api_key = load_env_variables()
configure_genai(google_api_key)

# Define the directory to save uploaded files
UPLOAD_DIR = "uploaded_files"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/process_question", methods=["POST"])
def process_question():
    if request.method == 'POST':
        data = request.json
        user_question = data.get('question')
        if user_question:
            response = asyncio.run(user_input(user_question))
            return jsonify({"response": response})
        else:
            return jsonify({"error": "No question provided"}), 400
    else:
        return jsonify({"error": "Only POST requests are supported"}), 405

@app.route("/upload", methods=["POST"])
def upload():
    if len(request.files) == 0:
        return jsonify({"error": "No file uploaded"}), 400

    uploaded_file = next(iter(request.files.values()))
    if uploaded_file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    file_path = os.path.join(UPLOAD_DIR, uploaded_file.filename)
    uploaded_file.save(file_path)

    file_extension = uploaded_file.filename.split('.')[-1].lower()
    text = ""

    if file_extension == "pdf":
        text = extract_text_from_pdf(file_path)
    elif file_extension == "docx":
        text = extract_text_from_docx(file_path)
    elif file_extension == "csv":
        text = extract_text_from_csv(file_path)
    elif file_extension == "txt":
        text = extract_text_from_txt(file_path)
    elif file_extension in ["xls", "xlsx"]:
        text = extract_text_from_excel(file_path)
    else:
        return jsonify({"error": "Unsupported file type"}), 400

    text_chunks = get_text_chunks(text)
    asyncio.run(get_vector_store(text_chunks))

    return jsonify({"message": "File uploaded and processed successfully"}), 200

@app.route("/upload_url", methods=["POST"])
def upload_url():
    data = request.json
    url = data.get('url')
    if not url:
        return jsonify({"error": "No URL provided"}), 400

    from urllib.request import urlopen
    from bs4 import BeautifulSoup
    import certifi
    import ssl

    def extract_text_from_url(url):
        context = ssl.create_default_context(cafile=certifi.where())
        with urlopen(url, context=context) as response:
            html = response.read()
        soup = BeautifulSoup(html, 'html.parser')
        return soup.get_text()

    try:
        text = extract_text_from_url(url)
    except Exception as e:
        return jsonify({"error": f"Failed to extract text from URL: {str(e)}"}), 400

    text_chunks = get_text_chunks(text)
    asyncio.run(get_vector_store(text_chunks))

    return jsonify({"message": "URL content processed successfully"}), 200

if __name__ == "__main__":
    app.run(debug=True)
