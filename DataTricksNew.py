import streamlit as st
import pandas as pd
import numpy as np
import io
import zipfile
import sqlite3

# --- 1. GLOBAL APP CONFIGURATION ---
st.set_page_config(page_title="LinkLab | Professional Data Tools", layout="wide")

# --- 2. DATABASE & AUTHENTICATION LOGIC ---
def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                 id INTEGER PRIMARY KEY AUTOINCREMENT, 
                 first_name TEXT, 
                 last_name TEXT, 
                 email TEXT UNIQUE, 
                 password TEXT)''')
    conn.commit()
    conn.close()

def authenticate_user(email, password):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE email = ? AND password = ?', (email, password))
    user = c.fetchone()
    conn.close()
    return user

def add_user(first, last, email, password):
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('INSERT INTO users (first_name, last_name, email, password) VALUES (?,?,?,?)', (first, last, email, password))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False

init_db()

# Initialize Session States
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'auth_page' not in st.session_state: st.session_state['auth_page'] = 'login'
if 'shared_df' not in st.session_state: st.session_state['shared_df'] = None

# --- 3. PAGE FUNCTIONS ---

def home_page():
    # Logo and Tagline
    col1, col2 = st.columns([1, 4])
    with col1:
        # Standard placeholder if the image file is missing
        try:
            st.image("image_cb68b62a.png", width=150)
        except:
            st.warning("Logo image missing.")
    with col2:
        st.title("LinkLab")
        st.write("### *The science of seamless data*")
    
    st.divider()
    st.markdown("""
    ### Master Your Data Complexity
    At **LinkLab**, we turn fragmented datasets into a single source of truth. 
    Our specialized environment provides the tools you need to:
    *   ✨ **Append** missing information seamlessly.
    *   🔗 **Merge** disparate sources with ease.
    *   🔍 **Compare** data with high-precision logic.
    """)
    st.info("👈 Select a tool from the sidebar to get started.")

def merger_page():
    st.title("📊 Append Data & Split Data")
    with st.sidebar:
        st.header("Settings")
        num_files = st.number_input("Number of files", 2, 20, 2)
        naming_opt = st.radio("Same column names?", ("Yes", "No"))
        st.header("Cleaning")
        rem_dup = st.checkbox("Remove Duplicates", value=True)
        null_h = st.selectbox("Missing Values", ["No Action", "Drop Rows", "Fill with 0"])

    def load_data(file):
        return pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)

    files = [st.file_uploader(f"File {i+1}", type=["xlsx", "xls", "csv"], key=f"m{i}") for i in range(num_files)]
    
    if all(files):
        dfs = [load_data(f) for f in files]
        base_cols = list(dfs[0].columns)
        final_dfs = []
        for i, df in enumerate(dfs):
            with st.expander(f"Preview: {files[i].name}"):
                st.dataframe(df.head(3))
                if naming_opt == "No" and i > 0:
                    rename_dict = {c: st.selectbox(f"Map '{c}' to:", base_cols, key=f"map{i}{c}") for c in df.columns}
                    final_dfs.append(df.rename(columns=rename_dict))
                else:
                    final_dfs.append(df)

        split_cols = st.multiselect("Split by Column(s) (Leave empty for full download):", options=base_cols)

        if st.button("🚀 Process & Prepare Export"):
            res = pd.concat(final_dfs, axis=0, ignore_index=True)
            if rem_dup: res = res.drop_duplicates()
            if null_h == "Drop Rows": res = res.dropna()
            elif null_h == "Fill with 0": res = res.fillna(0)
            
            st.session_state['shared_df'] = res 

            if split_cols:
                zip_buf = io.BytesIO()
                with zipfile.ZipFile(zip_buf, "a", zipfile.ZIP_DEFLATED, False) as z:
                    for keys, subset in res.groupby(split_cols):
                        name = "_".join([str(k) for k in keys]) if isinstance(keys, tuple) else str(keys)
                        eb = io.BytesIO()
                        with pd.ExcelWriter(eb, engine='xlsxwriter') as w: subset.to_excel(w, index=False)
                        z.writestr(f"Export_{name}.xlsx", eb.getvalue())
                st.success(f"Generated {len(res.groupby(split_cols))} files.")
                st.download_button("📥 Download ZIP", zip_buf.getvalue(), "split_exports.zip")
            else:
                eb = io.BytesIO()
                with pd.ExcelWriter(eb, engine='xlsxwriter') as w: res.to_excel(w, index=False)
                st.success("Full combined data is ready.")
                st.download_button("📥 Download Full Excel", eb.getvalue(), "merged_data.xlsx")

def audit_page():
    st.title("🚀 Data Comparison (Audit) Tool")
    c1, c2 = st.columns(2)
    with c1:
        f1 = st.file_uploader("Upload First Dataset", type=["csv", "xlsx"], key="a1")
        if st.session_state['shared_df'] is not None:
            if st.button("Use Merged Data as Dataset 1"):
                st.session_state['a1_data'] = st.session_state['shared_df']
                st.success("Merged data loaded!")

    with c2:
        f2 = st.file_uploader("Upload Second Dataset", type=["csv", "xlsx"], key="a2")

    d1 = st.session_state.get('a1_data') if f1 is None else (pd.read_csv(f1) if f1.name.endswith(".csv") else pd.read_excel(f1))
    
    if d1 is not None and f2 is not None:
        d2 = pd.read_csv(f2) if f2.name.endswith(".csv") else pd.read_excel(f2)
        common = [c for c in d1.columns if c in d2.columns]
        st.divider()
        k_col, c_col = st.columns(2)
        keys = k_col.multiselect("Select Unique Key(s):", options=common)
        comps = c_col.multiselect("Select Columns to Compare:", options=[c for c in common if c not in keys])

        if st.button("Run Comparison") and keys:
            for c in keys:
                d1[c], d2[c] = d1[c].astype(str).str.strip(), d2[c].astype(str).str.strip()
            merged = pd.merge(d1[keys + comps], d2[keys + comps], on=keys, how='outer', suffixes=('_F1', '_F2'), indicator=True)
            mismatches = merged[merged['_merge'] == 'both'].copy()
            
            if not mismatches.empty and comps:
                for col in comps:
                    mismatches[f"{col}_Diff"] = np.where(mismatches[f"{col}_F1"].fillna('N/A') != mismatches[f"{col}_F2"].fillna('N/A'), "DIFF", "")
                report = mismatches[(mismatches[[f"{c}_Diff" for c in comps]] == "DIFF").any(axis=1)]
                st.metric("Mismatch Rows Detected", len(report))
                st.dataframe(report)
                
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine='xlsxwriter') as w:
                    report.to_excel(w, index=False)
                st.download_button("💾 Download Audit Report", buf.getvalue(), "Audit_Results.xlsx")

def multi_key_merger_page():
    st.title("🔗 Multi-Key Merger (Advanced Join)")
    l_file = st.file_uploader("Left Dataset (Primary)", type=["csv", "xlsx"])
    r_file = st.file_uploader("Right Dataset (Lookup)", type=["csv", "xlsx"])

    if l_file and r_file:
        df_l = pd.read_csv(l_file) if l_file.name.endswith('.csv') else pd.read_excel(l_file)
        df_r = pd.read_csv(r_file) if r_file.name.endswith('.csv') else pd.read_excel(r_file)

        c1, c2 = st.columns(2)
        col_l = c1.multiselect("Match columns (Left):", df_l.columns)
        col_r = c2.multiselect("Match columns (Right):", df_r.columns)
        join_type = st.selectbox("Join Type", ["left", "right", "inner", "outer"])

        if st.button("🔗 Execute Join") and len(col_l) == len(col_r) > 0:
            result = pd.merge(df_l, df_r, left_on=col_l, right_on=col_r, how=join_type)
            st.success(f"Join successful! Result rows: {len(result)}")
            st.dataframe(result.head())
            
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='xlsxwriter') as w:
                result.to_excel(w, index=False)
            st.download_button("📥 Download Joined Result", buf.getvalue(), "multi_key_join.xlsx")

# --- 4. MAIN APP ROUTING ---

if not st.session_state['logged_in']:
    st.sidebar.image("image_cb68b62a.png", width=100)
    if st.session_state['auth_page'] == 'login':
        st.header("Login to LinkLab")
        email = st.text_input("Email")
        pw = st.text_input("Password", type="password")
        if st.button("Login"):
            if authenticate_user(email, pw):
                st.session_state['logged_in'] = True
                st.rerun()
            else: st.error("Invalid Login")
        if st.button("Need an account? Register"):
            st.session_state['auth_page'] = 'register'
            st.rerun()
    else:
        st.header("Register New User")
        fn = st.text_input("First Name")
        ln = st.text_input("Last Name")
        em = st.text_input("Email")
        pw = st.text_input("Password", type="password")
        if st.button("Create Account"):
            if add_user(fn, ln, em, pw):
                st.success("User created! Please login.")
                st.session_state['auth_page'] = 'login'
                st.rerun()
            else: st.error("Email already exists.")
        if st.button("Back to Login"):
            st.session_state['auth_page'] = 'login'
            st.rerun()
else:
    with st.sidebar:
        st.image("image_cb68b62a.png", width=100)
        page = st.radio("Navigation", ["Home", "Data Merger", "Audit Tool", "Multi-Key Merger"])
        st.divider()
        if st.button("🚪 Logout"):
            st.session_state['logged_in'] = False
            st.rerun()

    if page == "Home": home_page()
    elif page == "Data Merger": merger_page()
    elif page == "Audit Tool": audit_page()
    elif page == "Multi-Key Merger": multi_key_merger_page()
