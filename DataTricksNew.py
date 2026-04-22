import streamlit as st
import pandas as pd
import numpy as np
import io
import sqlite3
import os
import textwrap

# --- 1. GLOBAL CONFIGURATION ---
st.set_page_config(
    page_title="LinkLab | Professional Data Suite",
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
    .guide-card { 
        background-color: #ffffff; 
        padding: 20px; 
        border-radius: 10px; 
        border: 1px solid #e0e0e0; 
        margin-bottom: 15px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }
    .step-text { color: #007bff; font-weight: bold; }
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

# --- 4. SESSION STATE INITIALIZATION ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'auth_mode' not in st.session_state: st.session_state.auth_mode = 'login'
if 'u_name' not in st.session_state: st.session_state.u_name = ""
if 'u_email' not in st.session_state: st.session_state.u_email = ""

# --- 5. DATA UTILITIES ---
@st.cache_data(show_spinner=False)
def load_data(file):
    return pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)

# --- 6. PAGE CONTENT FUNCTIONS ---

def home_tab():
    st.title("🔬 LinkLab Workspace Guide")
    st.write("### Transform Fragmented Data into Actionable Insights")
    st.divider()

    col_info, col_img = st.columns([2, 1])
    
    with col_info:
        st.markdown("#### Why use LinkLab?")
        st.write("""
        In professional environments, data often arrives in pieces—multiple files, inconsistent versions, or 
        unformatted text. LinkLab provides a **centralized, automated environment** to clean, link, 
        and verify this data without writing a single line of code.
        """)

        st.markdown("---")
        
        st.markdown("#### 📊 Data Merger (Stacking)")
        st.info("**Best for:** Monthly reports or regional data that need to be unified into one master sheet.")
        
        st.markdown("#### 🔍 Audit Tool (Comparison)")
        st.info("**Best for:** Comparing 'Reference' data against 'New' data to find price changes, missing items, or errors.")
        
        st.markdown("#### 🔗 Multi-Key Join (Advanced VLOOKUP)")
        st.info("**Best for:** Linking two different datasets when a single ID isn't enough (matching by Name AND Date).")
        
        st.markdown("#### ✂️ Text Splitter (Formatting)")
        st.info("**Best for:** Preparing long descriptions for ERP systems that have strict character limits per column.")

def merger_tab():
    st.header("📊 Data Merger & Splitter")
    st.markdown("""
    <div class="guide-box">
    <span class="step-text">STEP 1:</span> Choose the number of files (2-20).<br>
    <span class="step-text">STEP 2:</span> Upload all files (CSV or Excel).<br>
    <span class="step-text">STEP 3:</span> Click <b>Run Merger</b>. The system will auto-detect columns and remove duplicates.<br>
    <span class="step-text">STEP 4:</span> Review the preview and <b>Download</b> the combined Excel.
    </div>
    """, unsafe_allow_html=True)
    st.write("")
    
    num = st.number_input("Number of files to unify:", 2, 20, 2)
    files = [st.file_uploader(f"Upload Dataset {i+1}", type=["csv", "xlsx"], key=f"m_{i}") for i in range(num)]
    
    if all(files):
        if st.button("🚀 Run Merger", use_container_width=True):
            dfs = [load_data(f) for f in files]
            res = pd.concat(dfs, axis=0, ignore_index=True).drop_duplicates()
            st.success(f"Unified {len(res)} rows successfully.")
            st.dataframe(res.head(10))
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine='xlsxwriter') as w: res.to_excel(w, index=False)
            st.download_button("📥 Download Master File", out.getvalue(), "linklab_master_merge.xlsx")

