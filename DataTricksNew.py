import streamlit as st
import pandas as pd
import numpy as np
import io
import zipfile
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
    /* Hide Sidebar */
    [data-testid="stSidebar"] {display: none;}
    
    /* Background and Layout */
    .main { background-color: #fcfcfc; }
    .block-container { padding-top: 1rem; }

    /* Horizontal Tab Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 30px;
        border-bottom: 2px solid #f0f2f6;
    }
    .stTabs [data-baseweb="tab"] {
        height: 60px;
        font-weight: 600;
        font-size: 16px;
        color: #555;
    }
    .stTabs [data-baseweb="tab"]:hover { color: #007bff; }
    .stTabs [data-baseweb="tab"][aria-selected="true"] { 
        color: #007bff; 
        border-bottom-color: #007bff; 
    }

    /* Top-Right Profile Menu */
    div[data-testid="stPopover"] > button {
        border-radius: 30px;
        border: 1px solid #dfe1e5;
        background-color: white;
        padding: 5px 25px;
        transition: 0.3s;
    }
    div[data-testid="stPopover"] > button:hover {
        border-color: #007bff;
        box-shadow: 0 1px 6px rgba(32,33,36,0.1);
    }
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

db_engine = DBManager()

# --- 4. SESSION STATE MANAGEMENT ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'auth_mode' not in st.session_state: st.session_state.auth_mode = 'login'
if 'user' not in st.session_state: st.session_state.user = None
if 'shared_df' not in st.session_state: st.session_state.shared_df = None

# --- 5. CORE FUNCTIONS ---

@st.cache_data(show_spinner=False)
def load_data(file):
    if file.name.endswith('.csv'): return pd.read_csv(file)
    return pd.read_excel(file)

# --- 6. PAGE TABS ---

def home_tab():
    c1, c2 = st.columns([1, 4])
    with c1:
        if os.path.exists("image_cb68b62a.png"): st.image("image_cb68b62a.png", width=140)
        else: st.title("🔬")
    with c2:
        st.title("LinkLab")
        st.write("### *The science of seamless data*")
    
    st.divider()
    st.markdown("""
    ### Master Your Data Complexity
    At **LinkLab**, we turn fragmented datasets into a single source of truth. 
    Use the navigation tabs above to access our specialized tools.
    
    *   **📊 Data Merger**: Combine multiple files and split them by category.
    *   **🔍 Audit Tool**: Detect precision errors between two versions of data.
    *   **🔗 Multi-Key Join**: Advanced lookup matching using multiple parameters.
    """)

def merger_tab():
    st.subheader("📊 Data Merger & Splitter")
    num_files = st.number_input("Number of files", 2, 20, 2)
    files = [st.file_uploader(f"Upload Dataset {i+1}", type=["csv", "xlsx"], key=f"f{i}") for i in range(num_files)]
    
    if all(files):
        dfs = [load_data(f) for f in files]
        if st.button("🚀 Process & Merge Data", use_container_width=True):
            res = pd.concat(dfs, axis=0, ignore_index=True).drop_duplicates()
            st.session_state.shared_df = res
            st.success(f"Successfully combined {len(res)} rows.")
            st.dataframe(res.head(10), use_container_width=True)
            
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
                res.to_excel(writer, index=False)
            st.download_button("📥 Download Master File", out.getvalue(), "merged_data.xlsx")

def audit_tab():
    st.subheader("🔍 Data Comparison Audit")
    c1, c2 = st.columns(2)
    with c1: f1 = st.file_uploader("Reference Dataset", type=["csv", "xlsx"])
    with c2: f2 = st.file_uploader("New Dataset", type=["csv", "xlsx"])
    
    if f1 and f2:
        d1, d2 = load_data(f1), load_data(f2)
        keys = st.multiselect("Select Primary Keys (IDs):", d1.columns)
        if st.button("Run Audit") and keys:
            merged = pd.merge(d1, d2, on=keys, how='outer', indicator=True, suffixes=('_REF', '_NEW'))
            diffs = merged[merged['_merge'] != 'both']
            st.metric("Total Discrepancies", len(diffs))
            st.dataframe(diffs, use_container_width=True)

def multi_key_tab():
    st.subheader("🔗 Multi-Key Advanced Join")
    c1, c2 = st.columns(2)
    with c1: l_file = st.file_uploader("Base Table", type=["csv", "xlsx"])
    with c2: r_file = st.file_uploader("Lookup Table", type=["csv", "xlsx"])
    
    if l_file and r_file:
        ldf, rdf = load_data(l_file), load_data(r_file)
        lk = st.multiselect("Match columns (Base):", ldf.columns)
        rk = st.multiselect("Match columns (Lookup):", rdf.columns)
        if st.button("🔗 Link Datasets") and len(lk) == len(rk) > 0:
            result = pd.merge(ldf, rdf, left_on=lk, right_on=rk, how='left')
            st.dataframe(result.head(10), use_container_width=True)

# --- 7. AUTHENTICATION PAGES ---

def auth_page():
    _, center, _ = st.columns([1, 2, 1])
    with center:
        if os.path.exists("image_cb68b62a.png"): st.image("image_cb68b62a.png", width=100)
        
        if st.session_state.auth_mode == 'login':
            st.header("LinkLab Login")
            email = st.text_input("Email")
            pw = st.text_input("Password", type="password")
            if st.button("Sign In", use_container_width=True, type="primary"):
                user = db_engine.authenticate(email, pw)
                if user:
                    st.session_state.logged_in = True
                    st.session_state.user = {"name": user[0], "email": user[1]}
                    st.rerun()
                else: st.error("Incorrect email or password")
            
            c1, c2 = st.columns(2)
            if c1.button("Forgot Password?"): st.session_state.auth_mode = 'forgot'; st.rerun()
            if c2.button("Register Account"): st.session_state.auth_mode = 'register'; st.rerun()

        elif st.session_state.auth_mode == 'register':
            st.header("Create Account")
            fn = st.text_input("First Name")
            em = st.text_input("Email Address")
            pw = st.text_input("Password", type="password")
            if st.button("Register", use_container_width=True, type="primary"):
                if db_engine.add_user(fn, em, pw):
                    st.success("Account created! Please login."); st.session_state.auth_mode = 'login'; st.rerun()
                else: st.error("Email already registered.")
            if st.button("Back to Login"): st.session_state.auth_mode = 'login'; st.rerun()

        elif st.session_state.auth_mode == 'forgot':
            st.header("Reset Password")
            st.info("Verify your identity.")
            em = st.text_input("Email")
            fn = st.text_input("Confirm First Name")
            npw = st.text_input("New Password", type="password")
            if st.button("Update Password", use_container_width=True, type="primary"):
                if db_engine.reset_password(em, fn, npw):
                    st.success("Updated! Login now."); st.session_state.auth_mode = 'login'; st.rerun()
                else: st.error("Verification failed.")
            if st.button("Cancel"): st.session_state.auth_mode = 'login'; st.rerun()

# --- 8. MAIN ROUTER ---

if not st.session_state.logged_in:
    auth_page()
else:
    # --- HEADER BAR ---
    h_left, h_right = st.columns([4, 1])
    with h_left:
        st.markdown(f"### LinkLab | 👋 Hello, {st.session_state.user['name']}")
    with h_right:
        with st.popover("👤 Profile"):
            st.write(f"**User:** {st.session_state.user['email']}")
            if st.button("🚪 Logout", use_container_width=True):
                st.session_state.logged_in = False
                st.rerun()

    # --- HORIZONTAL TABS ---
    tab_home, tab_merge, tab_audit, tab_join = st.tabs([
        "🏠 Home", "📊 Data Merger", "🔍 Audit Tool", "🔗 Multi-Key Join"
    ])

    with tab_home: home_tab()
    with tab_merge: merger_tab()
    with tab_audit: audit_tab()
    with tab_join: multi_key_tab()
