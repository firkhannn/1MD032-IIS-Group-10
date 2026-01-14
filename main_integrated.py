import time
import os
import requests
from furhat_remote_api import FurhatRemoteAPI
from dotenv import load_dotenv
from google import genai
from google.genai import types

# ---------------- Load Environment ----------------
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# ---------------- Elder Companion Bot ----------------
class ElderCompanionBot:
    def __init__(self, furhat_ip="localhost"):
        self.furhat = FurhatRemoteAPI(furhat_ip)
        self.user_name = "Friend"
        self.last_emotion = "neutral"

        # -------- Emotion → Gesture Mapping --------
        self.emotion_gestures = {
            "happy": ["BigSmile", "Nod"],
            "sad": ["Thoughtful", "LookDown"],
            "angry": ["ShakeHead"],
            "fear": ["GazeAway", "Thoughtful"],
            "surprise": ["Surprised", "RaiseBrows"],
            "disgust": ["ShakeHead", "LookAway"],
            "neutral": ["Smile"]
        }

        # -------- Gemini (paraphrase only) --------
        self.genai_client = genai.Client(api_key=GEMINI_API_KEY)
        self.chat = self.genai_client.chats.create(
            model="gemini-2.5-flash-lite",
            config=types.GenerateContentConfig(
                system_instruction=("""
                    You are Furhat, an elder companion robot.
                    Your task is to paraphrase a given response in a warm, gentle, calm, and respectful manner
                    that is easy for an elderly listener to understand.

                    Use simple, clear language with short to medium-length sentences.
                    Avoid slang, technical terms, or fast-paced phrasing.
                    Maintain a patient, reassuring, and compassionate tone.

                    You MUST preserve the original meaning, intent, and emotional stance exactly.
                    You MUST NOT add, remove, or reinterpret information.

                    You MAY reference concrete facts or reasons explicitly stated by the user
                    (such as a specific event, or a situation mentioned by the user)
                    to make the paraphrase feel more personal and grounded.

                    You MUST NOT invent new details, causes, advice, questions, or emotional guidance.
                    You MUST NOT introduce new actions, suggestions, or interpretations.

                    Only rephrase the original response using the user’s stated context while making sure the question at the end is not rephrased.
                    """
                )
            )
        )

    # ---------------- Greeting ----------------
    def greet_user(self):
        self.safe_gesture("Smile")
        self.say("Hello! I'm your companion Furhat.")
        self.say("May I know your name?")

        response = self.furhat.listen()
        if response and response.message:
            self.user_name = self.extract_name(response.message)

        self.say(f"Nice to meet you, {self.user_name}.")

    def extract_name(self, text):
        ignore = ["my", "name", "is", "i'm", "im", "call", "me"]
        words = [w for w in text.lower().split() if w not in ignore]
        return words[0].capitalize() if words else "Friend"

    # ---------------- Emotion Detection ----------------
    def detect_emotion(self, user_input=None):
        """
        Emotion decision logic based on 5-frame webcam window.
        Rules:
        1) 4 neutral + 1 other -> choose the other
        2) ≥2 non-neutral emotions -> choose highest confidence (non-neutral)
        3) All neutral -> ask LLM to infer emotion from user_input
        """
        try:
            response = requests.get("http://127.0.0.1:5000/emotion", timeout=1.0)
            if response.status_code != 200:
                return "neutral"

            payload = response.json()
            frames = payload.get("data", [])

            if not frames:
                return "neutral"

            # --- Group confidences by emotion ---
            counts = {}
            for f in frames:
                emo = f["emotion"].lower()
                conf = float(f["confidence"])
                counts.setdefault(emo, []).append(conf)

            # --- Case 3: all neutral → LLM fallback ---
            if list(counts.keys()) == ["neutral"]:
                return self.llm_emotion_fallback(user_input)

            # --- Remove neutral for decision ---
            non_neutral = {k: v for k, v in counts.items() if k != "neutral"}

            # --- Case 1: exactly one non-neutral emotion ---
            if len(non_neutral) == 1:
                return next(iter(non_neutral.keys()))

            # --- Case 2: multiple non-neutral → highest confidence wins ---
            best_emotion = max(
                non_neutral.items(),
                key=lambda item: max(item[1])
            )[0]

            return best_emotion

        except Exception as e:
            print("Webcam emotion read failed:", e)
            return "neutral"
        
    def llm_emotion_fallback(self, user_input):
        prompt = (
            "Based on the user's message, choose the ONE most likely emotion.\n"
            "Only return ONE word from this list:\n"
            "happy, sad, angry, fear, disgust, surprise\n\n"
            f"User message: '{user_input}'"
        )

        try:
            response = self.chat.send_message(prompt)
            emotion = response.text.strip().lower()
            if emotion in ["happy", "sad", "angry", "fear", "disgust", "surprise"]:
                return emotion
        except Exception as e:
            print("LLM emotion fallback failed:", e)

        return "neutral"

    # ---------------- Gemini Paraphrasing ----------------
    def paraphrase(self, fixed_reply, user_input):
        prompt = (
            f"User said: '{user_input}'\n"
            f"Original response: '{fixed_reply}'\n"
            "Paraphrase warmly for an elderly listener."
        )
        try:
            response = self.chat.send_message(prompt)
            return response.text.strip()
        except Exception as e:
            print("Gemini paraphrasing failed:", e)
            return fixed_reply  # SAFE FALLBACK

    # ---------------- Speech helpers ----------------
    def say(self, text):
        self.furhat.say(text=text, blocking=True)

    # ---------------- Gesture helpers ----------------
    def safe_gesture(self, name):
        if not name:
            return
        try:
            self.furhat.gesture(name=name)
        except Exception:
            pass

    def express_emotion(self, emotion):
        gestures = self.emotion_gestures.get(emotion, [])
        for g in gestures:
            self.safe_gesture(g)
            time.sleep(0.2)

    # ---------------- YES / NO logic ----------------
    YES_WORDS = [
        "yes", "yeah", "yep", "sure", "ok", "okay", "please",
        "alright", "i want", "i would", "i'd like", "lets", "let's",
        "go ahead", "1", "first"
    ]

    NO_WORDS = [
        "no", "nah", "nope", "not", "don't", "do not", "dont",
        "stop", "2", "second"
    ]

    def is_yes(self, text):
        return any(w in text.lower() for w in self.YES_WORDS)

    def is_no(self, text):
        return any(w in text.lower() for w in self.NO_WORDS)

    def ask_yes_no(self, question, reprompt="Sorry, is that a yes or a no?"):
        self.say(question)
        r1 = self.furhat.listen()
        if r1 and r1.message:
            if self.is_yes(r1.message):
                return True
            if self.is_no(r1.message):
                return False

        self.say(reprompt)
        r2 = self.furhat.listen()
        if r2 and r2.message:
            if self.is_yes(r2.message):
                return True
            if self.is_no(r2.message):
                return False

        return None

    def continue_chat_prompt(self):
        self.say("I understand. I will be here for you.")
        return True


    # ---------------- Activities ----------------
    def do_one_breath(self):
        self.say("Okay. Let’s do one slow breath together.")
        self.say("Breathe in... one... two... three...")
        time.sleep(0.3)
        self.say("Hold... one... two...")
        time.sleep(0.3)
        self.say("Breathe out... one... two... three... four...")

    def do_grounding_3_things(self):
        self.say("Okay. Let’s do a quick grounding exercise.")
        self.say("Name one thing you can see, one thing you can hear, and one thing you can feel.")
        self.furhat.listen()
        self.say("Good job. Let’s take one slow breath together.")
        self.say("Breathe in... and breathe out slowly.")

    def do_music_reco(self):
        self.say("Okay. Here are a few options: soft piano, calm lo-fi, or peaceful nature sounds.")
        self.say("Would you like something more relaxing, or something more uplifting?")
        self.furhat.listen()
        self.say("Alright. Try listening for a minute and notice how your body feels.")

    def do_journal_prompt(self):
        self.say("Okay. You can start by writing what happened and how you felt.")
        self.say("What is one detail you want to remember from today?")
        self.furhat.listen()
        self.say("That sounds meaningful. Writing it down can help you remember this moment.")

    # ---------------- Emotion Flows ----------------
    def sad_flow(self, user_input):
        fixed = "I’m sorry that you’re feeling sad and it is completely okay to feel this way. Would you like some music recommendations to help you feel a bit better?"
        choice = self.ask_yes_no(self.paraphrase(fixed, user_input))
        self.safe_gesture("Tilt(direction='left)")
        if choice:
            self.safe_gesture("Nod")
            self.do_music_reco()
            return True
        else:
            self.safe_gesture("Nod")
            self.continue_chat_prompt()
            return True

    def angry_flow(self, user_input):
        fixed = "It seems you're upset. Would you like a quick reset, like a calming breath?"
        choice = self.ask_yes_no(self.paraphrase(fixed, user_input))
        if choice:
            self.safe_gesture("Nod")
            self.do_one_breath()
            return True
        else:
            self.safe_gesture("Nod")
            self.continue_chat_prompt()
            return True

    def fear_flow(self, user_input):
        fixed = "You look worried. Would you like a quick grounding exercise to feel better?"
        self.safe_gesture("ExpressSad")
        choice = self.ask_yes_no(self.paraphrase(fixed, user_input))
        if choice:
            self.safe_gesture("Nod")
            self.do_grounding_3_things()
            return True
        else:
            self.safe_gesture("Nod")
            self.continue_chat_prompt()
            return True

    def happy_flow(self, user_input):
        fixed = "Oh, how wonderful! I am glad that you are happy! Would you like to pen down your thoughts to remember this eventful day?"
        choice = self.ask_yes_no(self.paraphrase(fixed, user_input))
        if choice:
            self.safe_gesture("Nod")
            self.safe_gesture("BigSmile")
            self.do_journal_prompt()
            return True
        else:
            self.safe_gesture("Nod")
            self.continue_chat_prompt()
            return True

    def surprise_flow(self, user_input):
        fixed = "Oh my, that is so surprising! I understand you got a shock, would you like to calm down with a slow breath?"
        self.safe_gesture("Tilt(direction='left')")
        choice = self.ask_yes_no(self.paraphrase(fixed, user_input))
        if choice:
            self.safe_gesture("Nod")
            self.do_one_breath()
            return True
        else:
            self.safe_gesture("Nod")
            self.continue_chat_prompt()
            return True

    def disgust_flow(self, user_input):
        fixed = "That seems really unpleasant, it is fine to feel unsettled. Would you like to take a moment to reset with a calming breath?"
        choice = self.ask_yes_no(self.paraphrase(fixed, user_input))
        if choice:
            self.safe_gesture("Nod")
            self.do_one_breath()
            return True
        else:
            self.safe_gesture("Nod")
            self.continue_chat_prompt()
            return True

    # ---------------- Respond Router ----------------
    def respond(self, user_input):
        emotion = self.detect_emotion(user_input)
        self.last_emotion = emotion
        self.express_emotion(emotion)

        if emotion == "sad":
            return self.sad_flow(user_input)
        elif emotion == "angry":
            return self.angry_flow(user_input)
        elif emotion == "fear":
            return self.fear_flow(user_input)
        elif emotion == "happy":
            return self.happy_flow(user_input)
        elif emotion == "surprise":
            return self.surprise_flow(user_input)
        elif emotion == "disgust":
            return self.disgust_flow(user_input)
        else:
            self.say("I'm here with you. Tell me what's on your mind.")
            return True

    # ---------------- Run Loop ----------------
    def run(self):
        print("Starting Elder Companion Bot...")
        self.greet_user()

        while True:
            self.furhat.say(text="How are you feeling today?", blocking=True)
            response = self.furhat.listen()

            if response and response.message:
                should_continue = self.respond(response.message)
                if should_continue is False:
                    break

            cont = self.ask_yes_no("Would you like to continue the chat?")
            if cont is False:
                break
            

        self.furhat.say(
            text=f"It was nice talking to you, {self.user_name}. Take care.",
            blocking=True
        )

    # ---------------- Furhat Setup ----------------
    def set_face(self, character="Titan", mask="Adult"):
        try:
            self.furhat.set_face(character=character, mask=mask)
        except Exception:
            pass

    def set_voice(self, name="Joanna"):
        try:
            self.furhat.set_voice(name=name)
        except Exception:
            pass


# ---------------- Main ----------------
def main():
    bot = ElderCompanionBot("localhost")
    bot.set_face("Isabel", "Adult")
    bot.set_voice("Joanna")
    bot.run()


if __name__ == "__main__":
    main()