def audit_tab():
    st.header("🔍 Precision Audit Tool")
    st.markdown("""
    <div class="guide-box">
    <span class="step-text">STEP 1:</span> Upload your <b>Reference</b> file (the source of truth).<br>
    <span class="step-text">STEP 2:</span> Upload the <b>New</b> file (to be checked).<br>
    <span class="step-text">STEP 3:</span> Select the <b>Unique Key</b> (e.g., SKU, ID, or Email).<br>
    <span class="step-text">STEP 4:</span> Click <b>Run Comparison</b> to identify missing or modified rows.
    </div>
    """, unsafe_allow_html=True)
    st.write("")

    c1, c2 = st.columns(2)
    with c1: f1 = st.file_uploader("Reference File (Old)", type=["csv", "xlsx"], key="a1")
    with c2: f2 = st.file_uploader("New File (To Check)", type=["csv", "xlsx"], key="a2")
    
    if f1 and f2:
        df1, df2 = load_data(f1), load_data(f2)
        keys = st.multiselect("Identify columns to match by (Unique Keys):", df1.columns)
        if st.button("Run Audit") and keys:
            merged = pd.merge(df1, df2, on=keys, how='outer', indicator=True)
            diffs = merged[merged['_merge'] != 'both']
            st.metric("Discrepancies Found", len(diffs))
            st.dataframe(diffs)

def join_tab():
    st.header("🔗 Multi-Key Join")
    st.markdown("""
    <div class="guide-box">
    <span class="step-text">STEP 1:</span> Upload <b>Base Table</b> (Main data).<br>
    <span class="step-text">STEP 2:</span> Upload <b>Lookup Table</b> (The source for extra info).<br>
    <span class="step-text">STEP 3:</span> Match columns from both (e.g., match 'Emp_ID' to 'Staff_Code').<br>
    <span class="step-text">STEP 4:</span> Click <b>Execute</b> to merge columns horizontally.
    </div>
    """, unsafe_allow_html=True)
    st.write("")

    c1, c2 = st.columns(2)
    with c1: l_file = st.file_uploader("Base Table", type=["csv", "xlsx"], key="j1")
    with c2: r_file = st.file_uploader("Lookup Table", type=["csv", "xlsx"], key="j2")
    
    if l_file and r_file:
        ldf, rdf = load_data(l_file), load_data(r_file)
        lk = st.multiselect("Match column(s) from Base:", ldf.columns)
        rk = st.multiselect("Match column(s) from Lookup:", rdf.columns)
        if st.button("🔗 Execute Join") and len(lk) == len(rk) > 0:
            res = pd.merge(ldf, rdf, left_on=lk, right_on=rk, how='left')
            st.success("Data Linked Successfully!")
            st.dataframe(res.head(10))

def splitter_tab():
    st.header("✂️ Text Column Splitter")
    st.markdown("""
    <div class="guide-box">
    <span class="step-text">STEP 1:</span> Set the <b>Max Characters</b> allowed per column (default 50).<br>
    <span class="step-text">STEP 2:</span> Upload your file and select the long text column.<br>
    <span class="step-text">STEP 3:</span> Click <b>Generate</b>. The app splits text without breaking words.<br>
    <span class="step-text">STEP 4:</span> Download the Excel with 'Part_1', 'Part_2', etc., columns added.
    </div>
    """, unsafe_allow_html=True)
    st.write("")

    max_len = st.number_input("Character Limit per Column", 1, 500, 50)
    up_file = st.file_uploader("Upload File with long text:", type=["csv", "xlsx"], key="s1")
    
    if up_file:
        df = load_data(up_file)
        col = st.selectbox("Select Column to Split:", df.columns)
        if st.button("Generate New Columns", type="primary"):
            def wrap_text(t, m): return textwrap.wrap(str(t), width=m, break_long_words=False) if pd.notna(t) else []
            chunks = df[col].apply(lambda x: wrap_text(x, max_len))
            new_cols = pd.DataFrame(chunks.tolist())
            new_cols.columns = [f"Part_{i+1}" for i in range(new_cols.shape[1])]
            df_final = pd.concat([df, new_cols], axis=1)
            st.success("Text Splitting Completed!")
            st.dataframe(df_final.head(10))
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='xlsxwriter') as w: df_final.to_excel(w, index=False)
            st.download_button("📥 Download Split Results", buf.getvalue(), "linklab_split_results.xlsx")

