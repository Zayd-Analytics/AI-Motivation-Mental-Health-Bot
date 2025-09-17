import streamlit as st
import google.generativeai as genai
import os
from dotenv import load_dotenv
import datetime
import matplotlib.pyplot as plt
from sqlalchemy import create_engine, Column, Integer, String, Date, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

# ------------------ CONFIG ------------------
st.set_page_config(page_title="AI Motivation & Mental Health Bot 🧠💡", page_icon="🤖", layout="wide")

# Load .env file
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# ------------------ DATABASE SETUP ------------------
Base = declarative_base()
engine = create_engine("sqlite:///mental_health_bot.db")
SessionLocal = sessionmaker(bind=engine)
db_session = SessionLocal()

# ------------------ TABLES ------------------
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    streak = Column(Integer, default=0)
    last_mood_date = Column(Date, nullable=True)
    daily_done = Column(Boolean, default=False)
    moods = relationship("MoodHistory", back_populates="user")

class MoodHistory(Base):
    __tablename__ = "mood_history"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    mood = Column(String, nullable=False)
    mood_num = Column(Integer, nullable=False)
    user = relationship("User", back_populates="moods")

Base.metadata.create_all(bind=engine)

# ------------------ FUNCTIONS ------------------
def get_or_create_user(email, name):
    user = db_session.query(User).filter_by(email=email).first()
    if not user:
        user = User(name=name, email=email)
        db_session.add(user)
        db_session.commit()
    return user

def detect_mood(user_input):
    mood_prompt = f"Analyze sentiment of this message in one word (Happy, Sad, Neutral, Stressed, Motivated): {user_input}"
    mood = genai.GenerativeModel("gemini-2.5-pro").generate_content(mood_prompt).text.strip()
    return mood

def generate_response(user_input, mood, chat):
    prompt = f"""
    You are an AI Mental Health & Motivation Coach.
    User's mood: {mood}
    Respond with:
    1. Calming/motivational response
    2. Short practical tip or exercise
    3. One motivational quote
    User message: {user_input}
    """
    response = chat.send_message(prompt)
    return response.text

def mood_to_num(mood):
    mapping = {"Sad": 1, "Neutral": 2, "Happy": 3, "Motivated": 4, "Stressed": 5}
    return mapping.get(mood, 2)

def plot_mood_history(user):
    moods = db_session.query(MoodHistory).filter_by(user_id=user.id).all()
    if len(moods) > 1:
        fig, ax = plt.subplots()
        ax.plot([m.timestamp.strftime("%H:%M") for m in moods], [m.mood_num for m in moods], marker="o")
        ax.set_title(f"{user.name}'s Mood Trend")
        ax.set_xlabel("Time")
        ax.set_ylabel("Mood Level (1=Sad, 2=Neutral, 3=Happy, 4=Motivated, 5=Stressed)")
        st.pyplot(fig)

def daily_motivation():
    prompt = """
    You are a Daily Motivation Coach.
    Give:
    1. One powerful motivational quote
    2. One small daily task (like gratitude journaling, quick exercise, positive reflection)
    Keep it short and inspiring.
    """
    response = genai.GenerativeModel("gemini-2.5-pro").generate_content(prompt)
    return response.text

# ------------------ STREAMLIT APP ------------------
st.title("🧠💡 AI Motivation & Mental Health Bot")

# Login
if "current_user" not in st.session_state:
    st.session_state.current_user = None

if not st.session_state.current_user:
    st.subheader("🔑 Login / Register")
    email = st.text_input("Enter your email:")
    name = st.text_input("Enter your name:")
    if st.button("Login"):
        if email and name:
            user = get_or_create_user(email, name)
            st.session_state.current_user = user.email
            st.session_state.chat = genai.GenerativeModel("gemini-2.5-pro").start_chat(history=[])
            st.success(f"Welcome, {user.name}! 🎉")
        else:
            st.error("Please enter both name and email to continue.")
    st.stop()

# Fetch logged-in user
user = db_session.query(User).filter_by(email=st.session_state.current_user).first()
st.sidebar.success(f"Logged in as {user.name} ({user.email})")

# Chat Mode
st.header("💬 Chat with Your AI Coach")
user_input = st.chat_input("How are you feeling today?")

if user_input:
    st.chat_message("user").markdown(user_input)

    # Detect mood
    mood = detect_mood(user_input)
    mood_num = mood_to_num(mood)
    today = datetime.date.today()

    # Update streak
    if user.last_mood_date != today:
        user.streak += 1
        user.last_mood_date = today
        user.daily_done = False
        db_session.commit()

    # Save mood history
    new_mood = MoodHistory(user_id=user.id, mood=mood, mood_num=mood_num)
    db_session.add(new_mood)
    db_session.commit()

    # Generate AI response
    response = generate_response(user_input, mood, st.session_state.chat)
    st.chat_message("assistant").markdown(f"**Mood Detected:** {mood}\n\n{response}")

    st.success(f"🔥 Current Streak: {user.streak} days")

# Daily Motivation Mode
st.header("🌅 Daily Motivation Mode")
if not user.daily_done:
    if st.button("Get Today's Motivation ✨"):
        daily = daily_motivation()
        user.daily_done = True
        db_session.commit()
        st.write(daily)
else:
    st.info("✅ You've already received today's motivation. Come back tomorrow!")

# Mood Tracker
st.header("📊 Mood Tracker Dashboard")
plot_mood_history(user)
