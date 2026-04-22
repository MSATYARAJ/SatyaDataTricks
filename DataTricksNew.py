import streamlit as st
import pandas as pd
import numpy as np
import io
import sqlite3

# --- 1. CONFIG & STYLING ---
st.set_page_config(page_title="LinkLab | Data Suite", layout="wide")

st.markdown("""
    <style>
    [data-testid="stSidebar"] {display: none;}
    .main .block-container {padding-top: 1rem;}
    .stTabs [data-baseweb="tab-list"] { gap: 30px; border-bottom: 1px solid #ddd; }
    .stTabs [data-baseweb="tab"] { height: 50px; font-weight: 600; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATABASE LOGIC ---
def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                 id INTEGER PRIMARY KEY AUTOINCREMENT, 
                 first_name TEXT, email TEXT UNIQUE, password TEXT)''')
    conn.commit()
    conn.close()

def authenticate_user(email, password):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('SELECT first_name, email FROM users WHERE email = ? AND password = ?', (email, password))
    user = c.fetchone()
    conn.close()
    return user

def verify_user_for_reset(email, first_name):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE email = ? AND first_name = ?', (email, first_name))
    user = c.fetchone()
    conn.close()
    return user is not None

def update_password(email, new_password):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('UPDATE users WHERE email = ?', (new_password, email))
    c.execute('UPDATE users SET password = ? WHERE email = ?', (new_password, email))
    conn.commit()
    conn.close()
    return True

def add_user(first, email, password):
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('INSERT INTO users (first_name, email, password) VALUES (?,?,?)', (first, email, password))
        conn.commit()
        conn.close()
        return True
    except: return False

init_db()

# --- 3. SESSION STATE ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'auth_mode' not in st.session_state: st.session_state['auth_mode'] = 'login' # login, register, forgot

# --- 4. AUTHENTICATION PAGES ---

def login_ui():
    st.subheader("Login to LinkLab")
    email = st.text_input("Email")
    pw = st.text_input("Password", type="password")
    if st.button("Login", use_container_width=True, type="primary"):
        user = authenticate_user(email, pw)
        if user:
            st.session_state['logged_in'] = True
            st.session_state['user_info'] = {"name": user[0], "email": user[1]}
            st.rerun()
        else: st.error("Invalid email or password")
    
    c1, c2 = st.columns(2)
    if c1.button("Forgot Password?", use_container_width=True):
        st.session_state['auth_mode'] = 'forgot'
        st.rerun()
    if c2.button("Create Account", use_container_width=True):
        st.session_state['auth_mode'] = 'register'
        st.rerun()

def register_ui():
    st.subheader("Create New Account")
    fn = st.text_input("First Name")
    em = st.text_input("Email")
    pw = st.text_input("Create Password", type="password")
    if st.button("Register", use_container_width=True, type="primary"):
        if add_user(fn, em, pw):
            st.success("Account created! Please login.")
            st.session_state['auth_mode'] = 'login'
            st.rerun()
        else: st.error("Email already exists")
    if st.button("Back to Login"):
        st.session_state['auth_mode'] = 'login'; st.rerun()

def forgot_pw_ui():
    st.subheader("Reset Password")
    st.info("Verify your identity to set a new password.")
    em = st.text_input("Registered Email")
    fn = st.text_input("Confirm First Name")
    new_pw = st.text_input("New Password", type="password")
    
    if st.button("Update Password", use_container_width=True, type="primary"):
        if verify_user_for_reset(em, fn):
            update_password(em, new_pw)
            st.success("Password updated successfully!")
            st.session_state['auth_mode'] = 'login'
            # st.rerun() is optional here to let them see success
        else:
            st.error("Verification failed. Information does not match.")
    if st.button("Back to Login"):
        st.session_state['auth_mode'] = 'login'; st.rerun()

# --- 5. MAIN LOGIC ---

if not st.session_state['logged_in']:
    _, center_col, _ = st.columns([1,2,1])
    with center_col:
        st.image("image_cb68b62a.png", width=100) # Optional logo
        if st.session_state['auth_mode'] == 'login': login_ui()
        elif st.session_state['auth_mode'] == 'register': register_ui()
        elif st.session_state['auth_mode'] == 'forgot': forgot_pw_ui()

else:
    # TOP HEADER BAR
    h_left, h_right = st.columns([4,1])
    with h_left:
        st.subheader(f"LinkLab | 👋 {st.session_state['user_info']['name']}")
    with h_right:
        with st.popover("👤 Profile"):
            st.write(f"Logged in as: **{st.session_state['user_info']['email']}**")
            if st.button("🚪 Logout", use_container_width=True):
                st.session_state['logged_in'] = False
                st.rerun()

    # APP TABS
    t1, t2, t3 = st.tabs(["🏠 Home", "📊 Merger", "🔍 Audit"])
    with t1: st.write("Welcome to your dashboard.")
    with t2: st.write("Upload files to merge...")
    with t3: st.write("Run data comparisons...")
    st.session_state['logged_in'] = False
    st.rerun()

    if page == "Home": home_page()
    elif page == "Data Merger": merger_page()
    elif page == "Audit Tool": audit_page()
    elif page == "Multi-Key Merger": multi_key_merger_page()
