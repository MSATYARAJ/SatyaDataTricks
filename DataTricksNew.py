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
 .stTabs [data-baseweb="tab-list"] { gap: 50px; border-bottom: 2px solid #e0e0e0; }
 .stTabs [data-baseweb="tab"] { height: 50px; font-weight: 600; font-size: 16px; }
 .stButton>button { border-radius: 4px; font-weight: bold; }
 /* Professional Guide Box */
 .guide-box { background-color: #e2f3fd; padding: 20px; border-radius: 10px; border-left: 5px solid #007bff; margin-bottom: 25px; }
 .step-num { color: #000000; font-weight: bold; margin-right: 5px; }
 </style>
 """, unsafe_allow_html=True)

# --- 3. DATABASE ENGINE ---
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
        except:
            return False
    def reset_password(self, email, first, new_pw):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('UPDATE users SET password = ? WHERE email = ? AND first_name = ?', (new_pw, email, first))
            return cursor.rowcount > 0

db_engine = DBManager()

# --- 4. SESSION STATE INITIALIZATION ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'auth_mode' not in st.session_state: st.session_state.auth_mode = 'login'
if 'u_name' not in st.session_state: st.session_state.u_name = "User"
if 'u_email' not in st.session_state: st.session_state.u_email = ""
if "uploader_key" not in st.session_state: st.session_state["uploader_key"] = 0

def reset_all_tools():
    st.session_state["uploader_key"] += 1
    if 'dupe_df' in st.session_state: del st.session_state['dupe_df']
    if 'matrix_df' in st.session_state: del st.session_state['matrix_df']
    st.cache_data.clear()
    st.rerun()

# --- 5. DATA UTILITIES ---
@st.cache_data(show_spinner=False)
def load_data(file):
    return pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)

# --- 6. PAGE FUNCTIONS ---
def home_tab():
    st.title("🔬 LinkLab Workspace Guide")
    st.write("### Your Digital Laboratory for Data Excellence")
    st.divider()
    st.markdown(""" 
    #### 🌟 Why LinkLab is your most valuable data asset:
    
    *   **Unify Fragments:** Stop manual copy-pasting. Merge 20+ files into one master source in seconds. 
    *   **Audit with Precision:** Automatically catch modified prices, inventory changes, or missing entries between versions. 
    *   **Solve Join Complexity:** Perform horizontal lookups using multiple match points to ensure 100% linking accuracy. 
    *   **System Ready:** Format your long descriptions to meet the character limits of ERP and Legacy systems without breaking words. 
    """)
    st.info("💡 **Select a tab above** to choose your specialized laboratory tool.")

def merger_tab():
    c_title, c_reset = st.columns([8, 1])
    c_title.header("📊 Data Merger & Splitter")
    c_reset.button("🔄 Clear & Reset", on_click=reset_all_tools, key="res_merger")
    st.markdown("""<div class="guide-box"> <b>Process Workflow:</b><br> <span class="step-num">1.</span> Input the number of files you need to stack.<br> <span class="step-num">2.</span> Upload your datasets (CSV or Excel).<br> <span class="step-num">3.</span> Click <b>Run Merger</b> to vertically unify data and remove duplicates.<br> <span class="step-num">4.</span> Review the preview and <b>Download</b> your Master File.</div>""", unsafe_allow_html=True)
    num = st.number_input("Number of files to unify:", 2, 20, 2)
    files = [st.file_uploader(f"Upload Dataset {i+1}", type=["csv", "xlsx"], key=f"m_{i}_{st.session_state['uploader_key']}") for i in range(num)]
    if all(files):
        if st.button("🚀 Run Merger", use_container_width=True):
            dfs = [load_data(f) for f in files]
            res = pd.concat(dfs, axis=0, ignore_index=True).drop_duplicates()
            st.success(f"Merged {len(res)} rows.")
            st.dataframe(res.head(10))
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine='xlsxwriter') as w:
                res.to_excel(w, index=False)
            st.download_button("📥 Download Master Excel", out.getvalue(), "merged_master.xlsx")

def audit_tab():
    c_title, c_reset = st.columns([8, 1])
    c_title.header("🔍 Precision Comaparison Tool")
    c_reset.button("🔄 Clear & Reset", on_click=reset_all_tools, key="res_audit")
    st.markdown("""<div class="guide-box"> <b>Process Workflow:</b><br> <span class="step-num">1.</span> Upload your <b>Reference</b> file (the master version).<br> <span class="step-num">2.</span> Upload the <b>New</b> file (the version to verify).<br> <span class="step-num">3.</span> Select the <b>Unique Keys</b> (e.g., ID or SKU) to map rows.<br> <span class="step-num">4.</span> View the <b>Mismatch Report</b> to see additions and modifications.</div>""", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1: f1 = st.file_uploader("Reference File", type=["csv", "xlsx"], key=f"a1_{st.session_state['uploader_key']}")
    with c2: f2 = st.file_uploader("New File", type=["csv", "xlsx"], key=f"a2_{st.session_state['uploader_key']}")
    if f1 and f2:
        df1, df2 = load_data(f1), load_data(f2)
        keys = st.multiselect("Match data based on (Unique Keys):", df1.columns)
        if st.button("Run Audit") and keys:
            merged = pd.merge(df1, df2, on=keys, how='outer', indicator=True)
            diffs = merged[merged['_merge'] != 'both']
            st.metric("Discrepancies Detected", len(diffs))
            st.dataframe(diffs)

def join_tab():
    c_title, c_reset = st.columns([8, 1])
    c_title.header("🔗 Advanced LookUp Tool")
    c_reset.button("🔄 Clear & Reset", on_click=reset_all_tools, key="res_join")
    st.markdown("""<div class="guide-box"> <b>Process Workflow:</b><br> <span class="step-num">1.</span> Load your <b>Base Table</b> (main file).<br> <span class="step-num">2.</span> Load your <b>Lookup Table</b> (file containing extra columns).<br> <span class="step-num">3.</span> Select matching columns in both files (multiple keys supported).<br> <span class="step-num">4.</span> Execute the <b>Horizontal Join</b> to merge columns.</div>""", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1: l_file = st.file_uploader("Base Table", type=["csv", "xlsx"], key=f"j1_{st.session_state['uploader_key']}")
    with c2: r_file = st.file_uploader("Lookup Table", type=["csv", "xlsx"], key=f"j2_{st.session_state['uploader_key']}")
    if l_file and r_file:
        ldf, rdf = load_data(l_file), load_data(r_file)
        lk = st.multiselect("Select Base Match Keys:", ldf.columns)
        rk = st.multiselect("Select Lookup Match Keys:", rdf.columns)
        if st.button("🔗 Execute Join") and len(lk) == len(rk) > 0:
            res = pd.merge(ldf, rdf, left_on=lk, right_on=rk, how='left')
            st.success("Data successfully linked horizontally.")
            st.dataframe(res.head(10))

def splitter_tab():
    c_title, c_reset = st.columns([8, 1])
    c_title.header("✂️ Text Column Splitter")
    c_reset.button("🔄 Clear & Reset", on_click=reset_all_tools, key="res_splitter")
    st.markdown("""<div class="guide-box"> <b>Process Workflow:</b><br> <span class="step-num">1.</span> Set your required <b>Character Limit</b> per column.<br> <span class="step-num">2.</span> Upload your file and select the long description column.<br> <span class="step-num">3.</span> Click <b>Generate</b> to split text into Part_1, Part_2, etc.<br> <span class="step-num">4.</span> <b>Download</b> the Excel file with the newly split columns.</div>""", unsafe_allow_html=True)
    max_len = st.number_input("Character Limit per Column:", 1, 500, 50)
    up_file = st.file_uploader("Upload File to Split:", type=["csv", "xlsx"], key=f"s1_{st.session_state['uploader_key']}")
    if up_file:
        df = load_data(up_file)
        col = st.selectbox("Select Column to Process:", df.columns)
        if st.button("Generate New Columns", type="primary"):
            def wrap_text(t, m): return textwrap.wrap(str(t), width=m, break_long_words=False) if pd.notna(t) else []
            chunks = df[col].apply(lambda x: wrap_text(x, max_len))
            new_cols = pd.DataFrame(chunks.tolist())
            new_cols.columns = [f"Part_{i+1}" for i in range(new_cols.shape[1])]
            df_final = pd.concat([df, new_cols], axis=1)
            st.success("Splitting successfully executed.")
            st.dataframe(df_final.head(10))
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='xlsxwriter') as w:
                df_final.to_excel(w, index=False)
            st.download_button("📥 Download Split Results", buf.getvalue(), "split_results.xlsx")

def duplicate_auditor_tab():
    # --- ORIGINAL CODE FROM FIRST SCRIPT ---
    col_title, col_clear = st.columns([8,1])
    with col_title: st.title("🔍 Advanced Duplicate Finder")
    with col_clear: st.button("🔄 Clear & Reset", on_click=reset_all_tools, key="res_dupe")
    st.markdown("""<div class="guide-box"> <b>Process Workflow:</b><br> <span class="step-num">1.</span> Upload the file you wish to audit for duplicates.<br> <span class="step-num">2.</span> Choose the column to check for <b>duplicates</b> (logic removes symbols/spaces automatically).<br> <span class="step-num">3.</span> (Optional) Select a column to <b>Pivot</b> for status counts and additional columns to <b>Spread</b> for visual verification.<br> <span class="step-num">4.</span> Review the <b>Verification Matrix</b> and download your reports.</div>""", unsafe_allow_html=True)
    uploaded_file = st.file_uploader("Upload File", type=['xlsx', 'csv'], key=f"up_{st.session_state['uploader_key']}")
    if uploaded_file:
        @st.cache_data
        def get_headers(file):
            if file.name.endswith('.csv'): return pd.read_csv(file, nrows=0).columns.tolist()
            return pd.read_excel(file, nrows=0).columns.tolist()
        all_cols = get_headers(uploaded_file)
        st.subheader("Step 1: Configuration & Filters")
        c1, c2, c3 = st.columns(3)
        with c1:
            dup_col = st.selectbox("Find duplicates in:", options=all_cols)
            exclude_input = st.text_input("🚫 Exact Clean Values to THROW AWAY (comma separated):")
        with c2:
            count_col = st.selectbox("Select column to pivot (Y/N Count):", options=[None] + all_cols)
            select_all = st.checkbox("Select All for Export")
            export_cols = st.multiselect("Keep in export:", options=all_cols, default=all_cols if select_all else [])
        with c3:
            verification_cols = st.multiselect("Matrix Columns (spread into headers):", options=all_cols, default=[])
        if st.button("🚀 Process & Filter Data", type="primary", use_container_width=True):
            with st.spinner("Processing..."):
                df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
                df['Clean_Key'] = df[dup_col].astype(str).str.replace(r'[^a-zA-Z0-9.]', '', regex=True).str.lower().str.strip()
                if exclude_input:
                    keywords = [k.strip().lower() for k in exclude_input.split(",") if k.strip()]
                    df = df[~df['Clean_Key'].isin(keywords)]
                mask = df['Clean_Key'].duplicated(keep=False)
                dupe_df = df.loc[mask].copy()
                if not dupe_df.empty:
                    counts = dupe_df['Clean_Key'].value_counts().reset_index()
                    counts.columns = ['Clean_Key', 'Total_Rows_in_Group']
                    matrix_df = counts.copy()
                    if count_col:
                        dupe_df[count_col] = dupe_df[count_col].astype(str).str.upper().str.strip()
                        status_counts = dupe_df.groupby(['Clean_Key', count_col]).size().unstack(fill_value=0)
                        status_counts = status_counts.rename(columns={col: f"{count_col}_{col}_Count" for col in status_counts.columns})
                        matrix_df = pd.merge(matrix_df, status_counts, on='Clean_Key', how='left')
                    for col in verification_cols:
                        u_vals = dupe_df.groupby('Clean_Key')[col].unique().apply(list).reset_index()
                        expanded = pd.DataFrame(u_vals[col].tolist(), index=u_vals['Clean_Key'])
                        expanded.columns = [f"{col}_{i+1}" for i in range(expanded.shape[1])]
                        matrix_df = pd.merge(matrix_df, expanded, on='Clean_Key', how='left')
                    st.session_state['dupe_df'] = dupe_df
                    st.session_state['matrix_df'] = matrix_df
                    st.session_state['final_export_cols'] = ['Clean_Key'] + [c for c in export_cols if c != 'Clean_Key']
        if 'dupe_df' in st.session_state:
            st.divider()
            st.success(f"✅ Data Processed. Found {len(st.session_state['dupe_df'])} duplicates.")
            st.subheader("📊 Verification Matrix Preview")
            st.dataframe(st.session_state['matrix_df'].head(100), use_container_width=True)
            st.subheader("📥 Download Section")
            d1, d2 = st.columns(2)
            buf1 = io.BytesIO()
            with pd.ExcelWriter(buf1, engine='xlsxwriter') as w:
                st.session_state['dupe_df'][st.session_state['final_export_cols']].to_excel(w, index=False)
            d1.download_button("📥 Download Duplicates", buf1.getvalue(), "duplicates.xlsx", use_container_width=True)
            buf2 = io.BytesIO()
            with pd.ExcelWriter(buf2, engine='xlsxwriter') as w:
                st.session_state['matrix_df'].to_excel(w, index=False)
            d2.download_button("📥 Download Matrix", buf2.getvalue(), "matrix.xlsx", use_container_width=True)

# --- 7. AUTHENTICATION UI & ROUTING ---
if not st.session_state.logged_in:
    col_l, col_r = st.columns([1, 1.2], gap="large")
    with col_r:
        if os.path.exists("image_cb68b62a.png"): st.image("image_cb68b62a.png", width=140)
        else: st.title("🔬 LinkLab")
        st.markdown("## Professional Data Management Platform")
        st.markdown(""" 
        LinkLab is an **Automated Data Laboratory** designed to eliminate the manual complexity of handling business datasets.
        
        **How this platform transforms your work:**
        *   **Vertical Merging:** Automatically stack disparate files into a single master sheet. 
        *   **Precision Auditing:** Algorithmic comparison to detect modified, added, or deleted data entries. 
        *   **Multi-Key Linking:** Perform advanced horizontal lookups where Excel's VLOOKUP fails. 
        *   **ERP Compatibility:** Instant text splitting to meet strict character constraints of industrial databases. 
        """)
    with col_l:
        if st.session_state.auth_mode == 'login':
            st.header("User Login")
            em = st.text_input("Email")
            pw = st.text_input("Password", type="password")
            if st.button("Sign In", use_container_width=True, type="primary"):
                user_record = db_engine.authenticate(em, pw)
                if user_record:
                    st.session_state.logged_in = True
                    st.session_state.u_name = user_record[0]
                    st.session_state.u_email = user_record[1]
                    st.rerun()
                else: st.error("Login failed. Please check your credentials.")
            c1, c2 = st.columns([1,0.75])
            if c1.button("Forgot Password?"): st.session_state.auth_mode = 'forgot'; st.rerun()
            if c2.button("Don't Have an Account ? Register"): st.session_state.auth_mode = 'register'; st.rerun()
        elif st.session_state.auth_mode == 'register':
            st.header("Register Account")
            fn = st.text_input("First Name")
            em = st.text_input("Email Address")
            pw = st.text_input("Create Password", type="password")
            if st.button("Register", use_container_width=True, type="primary"):
                if db_engine.add_user(fn, em, pw): st.success("Account created! Please login."); st.session_state.auth_mode = 'login'; st.rerun()
                else: st.error("Email already in use.")
            if st.button("Back to Login"): st.session_state.auth_mode = 'login'; st.rerun()
        elif st.session_state.auth_mode == 'forgot':
            st.header("Account Recovery")
            em = st.text_input("Registered Email")
            fn = st.text_input("Confirm First Name")
            np = st.text_input("New Password", type="password")
            if st.button("Reset Password", use_container_width=True, type="primary"):
                if db_engine.reset_password(em, fn, np): st.success("Updated! Login with your new password."); st.session_state.auth_mode = 'login'; st.rerun()
                else: st.error("Identity verification failed.")
            if st.button("Cancel"): st.session_state.auth_mode = 'login'; st.rerun()
else:
    cl, cr = st.columns([9,1])
    with cl: st.write(f"### LinkLab | 👋 Welcome, {st.session_state.u_name}")
    with cr:
        with st.popover("👤 Profile"):
            st.write(f"User: **{st.session_state.u_name}**")
            st.write(f"Logged in: **{st.session_state.u_email}**")
            if st.button("Logout", use_container_width=True):
                st.session_state.logged_in = False
                st.rerun()
    t_h, t_m, t_a, t_j, t_s, t_d = st.tabs(["🏠 Home", "📊 Merger", "🔍 Comparer", "🔗 Join", "✂️ Splitter", "🧬 Dupe Finder"])
    with t_h: home_tab()
    with t_m: merger_tab()
    with t_a: audit_tab()
    with t_j: join_tab()
    with t_s: splitter_tab()
    with t_d: duplicate_auditor_tab()

