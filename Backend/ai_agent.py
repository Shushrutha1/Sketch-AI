import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    model = None

class AIAgent:
    @staticmethod
    def generate_prompt_set(category: str) -> dict:
        """Generates dynamic gaming prompts utilizing Google Gemini foundational models."""
        default_payload = {
            "word": category.upper(),
            "challenge": f"Draw a realistic {category} within production timelines.",
            "hint": "It belongs to standard ecosystem metrics."
        }
        if not model:
            return default_payload

        prompt_matrix = (
            f"Generate a creative drawing game challenge for the structural domain category: '{category}'. "
            f"Respond strictly with a valid JSON structure containing exactly three keys: 'word', 'challenge', "
            f"and 'hint'. Do not wrap the JSON output inside Markdown code blocks or provide conversational text."
        )
        try:
            response = model.generate_content(prompt_matrix)
            clean_text = response.text.strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text.split("```json")[1].split("```")[0].strip()
            elif clean_text.startswith("```"):
                clean_text = clean_text.split("```")[1].split("```")[0].strip()
            return json.loads(clean_text)
        except Exception:
            return default_payload

    @staticmethod
    def process_ai_roast(word: str, guessed_history: list) -> str:
        """Asynchronously triggers funny programmatic commentary based on current canvas activity states."""
        if not model:
            return "AI Commentary: Fascinating execution vectors detected on canvas."
        
        prompt_matrix = (
            f"The goal of the player is to draw a '{word}'. Other players have guessed the following: {guessed_history}. "
            f"Provide a brief, single-sentence funny/witty commentary or harmless roast regarding this game state. "
            f"Keep it under 25 words."
        )
        try:
            response = model.generate_content(prompt_matrix)
            return response.text.strip()
        except Exception:
            return "AI Commentary: Processing structural path variations synchronously..."