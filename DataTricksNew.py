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

# --- 4. DATA PROCESSING UTILITIES ---
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
    Welcome to your professional data workspace. Below is a breakdown of your available tools and their specific uses:

    #### 1. 📊 Data Merger (Vertical)
    *   **Usage:** Stack multiple files (like monthly reports) into one master sheet.
    *   **Benefit:** Saves hours of manual copy-pasting and ensures row consistency.

    #### 2. 🔍 Audit Tool (Comparison)
    *   **Usage:** Compare two datasets to find discrepancies, modified values, or missing rows.
    *   **Benefit:** Ideal for Quality Assurance and tracking data updates between versions.

    #### 3. 🔗 Multi-Key Join (Horizontal)
    *   **Usage:** Merge columns from two files based on multiple matching criteria.
    *   **Benefit:** A robust replacement for VLOOKUP when one ID isn't enough to identify a record.

    #### 4. ✂️ Text Splitter (Column Formatting)
    *   **Usage:** Split long text/descriptions into multiple columns based on a character limit.
    *   **Benefit:** Essential for uploading data into legacy systems or ERPs with strict character limits per field.
    """)

def merger_tab():
    st.header("📊 Data Merger & Splitter")
    with st.expander("🛠️ How to use this tool"):
        st.write("1. Set the number of files. 2. Upload datasets. 3. Click 'Run Merger'. 4. Download the combined Excel result.")
    
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
            st.download_button("📥 Download Master File", out.getvalue(), "merged_master.xlsx")

def audit_tab():
    st.header("🔍 Precision Audit Tool")
    with st.expander("🛠️ How to use this tool"):
        st.write("1. Upload Reference and New files. 2. Select Unique Key(s). 3. View mismatches. 4. Fix data based on report.")
    
    c1, c2 = st.columns(2)
    with c1: f1 = st.file_uploader("Reference File", type=["csv", "xlsx"], key="aud1")
    with c2: f2 = st.file_uploader("New File", type=["csv", "xlsx"], key="aud2")
    
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
        st.write("1. Load Base and Lookup tables. 2. Select matching keys for both. 3. Join columns horizontally.")
    
    c1, c2 = st.columns(2)
    with c1: l_file = st.file_uploader("Base Table", type=["csv", "xlsx"], key="join1")
    with c2: r_file = st.file_uploader("Lookup Table", type=["csv", "xlsx"], key="join2")
    
    if l_file and r_file:
        ldf, rdf = load_data(l_file), load_data(r_file)
        lk = st.multiselect("Base Keys:", ldf.columns)
        rk = st.multiselect("Lookup Keys:", rdf.columns)
        if st.button("🔗 Execute Join") and len(lk) == len(rk) > 0:
            res = pd.merge(ldf, rdf, left_on=lk, right_on=rk, how='left')
            st.dataframe(res.head())

def splitter_tab():
    st.header("✂️ Text Column Splitter")
    with st.expander("🛠️ How to use this tool"):
        st.write("1. Upload file. 2. Set 'Max Characters' (e.g., 50). 3. Select text column. 4. 'Generate' to split long sentences into Part_1, Part_2, etc.")

    max_len = st.number_input("Max Characters per Column", 1, 500, 50)
    up_file = st.file_uploader("Upload File to Split", type=["csv", "xlsx"], key="split_uploader")

    if up_file:
        df = load_data(up_file)
        col_to_split = st.selectbox("Select column to process:", df.columns)
        
        if st.button("Generate New Columns", type="primary"):
            def split_to_chunks(text, m_len):
                return textwrap.wrap(str(text), width=m_len, break_long_words=False) if pd.notna(text) else []
            
            chunks = df[col_to_split].apply(lambda x: split_to_chunks(x, max_len))
            new_cols = pd.DataFrame(chunks.tolist())
            new_cols.columns = [f"Part_{i+1}" for i in range(new_cols.shape[1])]
            df_final = pd.concat([df, new_cols], axis=1)
            
            st.success("Successfully processed!")
            st.dataframe(df_final.head(20))
            
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='xlsxwriter') as w: df_final.to_excel(w, index=False)
            st.download_button("📥 Download Results", buf.getvalue(), "text_split_results.xlsx")

# --- 6. AUTHENTICATION LOGIC ---

if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'auth_mode' not in st.session_state: st.session_state.auth_mode = 'login'

if not st.session_state.logged_in:
    _, center, _ = st.columns()
    with center:
        if st.session_state.auth_mode == 'login':
            st.header("LinkLab Login")
            em = st.text_input("Email")
            pw = st.text_input("Password", type="password")
            if st.button("Login", use_container_width=True, type="primary"):
                user = db.authenticate(em, pw)
                if user:
                    st.session_state.logged_in = True
                    st.session_state.u_name = user[0]
                    st.session_state.u_email = user[1]
                    st.rerun()
                else: st.error("Access Denied.")
            if st.button("Forgot Password?"): st.session_state.auth_mode = 'forgot'; st.rerun()
            if st.button("Register"): st.session_state.auth_mode = 'register'; st.rerun()
        # ... (register and forgot UI logic similar to previous versions) ...
        elif st.session_state.auth_mode == 'register':
            fn = st.text_input("First Name")
            em = st.text_input("Email")
            pw = st.text_input("Password", type="password")
            if st.button("Create Account"):
                if db.add_user(fn, em, pw): st.session_state.auth_mode = 'login'; st.rerun()
            if st.button("Back"): st.session_state.auth_mode = 'login'; st.rerun()
        elif st.session_state.auth_mode == 'forgot':
            em = st.text_input("Email")
            fn = st.text_input("First Name")
            np = st.text_input("New PW", type="password")
            if st.button("Reset"):
                if db.reset_password(em, fn, np): st.session_state.auth_mode = 'login'; st.rerun()
            if st.button("Back"): st.session_state.auth_mode = 'login'; st.rerun()

else:
    # --- APP INTERFACE ---
    cl, cr = st.columns(2)
    with cl: st.write(f"### LinkLab | 👋 {st.session_state.u_name}")
    with cr:
        with st.popover("👤 Account"):
            st.write(f"Email: {st.session_state.u_email}")
            if st.button("Logout", use_container_width=True):
                st.session_state.logged_in = False
                st.rerun()

    # TABS
    tabs = st.tabs(["🏠 Home", "📊 Data Merger", "🔍 Audit Tool", "🔗 Join Tool", "✂️ Text Splitter"])
    with tabs[0]: home_tab()
    with tabs[1]: merger_tab()
    with tabs[2]: audit_tab()
    with tabs[3]: join_tab()
    with tabs[4]: splitter_tab()
