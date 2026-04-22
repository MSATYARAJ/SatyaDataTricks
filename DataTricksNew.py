import streamlit as st
import pandas as pd
import numpy as np
import io
import sqlite3
import os

# --- 1. GLOBAL CONFIGURATION ---
st.set_page_config(
    page_title="LinkLab | Data Science Suite",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 2. CSS STYLING ---
st.markdown("""
    <style>
    [data-testid="stSidebar"] {display: none;}
    .main { background-color: #fcfcfc; }
    .stTabs [data-baseweb="tab-list"] { gap: 20px; border-bottom: 2px solid #e0e0e0; }
    .stTabs [data-baseweb="tab"] { height: 50px; font-weight: 600; font-size: 16px; }
    .guide-box { background-color: #f0f2f6; padding: 20px; border-radius: 10px; border-left: 5px solid #007bff; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. DATABASE LOGIC ---
class DBManager:
    def __init__(self, db_path='users.db'):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, first_name TEXT, email TEXT UNIQUE, password TEXT)''')

    def authenticate(self, email, password):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT first_name, email FROM users WHERE email = ? AND password = ?', (email, password))
            return cursor.fetchone()

    def add_user(self, first, email, pw):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('INSERT INTO users (first_name, email, password) VALUES (?, ?, ?)', (first, email, pw))
                return True
        except: return False

    def reset_password(self, email, first, new_pw):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('UPDATE users SET password = ? WHERE email = ? AND first_name = ?', (new_pw, email, first))
            return cursor.rowcount > 0

db = DBManager()

# --- 4. DATA PROCESSING ---
@st.cache_data(show_spinner=False)
def load_data(file):
    return pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)

# --- 5. PAGE CONTENT FUNCTIONS ---

def home_tab():
    st.title("🔬 Welcome to LinkLab")
    st.write("### *The Science of Seamless Data*")
    st.divider()

    st.markdown("""
    ### 📖 Platform Guide
    Welcome to your professional data workspace. LinkLab is designed to solve common data fragmentation issues. Below is a breakdown of your available tools:

    #### 1. 📊 Data Merger (Vertical Integration)
    *   **Purpose:** Use this when you have multiple files with the same structure (e.g., Monthly Sales reports) and you want to stack them into one giant "Master" file.
    *   **Utility:** Eliminates manual Copy-Pasting. It can handle up to 20 files at once and even split the results into separate files automatically.

    #### 2. 🔍 Audit Tool (Data Verification)
    *   **Purpose:** Use this to compare two versions of a dataset to find changes, errors, or updates. 
    *   **Utility:** Perfect for checking "Before vs After" updates or finding which rows were added, deleted, or modified between two Excel sheets.

    #### 3. 🔗 Multi-Key Join (Horizontal Integration)
    *   **Purpose:** A high-powered alternative to Excel's VLOOKUP or XLOOKUP.
    *   **Utility:** Allows you to "link" two different datasets based on multiple matching points (e.g., matching a record using both 'Employee ID' AND 'Department').
    """)

def merger_tab():
    st.header("📊 Data Merger & Splitter")
    with st.expander("🛠️ How to use this tool"):
        st.write("""
        1. **Define Input:** Select the number of files you wish to combine.
        2. **Upload:** Drag and drop your CSV or Excel files.
        3. **Process:** Click 'Run Merger'. The app will stack the data and remove duplicates.
        4. **Download:** Save your new 'Master' dataset as a single Excel file.
        """)
    
    num = st.number_input("Number of files", 2, 20, 2)
    files = [st.file_uploader(f"Dataset {i+1}", type=["csv", "xlsx"], key=f"merge_{i}") for i in range(num)]
    
    if all(files):
        if st.button("🚀 Run Merger", use_container_width=True):
            dfs = [load_data(f) for f in files]
            res = pd.concat(dfs, axis=0, ignore_index=True).drop_duplicates()
            st.success("Merge Complete!")
            st.dataframe(res.head(10))
            
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine='xlsxwriter') as w: res.to_excel(w, index=False)
            st.download_button("📥 Download Result", out.getvalue(), "merged_master.xlsx")

def audit_tab():
    st.header("🔍 Precision Audit Tool")
    with st.expander("🛠️ How to use this tool"):
        st.write("""
        1. **Upload Files:** Upload your 'Reference' file (the original) and your 'New' file.
        2. **Select Keys:** Choose the column that uniquely identifies rows (e.g., 'ID' or 'Email').
        3. **Compare:** The app will analyze both files and highlight rows that are different or missing.
        4. **Export:** Download the 'Mismatch Report' to fix errors.
        """)
    
    c1, c2 = st.columns(2)
    with c1: f1 = st.file_uploader("Reference File", type=["csv", "xlsx"])
    with c2: f2 = st.file_uploader("New File", type=["csv", "xlsx"])
    
    if f1 and f2:
        df1, df2 = load_data(f1), load_data(f2)
        keys = st.multiselect("Select Unique Key(s):", df1.columns)
        if st.button("Run Audit") and keys:
            merged = pd.merge(df1, df2, on=keys, how='outer', indicator=True)
            diffs = merged[merged['_merge'] != 'both']
            st.metric("Mismatches Found", len(diffs))
            st.dataframe(diffs)

def join_tab():
    st.header("🔗 Multi-Key Join")
    with st.expander("🛠️ How to use this tool"):
        st.write("""
        1. **Load Tables:** Upload your 'Base' table and the 'Lookup' table containing the info you want to add.
        2. **Map Keys:** Select the matching columns from both files (e.g., 'Name' in File 1 = 'FullName' in File 2).
        3. **Join:** Click 'Execute' to pull the data across horizontally.
        """)
    
    c1, c2 = st.columns(2)
    with c1: l_file = st.file_uploader("Base Table", type=["csv", "xlsx"])
    with c2: r_file = st.file_uploader("Lookup Table", type=["csv", "xlsx"])
    
    if l_file and r_file:
        ldf, rdf = load_data(l_file), load_data(r_file)
        lk = st.multiselect("Base Keys:", ldf.columns)
        rk = st.multiselect("Lookup Keys:", rdf.columns)
        if st.button("🔗 Execute Join") and len(lk) == len(rk) > 0:
            res = pd.merge(ldf, rdf, left_on=lk, right_on=rk, how='left')
            st.dataframe(res.head())

# --- 6. AUTHENTICATION UI ---

if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'auth_mode' not in st.session_state: st.session_state.auth_mode = 'login'

if not st.session_state.logged_in:
    _, center, _ = st.columns([1, 2, 1])
    with center:
        if st.session_state.auth_mode == 'login':
            st.header("LinkLab Login")
            em = st.text_input("Email")
            pw = st.text_input("Password", type="password")
            if st.button("Login", use_container_width=True, type="primary"):
                user = db.authenticate(em, pw)
                if user:
                    st.session_state.logged_in = True
                    st.session_state.user_name = user[0]
                    st.session_state.user_email = user[1]
                    st.rerun()
                else: st.error("Login failed.")
            if st.button("Forgot Password?"): st.session_state.auth_mode = 'forgot'; st.rerun()
            if st.button("New User? Register"): st.session_state.auth_mode = 'register'; st.rerun()
        
        elif st.session_state.auth_mode == 'register':
            st.header("Register")
            fn = st.text_input("First Name")
            em = st.text_input("Email")
            pw = st.text_input("Password", type="password")
            if st.button("Register Account"):
                if db.add_user(fn, em, pw): st.session_state.auth_mode = 'login'; st.rerun()
            if st.button("Back"): st.session_state.auth_mode = 'login'; st.rerun()

        elif st.session_state.auth_mode == 'forgot':
            st.header("Reset Password")
            em = st.text_input("Email")
            fn = st.text_input("First Name")
            np = st.text_input("New Password", type="password")
            if st.button("Update"):
                if db.reset_password(em, fn, np): st.session_state.auth_mode = 'login'; st.rerun()
            if st.button("Back"): st.session_state.auth_mode = 'login'; st.rerun()

else:
    # --- APP HEADER ---
    col_l, col_r = st.columns([4, 1])
    with col_l: st.write(f"### LinkLab | 👋 Welcome, {st.session_state.user_name}")
    with col_r:
        with st.popover("👤 Account"):
            st.write(f"Email: {st.session_state.user_email}")
            if st.button("Logout", use_container_width=True):
                st.session_state.logged_in = False
                st.rerun()

    # --- MAIN TABS ---
    t1, t2, t3, t4 = st.tabs(["🏠 Home", "📊 Data Merger", "🔍 Audit Tool", "🔗 Join Tool"])
    with t1: home_tab()
    with t2: merger_tab()
    with t3: audit_tab()
    with t4: join_tab()
