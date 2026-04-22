import streamlit as st
import pandas as pd
import numpy as np
import io
import sqlite3
import os
import textwrap

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
    .stButton>button { border-radius: 4px; font-weight: bold; }
    .guide-box { background-color: #f0f2f6; padding: 15px; border-radius: 10px; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. DATABASE ENGINE ---
class DBManager:
    def __init__(self, db_path='users.db'):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS users 
                            (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                             first_name TEXT, email TEXT UNIQUE, password TEXT)''')

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

# --- 4. SESSION STATE INITIALIZATION (Prevents AttributeErrors) ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'auth_mode' not in st.session_state: st.session_state.auth_mode = 'login'
if 'u_name' not in st.session_state: st.session_state.u_name = ""
if 'u_email' not in st.session_state: st.session_state.u_email = ""

# --- 5. DATA UTILITIES ---
@st.cache_data(show_spinner=False)
def load_data(file):
    return pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)

# --- 6. TAB CONTENT FUNCTIONS ---

def home_tab():
    st.title("🔬 Welcome to LinkLab")
    st.write("### *The Science of Seamless Data*")
    st.divider()
    st.markdown("""
    ### 📖 Platform Guide
    Welcome to your professional data workspace. Below is a breakdown of your tools:
    *   **📊 Data Merger**: Stack multiple reports vertically into one master file.
    *   **🔍 Audit Tool**: Compare two versions of data to find mismatches or missing rows.
    *   **🔗 Multi-Key Join**: Link two tables using multiple column matches (Advanced VLOOKUP).
    *   **✂️ Text Splitter**: Break long text into multiple columns based on character limits.
    """)

def merger_tab():
    st.header("📊 Data Merger & Splitter")
    st.info("💡 **How to use:** Upload 2 or more files with the same columns to combine them into one master file.")
    num = st.number_input("Number of files", 2, 20, 2)
    files = [st.file_uploader(f"Dataset {i+1}", type=["csv", "xlsx"], key=f"m_{i}") for i in range(num)]
    
    if all(files):
        if st.button("🚀 Run Merger", use_container_width=True):
            dfs = [load_data(f) for f in files]
            res = pd.concat(dfs, axis=0, ignore_index=True).drop_duplicates()
            st.success(f"Merged {len(res)} unique rows.")
            st.dataframe(res.head(10))
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine='xlsxwriter') as w: res.to_excel(w, index=False)
            st.download_button("📥 Download Master File", out.getvalue(), "merged_master.xlsx")

def audit_tab():
    st.header("🔍 Precision Audit Tool")
    st.info("💡 **How to use:** Upload a Reference and a New file. Select the Unique Key (e.g. ID) to see what changed.")
    c1, c2 = st.columns(2)
    with c1: f1 = st.file_uploader("Reference File", type=["csv", "xlsx"], key="a1")
    with c2: f2 = st.file_uploader("New File", type=["csv", "xlsx"], key="a2")
    
    if f1 and f2:
        df1, df2 = load_data(f1), load_data(f2)
        keys = st.multiselect("Select Unique Key(s):", df1.columns)
        if st.button("Run Comparison") and keys:
            merged = pd.merge(df1, df2, on=keys, how='outer', indicator=True)
            diffs = merged[merged['_merge'] != 'both']
            st.metric("Discrepancies Found", len(diffs))
            st.dataframe(diffs)

def join_tab():
    st.header("🔗 Multi-Key Join")
    st.info("💡 **How to use:** Upload two tables and select the columns that match in both to pull data horizontally.")
    c1, c2 = st.columns(2)
    with c1: l_file = st.file_uploader("Base Table", type=["csv", "xlsx"], key="j1")
    with c2: r_file = st.file_uploader("Lookup Table", type=["csv", "xlsx"], key="j2")
    
    if l_file and r_file:
        ldf, rdf = load_data(l_file), load_data(r_file)
        lk = st.multiselect("Base Keys:", ldf.columns)
        rk = st.multiselect("Lookup Keys:", rdf.columns)
        if st.button("🔗 Execute Join") and len(lk) == len(rk) > 0:
            res = pd.merge(ldf, rdf, left_on=lk, right_on=rk, how='left')
            st.success("Join Successful!")
            st.dataframe(res.head(10))

def splitter_tab():
    st.header("✂️ Text Column Splitter")
    st.info("💡 **How to use:** Set a character limit and select a column. The tool splits long text into 'Part_1', 'Part_2', etc.")
    max_len = st.number_input("Max Characters per Column", 1, 500, 50)
    up_file = st.file_uploader("Upload File to Split", type=["csv", "xlsx"], key="s1")
    
    if up_file:
        df = load_data(up_file)
        col = st.selectbox("Select Text Column:", df.columns)
        if st.button("Generate New Columns", type="primary"):
            def wrap_text(t, m): return textwrap.wrap(str(t), width=m, break_long_words=False) if pd.notna(t) else []
            chunks = df[col].apply(lambda x: wrap_text(x, max_len))
            new_cols = pd.DataFrame(chunks.tolist())
            new_cols.columns = [f"Part_{i+1}" for i in range(new_cols.shape[1])]
            df_final = pd.concat([df, new_cols], axis=1)
            st.success("Successfully split text!")
            st.dataframe(df_final.head(10))
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='xlsxwriter') as w: df_final.to_excel(w, index=False)
            st.download_button("📥 Download Split Results", buf.getvalue(), "split_results.xlsx")

# --- 7. AUTHENTICATION LOGIC ---

if not st.session_state.logged_in:
    _, center, _ = st.columns([1, 2, 1])
    with center:
        if os.path.exists("image_cb68b62a.png"): st.image("image_cb68b62a.png", width=120)
        else: st.title("🔬 LinkLab")
        
        if st.session_state.auth_mode == 'login':
            st.header("Login")
            em = st.text_input("Email")
            pw = st.text_input("Password", type="password")
            if st.button("Login", use_container_width=True, type="primary"):
                user_record = db.authenticate(em, pw)
                if user_record:
                    st.session_state.logged_in = True
                    st.session_state.u_name = user_record[0]  # First Name
                    st.session_state.u_email = user_record[1] # Email
                    st.rerun()
                else: st.error("Invalid credentials.")
            
            c1, c2 = st.columns(2)
            if c1.button("Forgot Password?"): st.session_state.auth_mode = 'forgot'; st.rerun()
            if c2.button("Register Account"): st.session_state.auth_mode = 'register'; st.rerun()

        elif st.session_state.auth_mode == 'register':
            st.header("Register")
            fn = st.text_input("First Name")
            em = st.text_input("Email Address")
            pw = st.text_input("Password", type="password")
            if st.button("Create Account", use_container_width=True, type="primary"):
                if db.add_user(fn, em, pw):
                    st.success("Account created! Please login.")
                    st.session_state.auth_mode = 'login'; st.rerun()
                else: st.error("Email already exists.")
            if st.button("Back to Login"): st.session_state.auth_mode = 'login'; st.rerun()

        elif st.session_state.auth_mode == 'forgot':
            st.header("Reset Password")
            em = st.text_input("Registered Email")
            fn = st.text_input("Confirm First Name")
            np = st.text_input("New Password", type="password")
            if st.button("Update Password", use_container_width=True, type="primary"):
                if db.reset_password(em, fn, np):
                    st.success("Password updated! Please login.")
                    st.session_state.auth_mode = 'login'; st.rerun()
                else: st.error("Verification failed.")
            if st.button("Back"): st.session_state.auth_mode = 'login'; st.rerun()

else:
    # --- APP INTERFACE (POST-LOGIN) ---
    cl, cr = st.columns([4, 1])
    with cl: st.write(f"### LinkLab | 👋 Welcome, {st.session_state.u_name}")
    with cr:
        with st.popover("👤 Account"):
            st.write(f"Logged in as: **{st.session_state.u_email}**")
            if st.button("Logout", use_container_width=True):
                st.session_state.logged_in = False
                st.rerun()

    # Define Horizontal Navigation Tabs
    t_home, t_merger, t_audit, t_join, t_split = st.tabs([
        "🏠 Home", "📊 Merger", "🔍 Audit", "🔗 Join", "✂️ Splitter"
    ])

    with t_home: home_tab()
    with t_merger: merger_tab()
    with t_audit: audit_tab()
    with t_join: join_tab()
    with t_split: splitter_tab()
