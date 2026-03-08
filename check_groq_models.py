from groq import Groq
import os
from dotenv import load_dotenv

load_dotenv()

# Get API key
api_key = os.getenv('GROQ_API_KEY_1')
if not api_key:
    print("No API key found")
    exit(1)

print(f"API Key found: {api_key[:20]}...")

try:
    client = Groq(api_key=api_key)
    models = client.models.list()
    print("\nAvailable models on Groq:")
    for m in models.data:
        print(f"  - {m.id}")
except Exception as e:
    print(f"Error: {e}")
