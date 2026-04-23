import streamlit as st
import pandas as pd
import numpy as np
import io
import sqlite3
import os
import textwrap
import zipfile
from python-calamine import CalamineWorkbook

# --- 1. GLOBAL CONFIGURATION ---
st.set_page_config(
    page_title="LinkLab | Professional Data Suite",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="collapsed"
)
pd.set_option("styler.render.max_elements", 20000000)

# --- 2. CSS STYLING ---
st.markdown("""
<style>
 [data-testid="stSidebar"] {display: none;}
 .main { background-color: #fcfcfc; }
 .stTabs [data-baseweb="tab-list"] { gap: 30px; border-bottom: 2px solid #e0e0e0; }
 .stTabs [data-baseweb="tab"] { 
    height: 70px; 
    font-weight: 700; 
    font-size: 20px; 
    padding-left: 20px; 
    padding-right: 20px; 
 }
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
            conn.execute('''CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                first_name TEXT, 
                last_name TEXT, 
                email TEXT UNIQUE, 
                password TEXT)''')
    def authenticate(self, email, password):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT first_name, email FROM users WHERE email = ? AND password = ?', (email, password))
            return cursor.fetchone()
    def add_user(self, first, last, email, pw):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('INSERT INTO users (first_name, last_name, email, password) VALUES (?, ?, ?, ?)', (first, last, email, pw))
                return True
        except: return False

db_engine = DBManager()

# --- 4. SESSION STATE INITIALIZATION ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'auth_mode' not in st.session_state: st.session_state.auth_mode = 'login'
if 'u_name' not in st.session_state: st.session_state.u_name = "User"
if 'u_email' not in st.session_state: st.session_state.u_email = ""
if "uploader_key" not in st.session_state: st.session_state["uploader_key"] = 0

def reset_all_tools():
    st.session_state["uploader_key"] += 1
    # Clear specific tool states
    keys_to_clear = ['dupe_df', 'matrix_df', 'audit', 'final_export_cols', 'audit_results']
    for key in keys_to_clear:
        if key in st.session_state: del st.session_state[key]
    st.cache_data.clear()

# --- 5. DATA UTILITIES ---
@st.cache_data(show_spinner="Loading laboratory data...")
def load_data(file):
    if file is None: return None
    try:
        if file.name.lower().endswith('.csv'): return pd.read_csv(file)
        return pd.read_excel(file, engine='calamine')
    except Exception as e:
        st.error(f"Error loading file: {e}")
        return None

# --- 6. PAGE FUNCTIONS ---

def home_tab():
    st.title("🔬 LinkLab Workspace Guide")
    st.write("### Your Digital Laboratory for Data Excellence")
    st.divider()
    st.markdown(""" 
    #### 🌟 Why LinkLab is your most valuable data asset:
    Professional data management is often plagued by fragmentation and manual errors. LinkLab eliminates these hurdles by providing automated logic for complex tasks.
    * **Unify Fragments:** Stop manual copy-pasting. Merge 20+ files into one master source in seconds. 
    * **Audit with Precision:** Automatically catch modified prices, inventory changes, or missing entries between versions. 
    * **Solve Join Complexity:** Perform horizontal lookups using multiple match points to ensure 100% linking accuracy. 
    * **System Ready:** Format your long descriptions to meet the character limits of ERP and Legacy systems without breaking words. 
    """)
    st.info("💡 **Select a tab above** to choose your specialized laboratory tool.")

def merger_tab():
    c_title, c_reset = st.columns([8,1])
    c_title.header("📊 Data Merger & Multi-Column Split")
    c_reset.button("🔄 Clear & Reset", on_click=reset_all_tools, key="res_merger", use_container_width=True)
    
    st.markdown("""<div class="guide-box"> 
    <b>Process Workflow:</b><br> 
    <span class="step-num">1.</span> Input the number of files you need to stack.<br> 
    <span class="step-num">2.</span> Upload your datasets (CSV or Excel).<br> 
    <span class="step-num">3.</span> Use Column Alignment if headers differ across files.<br> 
    <span class="step-num">4.</span> Review the preview and <b>Download</b> a master file or ZIP archive.
    </div>""", unsafe_allow_html=True)
    
    c_set, c_clean = st.columns(2)
    with c_set:
        st.subheader("1. Settings")
        num_files = st.number_input("Number of files to merge", 2, 10, 2)
        naming_option = st.radio("Are column names the same across all files?", ("Yes", "No"))
    with c_clean:
        st.subheader("2. Data Cleaning")
        remove_duplicates = st.checkbox("Remove Duplicate Rows", value=True)
        handle_nulls = st.selectbox("Handle Missing Values", ["No Action", "Drop Rows", "Fill with 0"])

    uploaded_files = [st.file_uploader(f"Upload File {i+1}", type=['xlsx', 'csv'], key=f"m_{i}_{st.session_state['uploader_key']}") for i in range(num_files)]
    
    if all(uploaded_files):
        dataframes = [load_data(f) for f in uploaded_files if f]
        if len(dataframes) == num_files:
            base_cols = list(dataframes[0].columns)
            final_dfs = []
            
            st.subheader("📄 File Previews & Alignment")
            for idx, df in enumerate(dataframes):
                with st.expander(f"Preview: {uploaded_files[idx].name}"):
                    st.dataframe(df.head(3), use_container_width=True)
                    if naming_option == "No" and idx > 0:
                        st.info(f"Map columns for {uploaded_files[idx].name} to match the first file:")
                        rename_dict = { col: st.selectbox(f"Map '{col}' to:", base_cols, key=f"map_{idx}_{col}") for col in df.columns }
                        final_dfs.append(df.rename(columns=rename_dict))
                    else:
                        final_dfs.append(df)

            st.divider()
            st.subheader("📁 Export Settings")
            split_cols = st.multiselect("Select Column(s) to split data into multiple files (ZIP):", options=base_cols)
            
            if st.button("🚀 Process & Prepare Export", type="primary", use_container_width=True):
                result = pd.concat(final_dfs, axis=0, ignore_index=True)
                if remove_duplicates: result = result.drop_duplicates()
                if handle_nulls == "Drop Rows": result = result.dropna()
                elif handle_nulls == "Fill with 0": result = result.fillna(0)

                if split_cols:
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                        for group_keys, subset in result.groupby(split_cols):
                            name_str = "_".join([str(k) for k in group_keys])
                            excel_buffer = io.BytesIO()
                            with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
                                subset.to_excel(writer, index=False)
                            zip_file.writestr(f"Export_{name_str}.xlsx", excel_buffer.getvalue())
                    st.download_button("📥 Download ZIP Archive", zip_buffer.getvalue(), "split_exports.zip", use_container_width=True)
                else:
                    excel_buffer = io.BytesIO()
                    with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
                        result.to_excel(writer, index=False)
                    st.download_button("📥 Download Full Merged Data", excel_buffer.getvalue(), "merged_data.xlsx", use_container_width=True)

def audit_tab():
    c_title, c_reset = st.columns([8,1])
    c_title.header("🚀 High-Speed Precision Comparer")
    c_reset.button("🔄 Clear & Reset", on_click=reset_all_tools, key="res_audit", use_container_width=True)
    
    st.markdown("""<div class="guide-box"> 
    <b>Process Workflow:</b><br> 
    <span class="step-num">1.</span> Upload your <b>Reference</b> file (the master version).<br> 
    <span class="step-num">2.</span> Upload the <b>New</b> file (the version to verify).<br> 
    <span class="step-num">3.</span> Select the <b>Unique Keys</b> (e.g., ID or SKU) to map rows.<br> 
    <span class="step-num">4.</span> View the <b>Mismatch Report</b> to see side-by-side changes.
    </div>""", unsafe_allow_html=True)
    
    ac1, ac2 = st.columns(2)
    with ac1: f1 = st.file_uploader("Upload Reference Dataset", type=["csv", "xlsx"], key=f"au1_{st.session_state['uploader_key']}")
    with ac2: f2 = st.file_uploader("Upload New Dataset", type=["csv", "xlsx"], key=f"au2_{st.session_state['uploader_key']}")

    if f1 and f2:
        df1, df2 = load_data(f1), load_data(f2)
        common_cols = [c for c in df1.columns if c in df2.columns]
        with st.expander("⚙️ Configuration Settings", expanded=True):
            col_k, col_c = st.columns(2)
            keys = col_k.multiselect("Select Unique Key(s):", options=common_cols)
            remaining = [c for c in common_cols if c not in keys]
            sel_all = col_c.checkbox("Select All Columns")
            comps = col_c.multiselect("Select Columns to Compare:", options=remaining, default=remaining if sel_all else [])
            clean_dupes = st.checkbox("Automatically clean duplicates (Keep first instance)")

        if st.button("🚀 Run Analysis", type="primary", use_container_width=True) and keys:
            if clean_dupes:
                df1, df2 = df1.drop_duplicates(subset=keys), df2.drop_duplicates(subset=keys)
            
            for c in keys:
                df1[c], df2[c] = df1[c].astype(str).str.strip(), df2[c].astype(str).str.strip()
            
            df_all = pd.merge(df1[list(set(keys + comps))], df2[list(set(keys + comps))], on=keys, how='outer', suffixes=('_F1', '_F2'), indicator=True)
            orph_f1 = df_all[df_all['_merge'] == 'left_only'].drop(columns=['_merge'])
            orph_f2 = df_all[df_all['_merge'] == 'right_only'].drop(columns=['_merge'])
            df_matched = df_all[df_all['_merge'] == 'both'].copy()
            
            final_report = pd.DataFrame()
            if not df_matched.empty and comps:
                d1_v, d2_v = df_matched[[f"{c}_F1" for c in comps]].fillna('N/A').values, df_matched[[f"{c}_F2" for c in comps]].fillna('N/A').values
                for i, col in enumerate(comps):
                    df_matched[f"{col}_Diff"] = np.where(d1_v[:, i] != d2_v[:, i], "DIFF", "")
                final_report = df_matched[(d1_v != d2_v).any(axis=1)].copy()
                ordered = list(keys)
                for col in comps: ordered.extend([f"{col}_F1", f"{col}_F2", f"{col}_Diff"])
                final_report = final_report[ordered]
            st.session_state['audit'] = {'report': final_report, 'o1': orph_f1, 'o2': orph_f2, 'met': (len(df_matched), len(orph_f1), len(orph_f2))}

    if 'audit' in st.session_state:
        res = st.session_state['audit']
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Matched", res['met'][0]); m2.metric("Only F1", res['met'][1]); m3.metric("Only F2", res['met'][2]); m4.metric("Mismatch Rows", len(res['report']))
        if not res['report'].empty:
            st.subheader("🚩 Mismatched Data (Side-by-Side)")
            st.dataframe(res['report'].head(1000).style.applymap(lambda x: 'background-color: #ffcccc; color: #900; font-weight: bold;' if x == "DIFF" else '', subset=[c for c in res['report'].columns if c.endswith('_Diff')]), use_container_width=True)
        
        st.divider()
        st.subheader("🔍 Orphan Records")
        oc1, oc2 = st.columns(2)
        with oc1:
            st.write(f"**Dataset 1 Only ({len(res['o1'])})**")
            st.dataframe(res['o1'].head(500), use_container_width=True)
        with oc2:
            st.write(f"**Dataset 2 Only ({len(res['o2'])})**")
            st.dataframe(res['o2'].head(500), use_container_width=True)
        
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as w:
            if not res['report'].empty: res['report'].to_excel(w, index=False, sheet_name='Mismatches')
            res['o1'].to_excel(w, index=False, sheet_name='Only_F1')
            res['o2'].to_excel(w, index=False, sheet_name='Only_F2')
        st.download_button("💾 Download Full Audit (.xlsx)", buf.getvalue(), "Audit_Report.xlsx", use_container_width=True)

def join_tab():
    c_title, c_reset = st.columns([8,1])
    c_title.header("🚀 Advanced Multi-Column LookUp")
    c_reset.button("🔄 Clear & Reset", on_click=reset_all_tools, key="res_join", use_container_width=True)
    st.markdown("""<div class="guide-box"> 
    <b>Process Workflow:</b><br> 
    <span class="step-num">1.</span> Load Main Table and Table to Join.<br> 
    <span class="step-num">2.</span> Select matching Key Column(s).<br> 
    <span class="step-num">3.</span> Execute horizontal join and export.
    </div>""", unsafe_allow_html=True)
    
    col_a, col_b = st.columns(2)
    with col_a: f1 = st.file_uploader("Main Table", type=['csv', 'xlsx', 'parquet'], key=f"j1_{st.session_state['uploader_key']}")
    with col_b: f2 = st.file_uploader("Table to Join", type=['csv', 'xlsx', 'parquet'], key=f"j2_{st.session_state['uploader_key']}")
    if f1 and f2:
        df1, df2 = load_data(f1), load_data(f2)
        c1, c2, c3 = st.columns(3)
        with c1: left_keys = st.multiselect("Keys (Main Table)", df1.columns)
        with c2: right_keys = st.multiselect("Keys (Second Table)", df2.columns)
        with c3: join_type = st.selectbox("Join Type", ["left", "right", "inner", "outer"])
        
        s1, s2 = st.columns(2)
        suffix_left = s1.text_input("Suffix for Main Table", "_left")
        suffix_right = s2.text_input("Suffix for Second Table", "_right")
        
        if st.button("🚀 Merge Datasets", use_container_width=True) and len(left_keys) == len(right_keys) > 0:
            result = pd.merge(df1, df2, left_on=left_keys, right_on=right_keys, how=join_type, suffixes=(suffix_left, suffix_right))
            st.success(f"Merged successfully! Rows: {len(result)}")
            st.dataframe(result.head(100))
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as w: result.to_excel(w, index=False)
            st.download_button("Download Result", excel_buffer.getvalue(), "merged_result.xlsx", use_container_width=True)

def splitter_tab():
    c_title, c_reset = st.columns([8,1])
    c_title.header("✂️ Text Column Splitter")
    c_reset.button("🔄 Clear & Reset", on_click=reset_all_tools, key="res_split", use_container_width=True)
    st.markdown("""<div class="guide-box"> 
    <b>Process Workflow:</b><br> 
    <span class="step-num">1.</span> Set your required <b>Character Limit</b> per column.<br> 
    <span class="step-num">2.</span> Upload your file and select the long description column.<br> 
    <span class="step-num">3.</span> Click <b>Generate</b> to split text into Part_1, Part_2, etc.
    </div>""", unsafe_allow_html=True)
    
    max_len = st.number_input("Character Limit per Column:", 1, 500, 50)
    up = st.file_uploader("Upload File:", type=["csv", "xlsx"], key=f"s1_{st.session_state['uploader_key']}")
    if up:
        df = load_data(up)
        col = st.selectbox("Select Column to Process:", df.columns)
        if st.button("Generate New Columns", type="primary", use_container_width=True):
            def wrap_text(t, m): return textwrap.wrap(str(t), width=m, break_long_words=False) if pd.notna(t) else []
            chunks = df[col].apply(lambda x: wrap_text(x, max_len))
            new_cols = pd.DataFrame(chunks.tolist())
            new_cols.columns = [f"Part_{i+1}" for i in range(new_cols.shape[1])]
            st.dataframe(pd.concat([df, new_cols], axis=1).head(10))

def duplicate_auditor_tab():
    c_title, c_reset = st.columns([8,1])
    c_title.header("🧬 Advanced Duplicate Finder")
    c_reset.button("🔄 Clear & Reset", on_click=reset_all_tools, key="res_dupe", use_container_width=True)
    
    # Process Guide Restored
    st.markdown("""<div class="guide-box"> 
    <b>Process Workflow:</b><br> 
    <span class="step-num">1.</span> Upload the file you wish to audit for duplicates.<br> 
    <span class="step-num">2.</span> Choose the column to check for <b>duplicates</b>.<br> 
    <span class="step-num">3.</span> (Optional) Select a column to <b>Pivot</b> for status counts and additional columns to <b>Spread</b>.<br> 
    <span class="step-num">4.</span> Review the <b>Verification Matrix</b> and download your reports.
    </div>""", unsafe_allow_html=True)
    
    uploaded_file = st.file_uploader("Upload File", type=['xlsx', 'csv'], key=f"up_dupe_{st.session_state['uploader_key']}")
    if uploaded_file:
        df_p = load_data(uploaded_file)
        all_cols = df_p.columns.tolist()
        st.subheader("Step 1: Configuration & Filters")
        c1, c2, c3 = st.columns(3)
        with c1:
            dup_col = st.selectbox("Find duplicates in:", options=all_cols)
            exclude_input = st.text_input("🚫 Exact Clean Values to THROW AWAY (comma separated):")
        with c2:
            count_col = st.selectbox("Select column to pivot (Y/N Count):", options=[None] + all_cols)
            sel_all = st.checkbox("Select All for Export")
            export_cols = st.multiselect("Keep in export:", options=all_cols, default=all_cols if sel_all else [])
        with c3:
            verification_cols = st.multiselect("Matrix Columns (spread into headers):", options=all_cols, default=[])

        if st.button("🚀 Process & Filter Data", type="primary", use_container_width=True):
            df = load_data(uploaded_file)
            df['Clean_Key'] = df[dup_col].astype(str).str.replace(r'[^a-zA-Z0-9.]', '', regex=True).str.lower().str.strip()
            if exclude_input:
                keywords = [k.strip().lower() for k in exclude_input.split(",") if k.strip()]
                df = df[~df['Clean_Key'].isin(keywords)]
            
            mask = df['Clean_Key'].duplicated(keep=False)
            dupe_df = df.loc[mask].copy()
            if not dupe_df.empty:
                matrix = dupe_df['Clean_Key'].value_counts().reset_index(); matrix.columns = ['Clean_Key', 'Total_Rows_in_Group']
                if count_col:
                    dupe_df[count_col] = dupe_df[count_col].astype(str).str.upper().str.strip()
                    pivot = dupe_df.groupby(['Clean_Key', count_col]).size().unstack(fill_value=0)
                    pivot = pivot.rename(columns={col: f"{count_col}_{col}_Count" for col in pivot.columns})
                    matrix = pd.merge(matrix, pivot, on='Clean_Key', how='left')
                for col in verification_cols:
                    u_vals = dupe_df.groupby('Clean_Key')[col].unique().apply(list).reset_index()
                    expanded = pd.DataFrame(u_vals[col].tolist(), index=u_vals['Clean_Key'])
                    expanded.columns = [f"{col}_{i+1}" for i in range(expanded.shape[1])]
                    matrix = pd.merge(matrix, expanded, on='Clean_Key', how='left')
                
                st.session_state['dupe_df'] = dupe_df
                st.session_state['matrix_df'] = matrix
                st.session_state['final_export_cols'] = ['Clean_Key'] + [c for c in export_cols if c != 'Clean_Key']

        if 'dupe_df' in st.session_state:
            st.success(f"✅ Found {len(st.session_state['dupe_df'])} duplicates.")
            st.subheader("📊 Verification Matrix Preview")
            st.dataframe(st.session_state['matrix_df'].head(100), use_container_width=True)
            d1, d2 = st.columns(2)
            buf1, buf2 = io.BytesIO(), io.BytesIO()
            with pd.ExcelWriter(buf1, engine='xlsxwriter') as w: st.session_state['dupe_df'][st.session_state['final_export_cols']].to_excel(w, index=False)
            with pd.ExcelWriter(buf2, engine='xlsxwriter') as w: st.session_state['matrix_df'].to_excel(w, index=False)
            d1.download_button("📥 Download Duplicates", buf1.getvalue(), "duplicates.xlsx", use_container_width=True)
            d2.download_button("📥 Download Matrix", buf2.getvalue(), "matrix.xlsx", use_container_width=True)

# --- 7. AUTHENTICATION UI & ROUTING ---

if not st.session_state.logged_in:
    col_l, col_r = st.columns([1, 1.2], gap="large")
    with col_r:
        st.title("🔬 LinkLab")
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
                u = db_engine.authenticate(em, pw)
                if u:
                    st.session_state.logged_in = True
                    st.session_state.u_name = u[0]
                    st.session_state.u_email = u[1]
                    st.rerun()
                else: st.error("Login failed.")
            c1, c2 = st.columns([1,0.75])
            if c1.button("Forgot Password?"): st.session_state.auth_mode = 'forgot'; st.rerun()
            if c2.button("Don't Have an Account ? Register"): st.session_state.auth_mode = 'register'; st.rerun()
        elif st.session_state.auth_mode == 'register':
            st.header("Register Account")
            fn = st.text_input("First Name")
            ln = st.text_input("Last Name")
            em = st.text_input("Email Address")
            pw = st.text_input("Create Password", type="password")
            if st.button("Register", type="primary", use_container_width=True):
                if db_engine.add_user(fn, ln, em, pw): 
                    st.success("Account created! Please Login.")
                    st.session_state.auth_mode = 'login'; st.rerun()
                else: st.error("Email already in use.")
            if st.button("Back to Login", use_container_width=True): st.session_state.auth_mode = 'login'; st.rerun()
else:
    cl, cr = st.columns([8,1])
    cl.write(f"### LinkLab | 👋 Welcome, {st.session_state.u_name}")
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
