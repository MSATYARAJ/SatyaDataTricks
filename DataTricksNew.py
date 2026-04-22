import streamlit as st
import pandas as pd
import numpy as np
import io
import zipfile
import sqlite3
from datetime import datetime

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
    
    /* Global Background and Text */
    .main { background-color: #f8f9fa; }
    
    /* Horizontal Tab Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 20px;
        border-bottom: 2px solid #e0e0e0;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        font-weight: 600;
        font-size: 16px;
        color: #4a4a4a;
    }
    .stTabs [data-baseweb="tab"]:hover { color: #007bff; }
    .stTabs [data-baseweb="tab"][aria-selected="true"] { color: #007bff; border-bottom-color: #007bff; }

    /* Profile Popover Styling */
    div[data-testid="stPopover"] > button {
        border-radius: 20px;
        border: 1px solid #ddd;
        padding: 5px 20px;
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

db = DBManager()

# --- 4. SESSION STATE MANAGEMENT ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'auth_mode' not in st.session_state: st.session_state.auth_mode = 'login'
if 'user' not in st.session_state: st.session_state.user = None
if 'shared_df' not in st.session_state: st.session_state.shared_df = None

# --- 5. CORE FUNCTIONALITY (TABS) ---

@st.cache_data(show_spinner=False)
def load_data(file):
    if file.name.endswith('.csv'):
        return pd.read_csv(file)
    return pd.read_excel(file)

def home_tab():
    c1, c2 = st.columns([1, 4])
    with c1: 
        try: st.image("image_cb68b62a.png", width=150)
        except: st.title("🔬 LinkLab")
    with c2:
        st.title("Welcome to LinkLab")
        st.write("### *The science of seamless data*")
    
    st.divider()
    st.markdown("""
    ### Current Capabilities:
    *   **Data Merger**: Append multiple sources and split by category.
    *   **Audit Tool**: Identify precision mismatches between datasets.
    *   **Multi-Key Join**: Perform advanced horizontal joins (VLOOKUP Replacement).
    """)

def merger_tab():
    st.subheader("📊 Append & Split Tool")
    num_files = st.number_input("Number of files to merge", 2, 20, 2)
    files = [st.file_uploader(f"Dataset {i+1}", type=["csv", "xlsx"], key=f"file_{i}") for i in range(num_files)]
    
    if all(files):
        dfs = [load_data(f) for f in files]
        if st.button("🚀 Run Merger", use_container_width=True):
            combined = pd.concat(dfs, axis=0, ignore_index=True).drop_duplicates()
            st.session_state.shared_df = combined
            st.success(f"Merged successfully! {len(combined)} rows processed.")
            st.dataframe(combined.head(10), use_container_width=True)
            
            # Export
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
                combined.to_excel(writer, index=False)
            st.download_button("📥 Download Master Excel", out.getvalue(), "master_data.xlsx")

def audit_tab():
    st.subheader("🔍 Precision Audit Tool")
    col1, col2 = st.columns(2)
    with col1: f1 = st.file_uploader("First Dataset (Old/Reference)", type=["csv", "xlsx"])
    with col2: f2 = st.file_uploader("Second Dataset (New/Active)", type=["csv", "xlsx"])
    
    if f1 and f2:
        df1, df2 = load_data(f1), load_data(f2)
        common_cols = list(set(df1.columns) & set(df2.columns))
        keys = st.multiselect("Select Unique Key(s):", common_cols)
        
        if st.button("Compare Datasets") and keys:
            merged = pd.merge(df1, df2, on=keys, how='outer', indicator=True, suffixes=('_REF', '_NEW'))
            diffs = merged[merged['_merge'] != 'both']
            st.metric("Discrepancies Found", len(diffs))
            st.dataframe(diffs, use_container_width=True)

def join_tab():
    st.subheader("🔗 Multi-Key Join")
    c1, c2 = st.columns(2)
    with c1: lf = st.file_uploader("Primary Table", type=["csv", "xlsx"])
    with c2: rf = st.file_uploader("Lookup Table", type=["csv", "xlsx"])
    
    if lf and rf:
        ldf, rdf = load_data(lf), load_data(rf)
        l_keys = st.multiselect("Left Keys:", ldf.columns)
        r_keys = st.multiselect("Right Keys:", rdf.columns)
        
        if st.button("🔗 Join Data") and len(l_keys) == len(r_keys) > 0:
            result = pd.merge(ldf, rdf, left_on=l_keys, right_on=r_keys, how='left')
            st.success("Join Complete.")
            st.dataframe(result.head(), use_container_width=True)

# --- 6. AUTHENTICATION UI ---

def render_auth():
    _, center, _ = st.columns([1, 2, 1])
    with center:
        st.image("image_cb68b62a.png", width=120) if 'image_cb68b62a.png' else None
        
        if st.session_state.auth_mode == 'login':
            st.header("LinkLab Login")
            e = st.text_input("Email")
            p = st.text_input("Password", type="password")
            if st.button("Login", use_container_width=True, type="primary"):
                user = db.authenticate(e, p)
                if user:
                    st.session_state.logged_in = True
                    st.session_state.user = {"name": user[0], "email": user[1]}
                    st.rerun()
                else: st.error("Invalid credentials.")
            
            c1, c2 = st.columns(2)
            if c1.button("Forgot Password?"): st.session_state.auth_mode = 'forgot'; st.rerun()
            if c2.button("Register Account"): st.session_state.auth_mode = 'register'; st.rerun()

        elif st.session_state.auth_mode == 'register':
            st.header("Register")
            fn = st.text_input("First Name")
            em = st.text_input("Email")
            pw = st.text_input("Create Password", type="password")
            if st.button("Create Account", use_container_width=True, type="primary"):
                if db.add_user(fn, em, pw):
                    st.success("Account created! Logging you in..."); st.session_state.auth_mode = 'login'; st.rerun()
                else: st.error("Email already in use.")
            if st.button("Back to Login"): st.session_state.auth_mode = 'login'; st.rerun()

        elif st.session_state.auth_mode == 'forgot':
            st.header("Reset Password")
            em = st.text_input("Email Address")
            fn = st.text_input("Confirm First Name")
            npw = st.text_input("New Password", type="password")
            if st.button("Reset Password", use_container_width=True, type="primary"):
                if db.reset_password(em, fn, npw):
                    st.success("Password reset! You can now login."); st.session_state.auth_mode = 'login'; st.rerun()
                else: st.error("Verification failed.")
            if st.button("Back"): st.session_state.auth_mode = 'login'; st.rerun()

# --- 7. MAIN APP ROUTER ---

if not st.session_state.logged_in:
    render_auth()
else:
    # Top Right User Menu
    h_left, h_right = st.columns([4, 1])
    with h_left:
        st.title("LinkLab")
    with h_right:
        with st.popover(f"👤 {st.session_state.user['name']}"):
            st.write(f"ID: {st.session_state.user['email']}")
            if st.button("Logout", use_container_width=True):
                st.session_state.logged_in = False
                st.rerun()

    # Horizontal Navigation
    tab1, tab2, tab3, tab4 = st.tabs(["🏠 Home", "📊 Merger", "🔍 Audit", "🔗 Join"])
    with tab1: home_tab()
    with tab2: merger_tab()
    with tab3: audit_tab()
    with tab4: join_tab()
