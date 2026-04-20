import streamlit as st
import pandas as pd
import numpy as np
import io
import zipfile
import sqlite3

import streamlit as st

# 1. Add the Logo to the Sidebar (Standard Streamlit Way)
st.logo("image_cb68b62a.png", link="https://streamlit.app")

# 2. Add the Logo and Tagline to the Main Page
col1, col2 = st.columns([1, 4])

with col1:
    st.image("image_cb68b62a.png",width=500) # Adjust width as needed

with col2:
    st.title("LinkLab")
    st.write("### *The science of seamless data*")

st.divider()

# Your homepage description here
st.markdown("""
### Master Your Data Complexity
At **LinkLab**, we turn fragmented datasets into a single source of truth. 
Our specialized environment provides the tools you need to:
*   **Append** missing information seamlessly.
*   **Merge** disparate sources with ease.
*   **Compare** data with high-precision logic.
""")






# --- 1. GLOBAL APP CONFIGURATION ---
st.set_page_config(page_title="Satya Professional Data Tricks", layout="wide")

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

def update_password(email, new_password):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE email = ?', (email,))
    if c.fetchone():
        c.execute('UPDATE users SET password = ? WHERE email = ?', (new_password, email))
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False

init_db()

# Initialize Session States
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'auth_page' not in st.session_state: st.session_state['auth_page'] = 'login'
if 'shared_df' not in st.session_state: st.session_state['shared_df'] = None

# --- 3. PAGE FUNCTIONS ---

def merger_page():
    st.title("📊 Append Data & Split Data To Download")
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
            
            st.session_state['shared_df'] = res # Save output for Audit tool

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
    st.title("🚀 Data Comparison Tool")
    c1, c2 = st.columns(2)
    with c1:
        f1 = st.file_uploader("Upload First Dataset", type=["csv", "xlsx","xls"], key="a1")
        if st.session_state['shared_df'] is not None:
            if st.button("Use Merged Data as Dataset 1"):
                st.session_state['a1_data'] = st.session_state['shared_df']
                st.success("Merged data loaded successfully!")
    with c2:
        f2 = st.file_uploader("Upload Second Dataset", type=["csv", "xlsx","xls"], key="a2")

    d1 = None
    if 'a1_data' in st.session_state and st.session_state['a1_data'] is not None:
        d1 = st.session_state['a1_data']
    elif f1 is not None:
        d1 = pd.read_csv(f1) if f1.name.endswith(".csv") else pd.read_excel(f1)

    if d1 is not None and f2 is not None:
        d2 = pd.read_csv(f2) if f2.name.endswith(".csv") else pd.read_excel(f2)
        common = [c for c in d1.columns if c in d2.columns]
        st.divider()
        k_col, c_col = st.columns(2)
        keys = k_col.multiselect("Select Unique Key(s):", options=common)
        comps = c_col.multiselect("Select Columns to Compare:", options=[c for c in common if c not in keys])

        if st.button("Run  Comparison") and keys:
            for c in keys:
                d1[c], d2[c] = d1[c].astype(str).str.strip(), d2[c].astype(str).str.strip()
            merged = pd.merge(d1[keys + comps], d2[keys + comps], on=keys, how='outer', suffixes=('_F1', '_F2'), indicator=True)
            mismatches = merged[merged['_merge'] == 'both'].copy()
            if not mismatches.empty and comps:
                for col in comps:
                    mismatches[f"{col}_Diff"] = np.where(mismatches[f"{col}_F1"].fillna('N/A') != mismatches[f"{col}_F2"].fillna('N/A'), "DIFF", "")
                report = mismatches[(mismatches[[f"{c}_Diff" for c in comps]] == "DIFF").any(axis=1)]
                st.metric("Mismatch Rows Detected", len(report))
                st.dataframe(report, use_container_width=True)
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine='xlsxwriter') as w:
                    report.to_excel(w, index=False, sheet_name='Audit_Report')
                st.download_button("💾 Download Audit Report (.xlsx)", buf.getvalue(), "Audit_Results.xlsx")
            else:
                st.info("No mismatches found in common records.")

