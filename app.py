from flask import Flask, render_template, request, jsonify
from PyPDF2 import PdfReader
from langchain.text_splitter import RecursiveCharacterTextSplitter
import os
from langchain_google_genai import GoogleGenerativeAIEmbeddings
import google.generativeai as genai
from langchain.vectorstores import FAISS
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.chains.question_answering import load_qa_chain
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv
import asyncio
import docx
import pandas as pd
from urllib.request import urlopen
from bs4 import BeautifulSoup
import certifi
import ssl

# Load environment variables
load_dotenv()

# Retrieve environment variables
google_api_key = os.getenv("GOOGLE_API_KEY")

# Check if environment variables are loaded correctly
if not google_api_key:
    raise ValueError("GOOGLE_API_KEY is not set correctly")

# Configure Google Generative AI
genai.configure(api_key=google_api_key)

# Define the directory to save uploaded files
UPLOAD_DIR = "uploaded_files"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

def get_text_chunks(text):
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=10000, chunk_overlap=1000)
    chunks = text_splitter.split_text(text)
    return chunks

async def get_vector_store(text_chunks):
    embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
    vector_store = FAISS.from_texts(text_chunks, embedding=embeddings)
    vector_store.save_local("faiss_index")

def get_conversational_chain():
    prompt_template = """
    Answer the question as detailed as possible from the provided context, make sure to provide all the details. If the answer is not in
    the provided context, just say, "answer is not available in the context". Don't provide the wrong answer.

    Context:
    {context}

    Question:
    {question}

    Answer:
    """
    model = ChatGoogleGenerativeAI(model="gemini-pro", temperature=0.7)
    prompt = PromptTemplate(template=prompt_template, input_variables=["context", "question"])
    chain = load_qa_chain(model, chain_type="stuff", prompt=prompt)
    return chain

async def user_input(user_question):
    embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
    new_db = FAISS.load_local("faiss_index", embeddings, allow_dangerous_deserialization=True)
    docs = new_db.similarity_search(user_question)
    chain = get_conversational_chain()
    response = chain({"input_documents": docs, "question": user_question}, return_only_outputs=True)
    return response

def extract_text_from_pdf(pdf_path):
    text = ""
    pdf_reader = PdfReader(pdf_path)
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text

def extract_text_from_docx(docx_path):
    doc = docx.Document(docx_path)
    text = "\n".join([para.text for para in doc.paragraphs])
    return text

def extract_text_from_csv(csv_path):
    df = pd.read_csv(csv_path)
    return df.to_string(index=False)

def extract_text_from_txt(txt_path):
    with open(txt_path, 'r', encoding='utf-8') as file:
        return file.read()

def extract_text_from_excel(excel_path):
    df = pd.read_excel(excel_path)
    return df.to_string(index=False)

def extract_text_from_url(url):
    context = ssl.create_default_context(cafile=certifi.where())
    with urlopen(url, context=context) as response:
        html = response.read()
    soup = BeautifulSoup(html, 'html.parser')
    return soup.get_text()

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
    print(request.files)  # Debug: print request.files to see the uploaded files
    if len(request.files) == 0:
        print("No file part in the request")
        return jsonify({"error": "No file uploaded"}), 400

    uploaded_file = None
    for key in request.files:
        uploaded_file = request.files[key]
        break  # Get the first file found

    if uploaded_file is None or uploaded_file.filename == "":
        print("No selected file")
        return jsonify({"error": "No file selected"}), 400

    print(f"File received: {uploaded_file.filename}")

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
        print("Unsupported file type")
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

    try:
        text = extract_text_from_url(url)
    except Exception as e:
        return jsonify({"error": f"Failed to extract text from URL: {str(e)}"}), 400

    text_chunks = get_text_chunks(text)
    asyncio.run(get_vector_store(text_chunks))

    return jsonify({"message": "URL content processed successfully"}), 200

if __name__ == "__main__":
    app.run(debug=True)
