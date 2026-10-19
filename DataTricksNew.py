"""
LinkLab | Professional Data Suite
Redesigned: top navigation, single-page-at-a-time execution (faster), hashed
passwords, cached/streamed file parsing, persistent download buttons.

Requires: streamlit>=1.50, pandas>=2.2, pyarrow, python-calamine, xlsxwriter
"""
from __future__ import annotations

import hashlib
import hmac
import io
import re
import secrets
import sqlite3
import textwrap
import zipfile
from contextlib import closing

import numpy as np
import pandas as pd
import streamlit as st

# ─────────────────────────────────────────────────────────────────────────────
# 1. CONFIG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="LinkLab | Professional Data Suite",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="collapsed",
)
pd.set_option("styler.render.max_elements", 20_000_000)

ACCEPT = ["csv", "xlsx", "xls", "parquet"]
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
DB_PATH = "users.db"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# ─────────────────────────────────────────────────────────────────────────────
# 2. STYLING
# ─────────────────────────────────────────────────────────────────────────────
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="st-"], .stMarkdown { font-family: 'Inter', system-ui, sans-serif; }
footer, #MainMenu { visibility: hidden; }
.block-container { padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1280px; }

/* Page header */
.page-title { font-size: 1.7rem; font-weight: 800; letter-spacing: -.02em; color: #111827; line-height: 1.2; }
.page-sub   { color: #6B7280; font-size: .95rem; margin-top: .25rem; }

/* Workflow stepper */
.steps { display: flex; flex-wrap: wrap; gap: .6rem; margin: .9rem 0 1.3rem 0; }
.step  { display: flex; align-items: center; gap: .55rem; background: #fff; border: 1px solid #E5E7EB;
         border-radius: 999px; padding: .35rem .9rem .35rem .4rem; font-size: .85rem; font-weight: 500; color: #374151; }
.step b { background: #4F46E5; color: #fff; width: 22px; height: 22px; border-radius: 50%;
          display: inline-flex; align-items: center; justify-content: center; font-size: .75rem; }

/* Hero (login + home) */
.hero { background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 55%, #06B6D4 120%);
        color: #fff; border-radius: 20px; padding: 2.4rem 2.2rem; }
.hero h1 { color: #fff; font-size: 2.2rem; font-weight: 800; letter-spacing: -.03em; margin: 0 0 .4rem 0; padding: 0; }
.hero p  { color: rgba(255,255,255,.88); font-size: 1.02rem; margin: 0; }
.hero ul { list-style: none; padding: 0; margin: 1.4rem 0 0 0; }
.hero li { margin: .55rem 0; font-size: .95rem; color: rgba(255,255,255,.95); }
.hero li::before { content: "✓"; display: inline-block; width: 22px; height: 22px; line-height: 22px; text-align: center;
                   background: rgba(255,255,255,.2); border-radius: 50%; margin-right: .6rem; font-size: .75rem; }

/* Inputs & buttons */
.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] > button {
    border-radius: 10px; font-weight: 600; transition: transform .12s ease, box-shadow .12s ease; }
.stButton > button:hover, .stDownloadButton > button:hover { transform: translateY(-1px); box-shadow: 0 6px 16px rgba(79,70,229,.18); }
.stTabs [data-baseweb="tab"] { font-weight: 600; }
[data-testid="stFileUploaderDropzone"] { border-radius: 14px; border: 1.5px dashed #C7CBEA; background: #FAFAFF; }
[data-testid="stMetricValue"] { font-weight: 800; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# 3. AUTH / DATABASE  (salted scrypt hashes; legacy plaintext rows auto-upgrade)
# ─────────────────────────────────────────────────────────────────────────────
def _db():
    return closing(sqlite3.connect(DB_PATH))


@st.cache_resource
def init_db() -> bool:
    with _db() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name TEXT, last_name TEXT,
                email TEXT UNIQUE, password TEXT)"""
        )
        conn.commit()
    return True


def hash_pw(pw: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(pw.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_pw(pw: str, stored: str) -> bool:
    try:
        _, salt_hex, digest_hex = stored.split("$")
        test = hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1)
        return hmac.compare_digest(test.hex(), digest_hex)
    except Exception:
        return False


def authenticate(email: str, pw: str):
    with _db() as conn:
        row = conn.execute(
            "SELECT id, first_name, email, password FROM users WHERE lower(email)=?",
            (email.strip().lower(),),
        ).fetchone()
        if not row:
            return None
        uid, first, mail, stored = row
        if stored.startswith("scrypt$"):
            ok = verify_pw(pw, stored)
        else:  # legacy plaintext → verify, then upgrade to hash
            ok = hmac.compare_digest(stored, pw)
            if ok:
                conn.execute("UPDATE users SET password=? WHERE id=?", (hash_pw(pw), uid))
                conn.commit()
        return (first, mail) if ok else None


def add_user(first: str, last: str, email: str, pw: str) -> tuple[bool, str]:
    if not first.strip() or not email.strip():
        return False, "First name and email are required."
    if not EMAIL_RE.match(email.strip()):
        return False, "Please enter a valid email address."
    if len(pw) < 8:
        return False, "Password must be at least 8 characters."
    try:
        with _db() as conn:
            conn.execute(
                "INSERT INTO users (first_name, last_name, email, password) VALUES (?,?,?,?)",
                (first.strip(), last.strip(), email.strip().lower(), hash_pw(pw)),
            )
            conn.commit()
        return True, "Account created. You can sign in now."
    except sqlite3.IntegrityError:
        return False, "That email is already registered."


init_db()

# ─────────────────────────────────────────────────────────────────────────────
# 4. SESSION STATE
# ─────────────────────────────────────────────────────────────────────────────
for _k, _v in {"logged_in": False, "u_name": "User", "u_email": "", "uploader_key": 0}.items():
    st.session_state.setdefault(_k, _v)

TOOL_STATE_KEYS = ["merge_out", "audit", "join_out", "split_out", "dupe_out"]


def reset_all_tools():
    st.session_state["uploader_key"] += 1
    for key in TOOL_STATE_KEYS:
        st.session_state.pop(key, None)


# ─────────────────────────────────────────────────────────────────────────────
# 5. DATA UTILITIES (pure functions – no Streamlit calls)
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False, max_entries=12, ttl=3600)
def parse_file(name: str, raw: bytes) -> pd.DataFrame:
    n, buf = name.lower(), io.BytesIO(raw)
    if n.endswith(".csv"):
        try:
            return pd.read_csv(buf, engine="pyarrow")  # multithreaded, fastest
        except Exception:
            buf.seek(0)
            try:
                return pd.read_csv(buf, low_memory=False)
            except UnicodeDecodeError:
                buf.seek(0)
                return pd.read_csv(buf, encoding="latin-1", low_memory=False)
    if n.endswith(".parquet"):
        return pd.read_parquet(buf)
    return pd.read_excel(buf, engine="calamine")  # Rust reader, ~10× faster than openpyxl


def read_upload(f) -> pd.DataFrame | None:
    try:
        return parse_file(f.name, f.getvalue())
    except Exception as e:
        st.error(f"Could not read **{f.name}**: {e}")
        return None


def to_xlsx(sheets: dict[str, pd.DataFrame]) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter", engine_kwargs={"options": {"nan_inf_to_errors": True}}) as w:
        for name, d in sheets.items():
            name = name[:31]
            d.to_excel(w, index=False, sheet_name=name)
            ws = w.sheets[name]
            ws.freeze_panes(1, 0)
            if len(d.columns):
                ws.autofilter(0, 0, len(d), len(d.columns) - 1)
    return buf.getvalue()


def safe_name(s: str) -> str:
    return re.sub(r'[\\/:*?"<>|\s]+', "_", str(s)).strip("_")[:80] or "blank"


def clean_key(s: pd.Series) -> pd.Series:
    return s.astype(str).str.replace(r"[^a-zA-Z0-9.]", "", regex=True).str.lower().str.strip()


def merge_frames(frames, dedupe: bool, nulls: str) -> pd.DataFrame:
    out = pd.concat(frames, axis=0, ignore_index=True)
    if dedupe:
        out = out.drop_duplicates()
    if nulls == "Drop rows":
        out = out.dropna()
    elif nulls == "Fill with 0":
        out = out.fillna(0)
    return out


def zip_by_columns(df: pd.DataFrame, cols: list[str]) -> tuple[bytes, int]:
    buf, used = io.BytesIO(), set()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for keys, subset in df.groupby(cols, dropna=False, sort=False):
            keys = keys if isinstance(keys, tuple) else (keys,)
            name = f"Export_{'_'.join(safe_name(k) for k in keys)}"
            while name in used:
                name += "_x"
            used.add(name)
            zf.writestr(f"{name}.xlsx", to_xlsx({"Data": subset}))
    return buf.getvalue(), len(used)


def compare_frames(df1, df2, keys, comps, dedupe: bool):
    df1, df2 = df1.copy(), df2.copy()
    if dedupe:
        df1, df2 = df1.drop_duplicates(subset=keys), df2.drop_duplicates(subset=keys)
    for c in keys:
        df1[c], df2[c] = df1[c].astype(str).str.strip(), df2[c].astype(str).str.strip()

    cols = list(dict.fromkeys(keys + comps))
    allm = pd.merge(df1[cols], df2[cols], on=keys, how="outer", suffixes=("_F1", "_F2"), indicator=True)

    def orphan(flag: str, suffix: str) -> pd.DataFrame:
        o = allm.loc[allm["_merge"] == flag, keys + [f"{c}_{suffix}" for c in comps]]
        return o.rename(columns={f"{c}_{suffix}": c for c in comps}).reset_index(drop=True)

    o1, o2 = orphan("left_only", "F1"), orphan("right_only", "F2")
    matched = allm[allm["_merge"] == "both"]

    report = pd.DataFrame()
    if not matched.empty and comps:
        def arr(sfx):
            sub = matched[[f"{c}_{sfx}" for c in comps]].astype(object)
            return sub.where(sub.notna(), "N/A").to_numpy()

        neq = arr("F1") != arr("F2")
        data = {k: matched[k] for k in keys}
        for i, c in enumerate(comps):
            data[f"{c}_F1"], data[f"{c}_F2"] = matched[f"{c}_F1"], matched[f"{c}_F2"]
            data[f"{c}_Diff"] = np.where(neq[:, i], "DIFF", "")
        report = pd.DataFrame(data, index=matched.index)[neq.any(axis=1)].reset_index(drop=True)
    return report, o1, o2, len(matched)


def find_duplicates(df, dup_col, exclude, pivot_col, spread_cols):
    df = df.copy()
    df["Clean_Key"] = clean_key(df[dup_col])
    if exclude:
        drop = {re.sub(r"[^a-zA-Z0-9.]", "", k).lower() for k in exclude.split(",") if k.strip()}
        df = df[~df["Clean_Key"].isin(drop)]
    dupes = df[df["Clean_Key"].duplicated(keep=False)].copy()
    if dupes.empty:
        return dupes, pd.DataFrame(), len(df)

    matrix = dupes["Clean_Key"].value_counts().rename_axis("Clean_Key").reset_index(name="Total_Rows_in_Group")
    if pivot_col:
        dupes[pivot_col] = dupes[pivot_col].astype(str).str.upper().str.strip()
        pv = dupes.groupby(["Clean_Key", pivot_col]).size().unstack(fill_value=0)
        pv.columns = [f"{pivot_col}_{c}_Count" for c in pv.columns]
        matrix = matrix.merge(pv.reset_index(), on="Clean_Key", how="left")
    for col in spread_cols:
        u = dupes.groupby("Clean_Key")[col].unique()
        ex = pd.DataFrame(u.map(list).tolist(), index=u.index)
        ex.columns = [f"{col}_{i + 1}" for i in range(ex.shape[1])]
        matrix = matrix.merge(ex.reset_index(), on="Clean_Key", how="left")
    return dupes, matrix, len(df)


def split_text(series: pd.Series, width: int) -> pd.DataFrame:
    wrap = lambda t: textwrap.wrap(str(t), width=width, break_long_words=False) if pd.notna(t) else []
    parts = pd.DataFrame(series.map(wrap).tolist(), index=series.index)
    parts.columns = [f"Part_{i + 1}" for i in range(parts.shape[1])]
    return parts


# ─────────────────────────────────────────────────────────────────────────────
# 6. UI HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def page_header(title: str, subtitle: str, steps: list[str], key: str):
    c1, c2 = st.columns([6, 1], vertical_alignment="center")
    c1.markdown(
        f'<div class="page-title">{title}</div><div class="page-sub">{subtitle}</div>',
        unsafe_allow_html=True,
    )
    c2.button("Reset", icon=":material/restart_alt:", on_click=reset_all_tools, key=f"reset_{key}", width="stretch")
    chips = "".join(f'<div class="step"><b>{i}</b>{s}</div>' for i, s in enumerate(steps, 1))
    st.markdown(f'<div class="steps">{chips}</div>', unsafe_allow_html=True)


def kpis(items: list[tuple[str, int]]):
    for col, (label, val) in zip(st.columns(len(items)), items):
        col.metric(label, f"{val:,}", border=True)


def uploader_key(name: str) -> str:
    return f"{name}_{st.session_state['uploader_key']}"


# ─────────────────────────────────────────────────────────────────────────────
# 7. PAGES
# ─────────────────────────────────────────────────────────────────────────────
def home_page():
    st.markdown(
        """<div class="hero"><h1>Your digital laboratory for data excellence</h1>
        <p>Automate the repetitive spreadsheet work. Fast, accurate, and ready for ERP imports.</p></div>""",
        unsafe_allow_html=True,
    )
    st.write("")
    cards = [
        ("merger", "Data Merger", "Stack 2+ files into one master sheet, align headers, split into a ZIP by column.", ":material/layers:"),
        ("comparer", "Precision Comparer", "Find changed prices, stock levels, and missing rows between two versions.", ":material/compare_arrows:"),
        ("join", "Multi-Column Join", "Lookups on several keys where VLOOKUP fails. Left, right, inner, outer.", ":material/link:"),
        ("splitter", "Text Splitter", "Break long descriptions into character-limited columns without cutting words.", ":material/content_cut:"),
        ("dupes", "Duplicate Finder", "Surface duplicate groups with a verification matrix and status counts.", ":material/find_in_page:"),
    ]
    for row in (cards[:3], cards[3:]):
        for col, (pid, title, desc, icon) in zip(st.columns(3), row):
            with col, st.container(border=True):
                st.markdown(f"#### {title}")
                st.caption(desc)
                st.page_link(PAGES[pid], label="Open tool", icon=icon)


def merger_page():
    page_header(
        "Data Merger", "Stack multiple files into one clean master file.",
        ["Upload files", "Align columns", "Clean & split", "Download"], "merge",
    )
    with st.container(border=True):
        files = st.file_uploader(
            "Upload two or more files (CSV, Excel, Parquet)", type=ACCEPT,
            accept_multiple_files=True, key=uploader_key("m_up"),
        )
    if len(files) < 2:
        st.info("Upload at least two files to begin.", icon=":material/upload_file:")
        return

    frames = [read_upload(f) for f in files]
    if any(d is None for d in frames):
        return

    base = list(frames[0].columns)
    base_set = set(base)
    aligned = all(set(d.columns) == base_set for d in frames)
    k = st.session_state["uploader_key"]

    prepared = []
    with st.expander(f"Previews & column alignment · {len(files)} files", expanded=not aligned):
        if aligned:
            st.success("All files share identical headers.", icon=":material/check_circle:")
        else:
            st.warning(
                "Headers differ. Map columns from later files onto the first file's headers "
                "(unmapped columns are kept as-is).", icon=":material/warning:",
            )
        for i, (f, d) in enumerate(zip(files, frames)):
            st.markdown(f"**{f.name}** · {len(d):,} rows · {d.shape[1]} columns")
            st.dataframe(d.head(3), width="stretch")
            if i > 0 and not aligned:
                extra = [c for c in d.columns if c not in base_set]
                mapping, grid = {}, st.columns(3)
                for j, c in enumerate(extra):
                    pick = grid[j % 3].selectbox(f"'{c}' maps to", ["(keep as is)"] + base, key=f"map_{k}_{i}_{c}")
                    if pick != "(keep as is)":
                        mapping[c] = pick
                d = d.rename(columns=mapping)
            prepared.append(d)

    all_cols = list(dict.fromkeys(c for d in prepared for c in d.columns))
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        dedupe = c1.toggle("Remove duplicate rows", value=True)
        nulls = c2.selectbox("Missing values", ["No action", "Drop rows", "Fill with 0"])
        split_cols = c3.multiselect("Split into separate files by (ZIP)", all_cols)

    if st.button("Process & prepare export", type="primary", icon=":material/bolt:", width="stretch"):
        with st.spinner("Merging…"):
            result = merge_frames(prepared, dedupe, nulls)
            if split_cols:
                data, n = zip_by_columns(result, split_cols)
                out = dict(kind="zip", data=data, name="split_exports.zip", mime="application/zip", files=n)
            else:
                out = dict(kind="xlsx", data=to_xlsx({"Merged": result}), name="merged_data.xlsx", mime=XLSX_MIME, files=1)
            out.update(rows=len(result), cols=result.shape[1], preview=result.head(100))
            st.session_state["merge_out"] = out

    if out := st.session_state.get("merge_out"):
        st.divider()
        kpis([("Rows", out["rows"]), ("Columns", out["cols"]), ("Output files", out["files"])])
        st.dataframe(out["preview"], width="stretch")
        st.download_button(
            "Download " + ("ZIP archive" if out["kind"] == "zip" else "merged file"), out["data"], out["name"],
            mime=out["mime"], type="primary", icon=":material/download:", width="stretch",
        )


def comparer_page():
    page_header(
        "Precision Comparer", "Side-by-side change detection between a reference and a new file.",
        ["Upload both versions", "Choose unique keys", "Run analysis", "Review & export"], "audit",
    )
    a, b = st.columns(2)
    with a, st.container(border=True):
        f1 = st.file_uploader("Reference dataset (master)", type=ACCEPT, key=uploader_key("au1"))
    with b, st.container(border=True):
        f2 = st.file_uploader("New dataset (to verify)", type=ACCEPT, key=uploader_key("au2"))
    if not (f1 and f2):
        st.info("Upload both files to configure the comparison.", icon=":material/upload_file:")
        return

    df1, df2 = read_upload(f1), read_upload(f2)
    if df1 is None or df2 is None:
        return
    common = [c for c in df1.columns if c in df2.columns]

    with st.container(border=True):
        ck, cc = st.columns(2)
        keys = ck.multiselect("Unique key(s)", common, help="Columns that identify a row, e.g. SKU or ID.")
        remaining = [c for c in common if c not in keys]
        sel_all = cc.checkbox("Select all remaining columns")
        comps = cc.multiselect("Columns to compare", remaining, default=remaining if sel_all else [])
        dedupe = ck.checkbox("Auto-clean duplicate keys (keep first)", value=False)

    if st.button("Run analysis", type="primary", icon=":material/bolt:", width="stretch"):
        if not keys:
            st.warning("Select at least one unique key.")
        else:
            with st.spinner("Comparing…"):
                report, o1, o2, n_match = compare_frames(df1, df2, keys, comps, dedupe)
                sheets = {"Only_F1": o1, "Only_F2": o2}
                if not report.empty:
                    sheets = {"Mismatches": report, **sheets}
                st.session_state["audit"] = dict(
                    report=report, o1=o1, o2=o2, matched=n_match, xlsx=to_xlsx(sheets),
                    dup_warn=(not dedupe) and (df1.duplicated(keys).any() or df2.duplicated(keys).any()),
                )

    if res := st.session_state.get("audit"):
        st.divider()
        if res["dup_warn"]:
            st.warning("Duplicate keys detected. Rows may be multiplied. Enable *Auto-clean duplicate keys* for exact results.")
        kpis([("Matched", res["matched"]), ("Only in reference", len(res["o1"])),
              ("Only in new", len(res["o2"])), ("Mismatched rows", len(res["report"]))])

        t_mis, t1, t2 = st.tabs(["Mismatches", "Only in reference", "Only in new"])
        with t_mis:
            rep = res["report"]
            if rep.empty:
                st.success("No mismatches found in matched rows.", icon=":material/check_circle:")
            else:
                diff_cols = [c for c in rep.columns if c.endswith("_Diff")]
                style = lambda v: "background-color:#FEE2E2;color:#991B1B;font-weight:600" if v == "DIFF" else ""
                st.dataframe(rep.head(1000).style.map(style, subset=diff_cols), width="stretch")
                if len(rep) > 1000:
                    st.caption("Showing first 1,000 rows. The download contains all rows.")
        with t1:
            st.dataframe(res["o1"].head(500), width="stretch")
        with t2:
            st.dataframe(res["o2"].head(500), width="stretch")
        st.download_button("Download full audit (.xlsx)", res["xlsx"], "Audit_Report.xlsx", mime=XLSX_MIME,
                           type="primary", icon=":material/download:", width="stretch")


def join_page():
    page_header(
        "Multi-Column Lookup", "Join two tables on one or more key columns.",
        ["Load both tables", "Pick matching keys", "Join & export"], "join",
    )
    a, b = st.columns(2)
    with a, st.container(border=True):
        f1 = st.file_uploader("Main table", type=ACCEPT, key=uploader_key("j1"))
    with b, st.container(border=True):
        f2 = st.file_uploader("Table to join", type=ACCEPT, key=uploader_key("j2"))
    if not (f1 and f2):
        st.info("Upload both tables to continue.", icon=":material/upload_file:")
        return
    df1, df2 = read_upload(f1), read_upload(f2)
    if df1 is None or df2 is None:
        return

    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        lk = c1.multiselect("Keys · main table", df1.columns)
        rk = c2.multiselect("Keys · second table", df2.columns, help="Same number and order as the main-table keys.")
        how = c3.selectbox("Join type", ["left", "right", "inner", "outer"])
        s1, s2, s3 = st.columns(3)
        sl = s1.text_input("Suffix · main", "_left")
        sr = s2.text_input("Suffix · second", "_right")
        as_text = s3.toggle("Match keys as trimmed text", value=True, help="Avoids int/text mismatches and stray spaces.")

    if st.button("Merge datasets", type="primary", icon=":material/bolt:", width="stretch"):
        if not lk or len(lk) != len(rk):
            st.warning("Select the same number of keys (at least one) for both tables.")
        else:
            with st.spinner("Joining…"):
                l, r = df1.copy(), df2.copy()
                if as_text:
                    for c in lk:
                        l[c] = l[c].astype(str).str.strip()
                    for c in rk:
                        r[c] = r[c].astype(str).str.strip()
                m = pd.merge(l, r, left_on=lk, right_on=rk, how=how, suffixes=(sl, sr), indicator="_lk_match")
                matched = int((m["_lk_match"] == "both").sum())
                m = m.drop(columns="_lk_match")
                st.session_state["join_out"] = dict(
                    rows=len(m), cols=m.shape[1], matched=matched, preview=m.head(100),
                    data=to_xlsx({"Joined": m}),
                )

    if out := st.session_state.get("join_out"):
        st.divider()
        kpis([("Result rows", out["rows"]), ("Matched rows", out["matched"]), ("Columns", out["cols"])])
        st.dataframe(out["preview"], width="stretch")
        st.download_button("Download result", out["data"], "merged_result.xlsx", mime=XLSX_MIME,
                           type="primary", icon=":material/download:", width="stretch")


def splitter_page():
    page_header(
        "Text Column Splitter", "Fit long descriptions into ERP-friendly, character-limited columns.",
        ["Set character limit", "Upload & pick column", "Generate", "Download"], "split",
    )
    with st.container(border=True):
        c1, c2 = st.columns([1, 2])
        max_len = c1.number_input("Character limit per column", 1, 500, 50)
        up = c2.file_uploader("Upload file", type=ACCEPT, key=uploader_key("s1"))
    if not up:
        st.info("Upload a file and choose the text column to split.", icon=":material/upload_file:")
        return
    df = read_upload(up)
    if df is None:
        return
    col = st.selectbox("Column to process", df.columns)

    if st.button("Generate new columns", type="primary", icon=":material/bolt:", width="stretch"):
        with st.spinner("Splitting…"):
            parts = split_text(df[col], int(max_len))
            full = pd.concat([df, parts], axis=1)
            over = int((parts.stack().astype(str).str.len() > max_len).sum()) if parts.shape[1] else 0
            st.session_state["split_out"] = dict(
                preview=full.head(10), n_parts=parts.shape[1], rows=len(full), over=over,
                xlsx=to_xlsx({"Split": full}), csv=full.to_csv(index=False).encode("utf-8-sig"),
            )

    if out := st.session_state.get("split_out"):
        st.divider()
        kpis([("Rows", out["rows"]), ("Columns generated", out["n_parts"]), ("Words over limit", out["over"])])
        if out["over"]:
            st.caption("Some single words are longer than the limit; words are never broken mid-way.")
        st.dataframe(out["preview"], width="stretch")
        d1, d2 = st.columns(2)
        d1.download_button("Download Excel", out["xlsx"], "split_columns.xlsx", mime=XLSX_MIME,
                           type="primary", icon=":material/download:", width="stretch")
        d2.download_button("Download CSV", out["csv"], "split_columns.csv", mime="text/csv",
                           icon=":material/download:", width="stretch")


def dupes_page():
    page_header(
        "Duplicate Finder", "Detect duplicate groups and verify them with a matrix.",
        ["Upload file", "Choose duplicate column", "Filter & pivot", "Review & export"], "dupe",
    )
    with st.container(border=True):
        up = st.file_uploader("Upload file", type=ACCEPT, key=uploader_key("up_dupe"))
    if not up:
        st.info("Upload a file to audit for duplicates.", icon=":material/upload_file:")
        return
    df = read_upload(up)
    if df is None:
        return
    cols = df.columns.tolist()

    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            dup_col = st.selectbox("Find duplicates in", cols)
            exclude = st.text_input("Values to ignore (comma-separated)", help="Compared after cleaning, e.g. N/A, none")
        with c2:
            pivot_col = st.selectbox("Pivot column (status counts)", [None] + cols)
            sel_all = st.checkbox("Select all columns for export")
            export_cols = st.multiselect("Columns in export", cols, default=cols if sel_all else [])
        with c3:
            spread = st.multiselect("Matrix columns (spread into headers)", cols)

    if st.button("Process & filter data", type="primary", icon=":material/bolt:", width="stretch"):
        with st.spinner("Scanning for duplicates…"):
            dupes, matrix, scanned = find_duplicates(df, dup_col, exclude, pivot_col, spread)
            if dupes.empty:
                st.session_state["dupe_out"] = dict(empty=True, scanned=scanned)
            else:
                cols_out = ["Clean_Key"] + [c for c in export_cols if c != "Clean_Key"]
                st.session_state["dupe_out"] = dict(
                    empty=False, scanned=scanned, rows=len(dupes), groups=len(matrix), matrix=matrix.head(100),
                    dupes_x=to_xlsx({"Duplicates": dupes[cols_out]}), matrix_x=to_xlsx({"Matrix": matrix}),
                )

    if out := st.session_state.get("dupe_out"):
        st.divider()
        if out["empty"]:
            st.success(f"No duplicates found in {out['scanned']:,} rows.", icon=":material/check_circle:")
            return
        kpis([("Rows scanned", out["scanned"]), ("Duplicate rows", out["rows"]), ("Duplicate groups", out["groups"])])
        st.subheader("Verification matrix")
        st.dataframe(out["matrix"], width="stretch")
        d1, d2 = st.columns(2)
        d1.download_button("Download duplicates", out["dupes_x"], "duplicates.xlsx", mime=XLSX_MIME,
                           type="primary", icon=":material/download:", width="stretch")
        d2.download_button("Download matrix", out["matrix_x"], "matrix.xlsx", mime=XLSX_MIME,
                           icon=":material/download:", width="stretch")


# ─────────────────────────────────────────────────────────────────────────────
# 8. AUTH SCREEN
# ─────────────────────────────────────────────────────────────────────────────
def auth_screen():
    left, right = st.columns([1.15, 1], gap="large", vertical_alignment="center")
    with left:
        st.markdown(
            """<div class="hero"><h1>🔬 LinkLab</h1>
            <p>The professional data management platform.</p>
            <ul>
              <li><b>Vertical merging</b>: stack disparate files into one master sheet</li>
              <li><b>Precision auditing</b>: detect modified, added, or deleted entries</li>
              <li><b>Multi-key linking</b>: lookups where VLOOKUP falls short</li>
              <li><b>ERP compatibility</b>: split text to strict character limits</li>
            </ul></div>""",
            unsafe_allow_html=True,
        )
    with right, st.container(border=True):
        t_in, t_up = st.tabs(["Sign in", "Create account"])
        with t_in:
            with st.form("login", border=False):
                em = st.text_input("Email", placeholder="you@company.com")
                pw = st.text_input("Password", type="password")
                go = st.form_submit_button("Sign in", type="primary", width="stretch")
            if go:
                u = authenticate(em, pw)
                if u:
                    st.session_state.update(logged_in=True, u_name=u[0], u_email=u[1])
                    st.rerun()
                st.error("Invalid email or password.")
            with st.expander("Forgot password?"):
                st.caption("Contact your LinkLab administrator to reset your password.")
        with t_up:
            with st.form("register", border=False):
                a, b = st.columns(2)
                fn, ln = a.text_input("First name"), b.text_input("Last name")
                em = st.text_input("Email address")
                pw = st.text_input("Create password", type="password", help="At least 8 characters")
                go = st.form_submit_button("Create account", type="primary", width="stretch")
            if go:
                ok, msg = add_user(fn, ln, em, pw)
                (st.success if ok else st.error)(msg)


# ─────────────────────────────────────────────────────────────────────────────
# 9. ROUTING
# ─────────────────────────────────────────────────────────────────────────────
if not st.session_state.logged_in:
    auth_screen()
else:
    PAGES = {
        "home": st.Page(home_page, title="Home", icon=":material/home:", url_path="home", default=True),
        "merger": st.Page(merger_page, title="Merger", icon=":material/layers:", url_path="merger"),
        "comparer": st.Page(comparer_page, title="Comparer", icon=":material/compare_arrows:", url_path="comparer"),
        "join": st.Page(join_page, title="Join", icon=":material/link:", url_path="join"),
        "splitter": st.Page(splitter_page, title="Splitter", icon=":material/content_cut:", url_path="splitter"),
        "dupes": st.Page(dupes_page, title="Dupe Finder", icon=":material/find_in_page:", url_path="dupes"),
    }
    nav = st.navigation(list(PAGES.values()), position="top")

    hl, hr = st.columns([6, 1], vertical_alignment="center")
    hl.caption(f"👋 Welcome back, **{st.session_state.u_name}**")
    with hr.popover(st.session_state.u_name, icon=":material/account_circle:", width="stretch"):
        st.write(f"Signed in as **{st.session_state.u_email}**")
        if st.button("Log out", icon=":material/logout:", width="stretch"):
            st.session_state.logged_in = False
            reset_all_tools()
            st.rerun()

    nav.run()
