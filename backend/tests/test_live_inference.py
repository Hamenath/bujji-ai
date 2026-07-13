import asyncio
import sys
import json
import httpx
import pytest

# Add a default target model
MODEL = "llama3.2"

@pytest.mark.integration
async def test_live_inference():
    print("====================================================")
    print("             OLLAMA LIVE INFERENCE TEST             ")
    print("====================================================")
    
    base_url = "http://localhost:11434"
    print(f"Connecting to Ollama at: {base_url}...")
    
    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        # 1. Check availability
        try:
            response = await client.get("/api/tags", timeout=3.0)
            if response.status_code != 200:
                print(f"[ERROR] Ollama returned status {response.status_code}")
                return
            print("[SUCCESS] Ollama service is ONLINE.")
        except Exception as e:
            print(f"[OFFLINE] Unable to connect to Ollama: {e}")
            print("Please ensure Ollama is installed and running on your system.")
            return

        # 2. Get local models
        try:
            tags = response.json()
            models = [m["name"] for m in tags.get("models", [])]
            print(f"Installed models: {models}")
            if not models:
                print(f"[WARNING] No models installed. Please run: ollama pull {MODEL}")
                return
            
            # Use the first available model if default is not installed
            target_model = MODEL
            # If target model is not pulled, check if we have any llama or qwen model
            installed_target = any(target_model in m for m in models)
            if not installed_target and len(models) > 0:
                target_model = models[0]
                print(f"Default model '{MODEL}' not installed. Using '{target_model}' instead.")
        except Exception as e:
            print(f"[ERROR] Failed to list models: {e}")
            return

        # 3. Non-streaming generation test
        print(f"\n1. Testing non-streaming text generation with '{target_model}'...")
        prompt = "Write a one-sentence greeting to the user."
        payload = {
            "model": target_model,
            "prompt": prompt,
            "stream": False
        }
        try:
            res = await client.post("/api/generate", json=payload)
            res.raise_for_status()
            data = res.json()
            print(f"Prompt: {prompt}")
            print(f"Response: {data.get('response', '').strip()}")
            print("[SUCCESS] Non-streaming generation passed.")
        except Exception as e:
            print(f"[FAIL] Non-streaming generation failed: {e}")

        # 4. Streaming generation test
        print(f"\n2. Testing streaming text generation with '{target_model}'...")
        payload = {
            "model": target_model,
            "prompt": "Count from 1 to 5.",
            "stream": True
        }
        try:
            print("Stream output: ", end="", flush=True)
            async with client.stream("POST", "/api/generate", json=payload) as stream_res:
                stream_res.raise_for_status()
                async for line in stream_res.aiter_lines():
                    if line:
                        chunk = json.loads(line)
                        text_chunk = chunk.get("response", "")
                        print(text_chunk, end="", flush=True)
            print()
            print("[SUCCESS] Streaming generation passed.")
        except Exception as e:
            print(f"\n[FAIL] Streaming generation failed: {e}")
            
if __name__ == "__main__":
    asyncio.run(test_live_inference())
