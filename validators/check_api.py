# check_api.py - simple check_api
import os
import warnings
import litellm
from dotenv import load_dotenv

# Compatible warning suppression for all Pydantic versions
try:
    from pydantic import PydanticSerializationWarning
    warnings.filterwarnings("ignore", category=PydanticSerializationWarning)
except ImportError:
    warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

load_dotenv()

def test_deepseek():
    try:
        response = litellm.completion(
            model="deepseek/deepseek-chat",
            api_key=os.getenv("Deepseek_API_KEY"),
            messages=[{"role": "user", "content": "Hello"}]
        )
        print("✅ API Key Valid | Response:", response.choices[0].message.content)
        return True
    except Exception as e:
        print(f"⛔ API Error or Invalid Key: {str(e)}")
        return False

if __name__ == "__main__":
    test_deepseek()