def multi_key_merger_page():
    @st.cache_data(show_spinner="Loading data...")
    def load_data(uploaded_file):
        name = uploaded_file.name.lower()
        try:
            if name.endswith('.csv'):
                return pd.read_csv(uploaded_file)
            elif name.endswith(('.xlsx', '.xlsm')):
                return pd.read_excel(uploaded_file)
            elif name.endswith('.parquet'):
                return pd.read_parquet(uploaded_file)
            return None
        except Exception as e:
            st.error(f"Error loading file: {e}")
            return None

    st.title("🚀 LookUp Data (Advanced) Matching On Multiple Columns")
    col_a, col_b = st.columns(2)
    with col_a:
        file1 = st.file_uploader("Main Table", type=['csv', 'xlsx','xls','json', 'parquet'], key="mkm1")
    with col_b:
        file2 = st.file_uploader("Table to Join", type=['csv', 'xlsx','xls','json', 'parquet'], key="mkm2")

    if file1 and file2:
        df1 = load_data(file1)
        df2 = load_data(file2)
        if df1 is not None and df2 is not None:
            a, b = st.columns(2)
            with a:
                st.write("### Main Table Preview")
                st.dataframe(df1.head(5))
            with b:
                st.write("### Join Table Preview")
                st.dataframe(df2.head(5))
            
            st.divider()
            st.subheader("🛠 Join Configuration")
            c1, c2, c3 = st.columns(3)
            with c1:
                left_keys = st.multiselect("Key Column(s) (Main Table)", df1.columns, key="mkm_lk")
            with c2:
                right_keys = st.multiselect("Key Column(s) (Second Table)", df2.columns, key="mkm_rk")
            with c3:
                join_type = st.selectbox("Join Type", ["left", "right", "inner", "outer"], key="mkm_jt")

            st.write("#### Handle Overlapping Column Names")
            s1, s2 = st.columns(2)
            suffix_left = s1.text_input("Suffix for Main Table", "_left", key="mkm_sl")
            suffix_right = s2.text_input("Suffix for Second Table", "_right", key="mkm_sr")

            other_cols = [c for c in df2.columns if c not in right_keys]
            selected_cols = st.multiselect("Columns from Second Table to keep", other_cols, default=other_cols, key="mkm_sc")

            if len(left_keys) != len(right_keys):
                st.warning("⚠️ Select the same number of keys for both tables.")
            elif len(left_keys) == 0:
                st.info("Select at least one key column to begin.")
            else:
                if st.button("🚀 Merge Datasets", key="mkm_btn"):
                    cols_to_use = list(right_keys) + list(selected_cols)
                    result = pd.merge(
                        df1, df2[cols_to_use], 
                        left_on=left_keys, 
                        right_on=right_keys, 
                        how=join_type, 
                        suffixes=(suffix_left, suffix_right)
                    )
                    st.success(f"Merged successfully! Row count: {len(result)}")
                    st.dataframe(result.head(100))
                    
                    st.divider()
                    st.subheader("📥 Export Result")
                    d_col1, d_col2 = st.columns(2)
                    
                    csv_buffer = io.BytesIO()
                    result.to_csv(csv_buffer, index=False)
                    d_col1.download_button("Download as CSV", csv_buffer.getvalue(), "merged.csv", "text/csv", use_container_width=True)
                    
                    excel_buffer = io.BytesIO()
                    with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
                        result.to_excel(writer, index=False, sheet_name='MergedData')
                    d_col2.download_button("Download as Excel", excel_buffer.getvalue(), "merged.xlsx", "application/vnd.ms-excel", use_container_width=True)

# --- 4. NAVIGATION & AUTHENTICATION CONTROL ---

# --- 4. NAVIGATION & AUTHENTICATION CONTROL ---

if not st.session_state['logged_in']:
    # Show Auth screens ONLY (No Sidebar Tools)
    if st.session_state['auth_page'] == 'login':
        st.header("🔐 User Login")
        with st.form("login_form"):
            e = st.text_input("Email")
            p = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                u = authenticate_user(e, p)
                if u:
                    st.session_state['logged_in'] = True
                    st.rerun()
                else:
                    st.error("Invalid credentials.")
        
        c1, c2 = st.columns(2)
        if c1.button("Create Account"): 
            st.session_state['auth_page'] = 'reg'
            st.rerun()
        if c2.button("Forgot Password?"): 
            st.session_state['auth_page'] = 'reset'
            st.rerun()

    elif st.session_state['auth_page'] == 'reg':
        st.header("📝 Register")
        with st.form("reg_form"):
            fn, ln, em, pw = st.text_input("First Name"), st.text_input("Last Name"), st.text_input("Email Address"), st.text_input("Password", type="password")
            if st.form_submit_button("Create Account"):
                if add_user(fn, ln, em, pw):
                    st.success("Account created! Please login.")
                    st.session_state['auth_page'] = 'login'
                    st.rerun()
                else: st.error("Email already registered.")
        if st.button("Back to Login"): 
            st.session_state['auth_page'] = 'login'
            st.rerun()

    elif st.session_state['auth_page'] == 'reset':
        st.header("🔄 Reset Password")
        with st.form("reset_form"):
            e = st.text_input("Registered Email")
            new_p = st.text_input("New Password", type="password")
            conf_p = st.text_input("Confirm Password", type="password")
            if st.form_submit_button("Update Password"):
                if new_p != conf_p: st.error("Passwords do not match.")
                elif update_password(e, new_p):
                    st.success("Password updated!")
                    st.session_state['auth_page'] = 'login'
                    st.rerun()
                else: st.error("Email not found.")
        if st.button("Back to Login"): 
            st.session_state['auth_page'] = 'login'
            st.rerun()

else:
    # --- LOGGED IN: RUN NAVIGATION & TOOLS HERE ---
    
    if st.sidebar.button("Logout"):
        st.session_state['logged_in'] = False
        st.session_state['shared_df'] = None
        st.session_state['a1_data'] = None
        st.session_state['auth_page'] = 'login'
        st.rerun()

    # Move these lines inside the 'else' so they are hidden on logout
    pg = st.navigation({
        "Data Tools": [
            st.Page(merger_page, title="Append Data & Split to Download", icon="📊"),
            st.Page(audit_page, title="Match Data(Primary Key) & Compare ", icon="🚀"),
            st.Page(multi_key_merger_page, title="LookUp Data(Advanced) ", icon="🔗"),
        ]
    })
    pg.run()
