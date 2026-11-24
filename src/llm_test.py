
import json
import urllib.request

url = "http://localhost:11434/api/chat"

payload = {
    "model": "qwen3:4b",
    "messages": [
        {
            "role": "user",
            "content": "Explain SQL in one sentence."
        }
    ],
    "stream": False
}

request = urllib.request.Request(
    url,
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST"
)

print("Sending question to Qwen3...")

with urllib.request.urlopen(request, timeout=180) as response:
    result = json.loads(response.read().decode("utf-8"))

print("\nQwen3 response:")
print(result["message"]["content"])
