import streamlit as st
import pandas as pd
import numpy as np
import io
import sqlite3
import os

# --- 1. GLOBAL CONFIGURATION ---
st.set_page_config(
    page_title="LinkLab | Professional Data Suite",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 2. PROFESSIONAL STYLING (CSS) ---
st.markdown("""
    <style>
    [data-testid="stSidebar"] {display: none;}
    .main { background-color: #f8f9fa; }
    .stTabs [data-baseweb="tab-list"] { gap: 20px; border-bottom: 2px solid #e0e0e0; }
    .stTabs [data-baseweb="tab"] { height: 50px; font-weight: 600; font-size: 16px; }
    div[data-testid="stPopover"] > button { border-radius: 20px; border: 1px solid #ddd; padding: 5px 20px; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. DATABASE ENGINE ---
class DBManager:
    def __init__(self, db_path='users.db'):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name TEXT,
                email TEXT UNIQUE,
                password TEXT)''')

    def authenticate(self, email, password):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT first_name, email FROM users WHERE email = ? AND password = ?', (email, password))
            return cursor.fetchone()

    def add_user(self, first_name, email, password):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('INSERT INTO users (first_name, email, password) VALUES (?, ?, ?)', (first_name, email, password))
                return True
        except sqlite3.IntegrityError:
            return False

    def reset_password(self, email, first_name, new_password):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('UPDATE users SET password = ? WHERE email = ? AND first_name = ?', (new_password, email, first_name))
            return cursor.rowcount > 0

db = DBManager()

# --- 4. SESSION STATE ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'auth_mode' not in st.session_state: st.session_state.auth_mode = 'login'
if 'user' not in st.session_state: st.session_state.user = None

# --- 5. UI COMPONENTS ---

def render_auth():
    _, center, _ = st.columns([1, 2, 1])
    with center:
        # Fixed Image Check
        if os.path.exists("image_cb68b62a.png"):
            st.image("image_cb68b62a.png", width=120)
        else:
            st.title("🔬 LinkLab")
        
        if st.session_state.auth_mode == 'login':
            st.subheader("Login")
            e = st.text_input("Email", placeholder="example@linklab.com")
            p = st.text_input("Password", type="password")
            if st.button("Login", use_container_width=True, type="primary"):
                user = db.authenticate(e, p)
                if user:
                    st.session_state.logged_in = True
                    st.session_state.user = {"name": user[0], "email": user[1]}
                    st.rerun()
                else: st.error("Invalid email or password.")
            
            c1, c2 = st.columns(2)
            if c1.button("Forgot Password?", use_container_width=True): 
                st.session_state.auth_mode = 'forgot'; st.rerun()
            if c2.button("Register Account", use_container_width=True): 
                st.session_state.auth_mode = 'register'; st.rerun()

        elif st.session_state.auth_mode == 'register':
            st.subheader("Create Account")
            fn = st.text_input("First Name")
            em = st.text_input("Email")
            pw = st.text_input("Password", type="password")
            if st.button("Register", use_container_width=True, type="primary"):
                if db.add_user(fn, em, pw):
                    st.success("Account created! Please login.")
                    st.session_state.auth_mode = 'login'; st.rerun()
                else: st.error("Email already exists.")
            if st.button("Back to Login", use_container_width=True): 
                st.session_state.auth_mode = 'login'; st.rerun()

        elif st.session_state.auth_mode == 'forgot':
            st.subheader("Reset Password")
            em = st.text_input("Email Address")
            fn = st.text_input("First Name (Verification)")
            npw = st.text_input("New Password", type="password")
            if st.button("Update Password", use_container_width=True, type="primary"):
                if db.reset_password(em, fn, npw):
                    st.success("Updated! Please login."); st.session_state.auth_mode = 'login'; st.rerun()
                else: st.error("Identity verification failed.")
            if st.button("Back", use_container_width=True): 
                st.session_state.auth_mode = 'login'; st.rerun()

# --- 6. APP CONTENT ---

def main_app():
    # Top Right Header
    h_left, h_right = st.columns([4, 1])
    with h_left:
        st.title("LinkLab")
    with h_right:
        with st.popover(f"👤 {st.session_state.user['name']}", use_container_width=True):
            st.write(f"**Email:** {st.session_state.user['email']}")
            if st.button("Logout", use_container_width=True):
                st.session_state.logged_in = False
                st.rerun()

    # Horizontal Tabs
    tab1, tab2, tab3 = st.tabs(["🏠 Home", "📊 Merger", "🔍 Audit"])
    
    with tab1:
        st.write("### Welcome back to the Data Science Suite.")
        st.info("Select a tab above to begin processing your files.")
        
    with tab2:
        st.subheader("Data Merger")
        st.write("Merge multiple CSV or Excel files vertically.")
        # Logic for merger goes here...

    with tab3:
        st.subheader("Audit Tool")
        st.write("Compare datasets for precision errors.")
        # Logic for audit goes here...

# --- 7. ROUTER ---
if st.session_state.logged_in:
    main_app()
else:
    render_auth()
