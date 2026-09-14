import os
import json
import asyncio
import websockets
import base64
import sys

# Add parent directory to path to import agent modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.config import GEMINI_API_KEY, GEMINI_LIVE_MODEL

if not GEMINI_LIVE_MODEL.startswith("models/"):
    formatted_model = f"models/{GEMINI_LIVE_MODEL}"
else:
    formatted_model = GEMINI_LIVE_MODEL

GEMINI_WS_URL = f"wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key={GEMINI_API_KEY}"

language_configs = {
    "Bengali": {
        "code": "bn-BD",
        "greeting": "আসসালামুআলাইকুম! Unified Cloud এ কল করার জন্য ধন্যবাদ। কিভাবে আপনাকে সাহায্য করতে পারি?",
        "voice": "Leda"
    },
    "English": {
        "code": "en-US",
        "greeting": "Hello! Thank you for calling Unified Cloud . How can I help you today?",
        "voice": "Aoede"
    },
    "Spanish": {
        "code": "es-ES",
        "greeting": "¡Hola! Gracias por llamar a Unified Cloud. ¿Cómo puedo ayudarle hoy?",
        "voice": "Aoede"
    },
    "Portuguese": {
        "code": "pt-PT",
        "greeting": "Olá! Obrigado por ligar para a Unified Cloud. Como posso ajudá-lo hoje?",
        "voice": "Aoede"
    }
}

VOICE_PERSONA_PROMPT = """
--- VOICE CALL PERSONA ---
You are the voice receptionist of Unified Cloud.
- STRICT RULE: When greeting, you MUST start exactly with "{greeting}" (Do not change this greeting).
"""

async def generate_greeting(lang_name, config):
    print(f"Generating greeting for {lang_name}...")
    full_prompt = VOICE_PERSONA_PROMPT.format(greeting=config["greeting"])
    audio_chunks = []
    
    try:
        async with websockets.connect(GEMINI_WS_URL) as gemini_ws:
            setup_message = {
                "setup": {
                    "model": formatted_model,
                    "generationConfig": {
                        "temperature": 0.2,
                        "responseModalities": ["AUDIO"],
                        "speechConfig": {
                            "voiceConfig": {
                                "prebuiltVoiceConfig": {
                                    "voiceName": config["voice"]
                                }
                            },
                            "languageCode": config["code"]
                        }
                    },
                    "systemInstruction": {
                        "parts": [{"text": full_prompt}]
                    }
                }
            }
            await gemini_ws.send(json.dumps(setup_message))
            setup_response = await gemini_ws.recv()
            print(f"[{lang_name}] Setup response received.")

            initial_greeting_message = {
                "clientContent": {
                    "turns": [
                        {
                            "role": "user",
                            "parts": [{"text": "Hello! Please greet me to start the call. Say ONLY the greeting."}]
                        }
                    ],
                    "turnComplete": True
                }
            }
            await gemini_ws.send(json.dumps(initial_greeting_message))

            while True:
                response_str = await gemini_ws.recv()
                data = json.loads(response_str)
                
                if "serverContent" in data:
                    server_content = data["serverContent"]
                    if "modelTurn" in server_content:
                        parts = server_content["modelTurn"].get("parts", [])
                        for part in parts:
                            if "inlineData" in part:
                                chunk_b64 = part["inlineData"]["data"]
                                audio_chunks.append(base64.b64decode(chunk_b64))
                    
                    if server_content.get("turnComplete"):
                        print(f"[{lang_name}] Turn complete.")
                        break
                        
    except Exception as e:
        print(f"Error generating {lang_name}: {e}")
        return None

    # Concatenate all raw PCM chunks
    if not audio_chunks:
        print(f"[{lang_name}] No audio generated!")
        return None
        
    full_audio = b"".join(audio_chunks)
    full_b64 = base64.b64encode(full_audio).decode('utf-8')
    print(f"[{lang_name}] Successfully generated {len(full_audio)} bytes of audio.")
    return full_b64

async def main():
    greetings_data = {}
    for lang, config in language_configs.items():
        b64_audio = await generate_greeting(lang, config)
        if b64_audio:
            greetings_data[lang] = {
                "text": config["greeting"],
                "audioB64": b64_audio
            }
    
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    os.makedirs(data_dir, exist_ok=True)
    out_path = os.path.join(data_dir, "greetings.json")
    
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(greetings_data, f, ensure_ascii=False, indent=2)
    
    print(f"\nSuccessfully wrote generated greetings to {out_path}")

if __name__ == "__main__":
    asyncio.run(main())
