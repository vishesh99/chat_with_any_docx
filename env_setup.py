import os
from dotenv import load_dotenv
import google.generativeai as genai

def load_env_variables():
    load_dotenv()
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        raise ValueError("GOOGLE_API_KEY is not set correctly")
    return google_api_key

def configure_genai(api_key):
    genai.configure(api_key=api_key)
