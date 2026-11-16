import os
import time
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv('GROQ_API_KEY_1') or os.getenv('GROQ_API_KEY')
client = Groq(api_key=api_key) if api_key else Groq()

models_to_test = [
    "qwen/qwen3.8-27b",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant"
]

for model in models_to_test:
    print(f"Testing {model}...")
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Say hello"}],
            temperature=0.7,
            max_tokens=10
        )
        print(f"  Success! Response: {response.choices[0].message.content}")
    except Exception as e:
        print(f"  Error: {e}")
    time.sleep(1)