# --- 7. AUTHENTICATION UI ---

if not st.session_state.logged_in:
    # --- LOGIN PAGE DESCRIPTION ---
    col_auth, col_intro = st.columns([1, 1.2], gap="large")
    
    with col_intro:
        st.image("image_cb68b62a.png", width=120) if os.path.exists("image_cb68b62a.png") else st.title("🔬 LinkLab")
        st.write("## Professional Data Management Made Simple")
        st.markdown("""
        LinkLab is an **all-in-one productivity engine** designed for data analysts, 
        accountants, and administrators. 
        
        **How this platform helps you:**
        *   🚀 **Save Time:** Automate repetitive manual Copy-Paste tasks in Excel.
        *   🛡️ **Reduce Errors:** Use algorithmic auditing to find hidden discrepancies.
        *   🔄 **Data Integrity:** Seamlessly merge data from multiple departments into one source of truth.
        *   📦 **Legacy Ready:** Format text instantly for ERP and older database uploads.
        """)

    with col_auth:
        if st.session_state.auth_mode == 'login':
            st.header("Login")
            em = st.text_input("Email")
            pw = st.text_input("Password", type="password")
            if st.button("Login", use_container_width=True, type="primary"):
                user_record = db.authenticate(em, pw)
                if user_record:
                    st.session_state.logged_in = True
                    st.session_state.u_name = user_record[0]
                    st.session_state.u_email = user_record[1]
                    st.rerun()
                else: st.error("Invalid credentials.")
            
            c1, c2 = st.columns(2)
            if c1.button("Forgot Password?"): st.session_state.auth_mode = 'forgot'; st.rerun()
            if c2.button("Register Account"): st.session_state.auth_mode = 'register'; st.rerun()

        elif st.session_state.auth_mode == 'register':
            st.header("Register")
            fn = st.text_input("First Name")
            em = st.text_input("Email")
            pw = st.text_input("Password", type="password")
            if st.button("Create Account", use_container_width=True, type="primary"):
                if db.add_user(fn, em, pw):
                    st.success("Registration Success! Please login."); st.session_state.auth_mode = 'login'; st.rerun()
                else: st.error("Email already exists.")
            if st.button("Back to Login"): st.session_state.auth_mode = 'login'; st.rerun()

        elif st.session_state.auth_mode == 'forgot':
            st.header("Reset Password")
            em = st.text_input("Registered Email")
            fn = st.text_input("First Name")
            np = st.text_input("New Password", type="password")
            if st.button("Update Password", use_container_width=True, type="primary"):
                if db.reset_password(em, fn, np):
                    st.success("Updated! Login now."); st.session_state.auth_mode = 'login'; st.rerun()
                else: st.error("Verification failed.")
            if st.button("Back"): st.session_state.auth_mode = 'login'; st.rerun()

else:
    # --- APP INTERFACE (POST-LOGIN) ---
    cl, cr = st.columns()
    with cl: st.write(f"### LinkLab | 👋 Welcome, {st.session_state.u_name}")
    with cr:
        with st.popover("👤 Account Settings"):
            st.write(f"Logged in as: **{st.session_state.u_email}**")
            if st.button("Logout", use_container_width=True):
                st.session_state.logged_in = False
                st.rerun()

    t_home, t_merger, t_audit, t_join, t_split = st.tabs([
        "🏠 Home", "📊 Data Merger", "🔍 Audit Tool", "🔗 Join Tool", "✂️ Text Splitter"
    ])

    with t_home: home_tab()
    with t_merger: merger_tab()
    with t_audit: audit_tab()
    with t_join: join_tab()
    with t_split: splitter_tab()
