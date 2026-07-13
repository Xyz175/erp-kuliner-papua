import streamlit as st
import pandas as pd
import psycopg2
import time
from datetime import datetime

# ==========================================
# 1. PENGATURAN HALAMAN & KONEKSI SUPABASE
# ==========================================
st.set_page_config(page_title="ERP Cloud V7 (Lengkap)", layout="wide", page_icon="🏢")

SUPABASE_URI = "postgresql://postgres.jskxygpvnbjgjjgsvwqf:ZeeyStore175@aws-0-ap-southeast-2.pooler.supabase.com:6543/postgres"

def get_connection():
    return psycopg2.connect(SUPABASE_URI)

def init_db():
    conn = get_connection()
    conn.autocommit = True 
    cursor = conn.cursor()
    
    cursor.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT)")
    cursor.execute("INSERT INTO users (username, password, role) VALUES ('owner', 'owner123', 'Owner') ON CONFLICT DO NOTHING")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bahan_baku (
            nama_bahan TEXT PRIMARY KEY, harga_beli REAL, jumlah_isi REAL, satuan TEXT, harga_satuan REAL,
            stok_gudang REAL DEFAULT 0, stok_cafe REAL DEFAULT 0, stok_taman REAL DEFAULT 0, harga_jual_internal REAL DEFAULT 0
        )
    """)
    cursor.execute("CREATE TABLE IF NOT EXISTS resep (id SERIAL PRIMARY KEY, nama_resep TEXT UNIQUE, total_hpp_bahan REAL, total_operasional REAL, total_hpp_final REAL, harga_jual REAL DEFAULT 0, tanggal_dibuat TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS detail_resep (id SERIAL PRIMARY KEY, resep_id INTEGER, nama_bahan TEXT, jumlah_pakai REAL, satuan TEXT, subtotal_biaya REAL)")
    cursor.execute("CREATE TABLE IF NOT EXISTS riwayat_stok (id SERIAL PRIMARY KEY, tanggal TEXT, nama_bahan TEXT, jenis_transaksi TEXT, jumlah REAL, keterangan TEXT, laba_internal REAL DEFAULT 0, dari_gudang TEXT, ke_unit TEXT)")
    
    # DATABASE GUDANG KIOS (TERPISAH)
    cursor.execute("CREATE TABLE IF NOT EXISTS stok_kios_item (nama_barang TEXT PRIMARY KEY, stok REAL DEFAULT 0, satuan TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS riwayat_kios (id SERIAL PRIMARY KEY, tanggal TEXT, nama_barang TEXT, jenis_transaksi TEXT, jumlah REAL, pic TEXT)")
    
    cursor.close()
    conn.close()

try: init_db()
except Exception as e: st.error(f"⚠️ Gagal inisialisasi database! Eror: {e}")

def convert_df_to_csv(df): return df.to_csv(index=False).encode('utf-8')
def get_daftar_bahan():
    try:
        conn = get_connection()
        df = pd.read_sql_query("SELECT * FROM bahan_baku ORDER BY nama_bahan ASC", conn)
        conn.close()
        return df
    except: return pd.DataFrame()

if 'racikan_sementara' not in st.session_state: st.session_state.racikan_sementara = pd.DataFrame(columns=["Nama Bahan", "Jumlah Pakai", "Satuan", "Subtotal"])
if 'sudah_login' not in st.session_state: st.session_state.sudah_login = False

# ==========================================
# 2. SISTEM LOGIN
# ==========================================
if not st.session_state.sudah_login:
    st.title("🔐 Login Sistem ERP Etnik Papua")
    user_input = st.text_input("Username")
    pass_input = st.text_input("Password", type="password")
    if st.button("Masuk / Login", type="primary"):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT role FROM users WHERE username=%s AND password=%s", (user_input, pass_input))
        res = cursor.fetchone()
        conn.close()
        if res:
            st.session_state.sudah_login = True
            st.session_state.username = user_input
            st.session_state.role = res[0]
            st.rerun()
        else: st.error("❌ Username atau Password salah!")
    st.stop()

# ==========================================
# 3. NAVIGASI MENU (SESUAI HAK AKSES)
# ==========================================
role = st.session_state.role
st.sidebar.title("🏢 ERP MULTI-GUDANG V7")
st.sidebar.write(f"👤 User: **{st.session_state.username}**")
st.sidebar.write(f"🛡️ Hak Akses: **{role}**")
if st.sidebar.button("🚪 Keluar / Logout"):
    st.session_state.sudah_login = False
    st.rerun()
st.sidebar.write("---")

if role == "Gudang Kios":
    menu_options = ["📦 Gudang Kios (In/Out)"]
elif role == "Karyawan":
    menu_options = ["🍳 Operasional & Dapur"]
elif role in ["Owner", "Admin"]:
    menu_options = ["📊 Dashboard Analitik", "📦 Manajemen Gudang Pusat", "🚚 Transfer ke Unit", "🍳 Operasional & Dapur", "🍽️ Cafe: HPP & Target", "📦 Gudang Kios (In/Out)", "📂 Arsip & Harga Jual"]

if role == "Owner":
    menu_options.append("👥 Manajemen User")

menu = st.sidebar.radio("Navigasi Sistem:", menu_options)

# ==========================================
# 4. ISI KODE UNTUK SEMUA MENU
# ==========================================

# --- MENU: GUDANG KIOS ---
if menu == "📦 Gudang Kios (In/Out)":
    st.title("📦 Gudang Kios (Pencatatan Mandiri)")
    tab_in, tab_out, tab_report = st.tabs(["📥 1. Barang Masuk Kios", "📤 2. Barang Keluar Kios", "📊 3. Laporan & Ekspor Excel"])
    conn = get_connection()
    df_kios = pd.read_sql_query("SELECT nama_barang, stok, satuan FROM stok_kios_item ORDER BY nama_barang ASC", conn)
    
    with tab_in:
        pilihan = ["-- Input Barang Baru --"] + (df_kios['nama_barang'].tolist() if not df_kios.empty else [])
        barang_masuk = st.selectbox("Pilih Barang Kios:", pilihan)
        c1, c2, c3 = st.columns(3)
        with c1: nama_baru = st.text_input("Nama Barang", value="" if barang_masuk == "-- Input Barang Baru --" else barang_masuk, disabled=(barang_masuk != "-- Input Barang Baru --"))
        with c2: qty_masuk = st.number_input("Jumlah Masuk", min_value=1.0, step=1.0)
        with c3: sat_baru = st.text_input("Satuan (pcs/botol)", value="" if barang_masuk == "-- Input Barang Baru --" else df_kios[df_kios['nama_barang']==barang_masuk]['satuan'].values[0])
        
        if st.button("📥 Simpan Barang Masuk", type="primary"):
            if nama_baru:
                cursor = conn.cursor()
                tgl = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("INSERT INTO stok_kios_item (nama_barang, stok, satuan) VALUES (%s, %s, %s) ON CONFLICT (nama_barang) DO UPDATE SET stok = stok_kios_item.stok + EXCLUDED.stok", (nama_baru.strip(), qty_masuk, sat_baru))
                cursor.execute("INSERT INTO riwayat_kios (tanggal, nama_barang, jenis_transaksi, jumlah, pic) VALUES (%s, %s, %s, %s, %s)", (tgl, nama_baru.strip(), 'Masuk', qty_masuk, st.session_state.username))
                conn.commit()
                st.success("✅ Barang Masuk Tercatat!")
                time.sleep(1.5)
                st.rerun()

    with tab_out:
        if df_kios.empty: st.warning("Stok Kios Masih Kosong!")
        else:
            out1, out2 = st.columns(2)
            with out1: barang_keluar = st.selectbox("Pilih Barang Keluar:", df_kios['nama_barang'].tolist())
            stok_sisa = df_kios[df_kios['nama_barang']==barang_keluar]['stok'].values[0]
            with out2: qty_keluar = st.number_input(f"Jumlah Keluar (Stok: {stok_sisa})", min_value=1.0, max_value=float(stok_sisa) if stok_sisa > 0 else 1.0, step=1.0)
            
            if st.button("📤 Catat Barang Keluar", type="primary"):
                cursor = conn.cursor()
                tgl = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("UPDATE stok_kios_item SET stok = stok - %s WHERE nama_barang = %s", (qty_keluar, barang_keluar))
                cursor.execute("INSERT INTO riwayat_kios (tanggal, nama_barang, jenis_transaksi, jumlah, pic) VALUES (%s, %s, %s, %s, %s)", (tgl, barang_keluar, 'Keluar', qty_keluar, st.session_state.username))
                conn.commit()
                st.success("✅ Barang Keluar Tercatat!")
                time.sleep(1.5)
                st.rerun()

    with tab_report:
        st.dataframe(df_kios, use_container_width=True)
        if not df_kios.empty:
            st.download_button("📥 Ekspor Stok Kios", data=convert_df_to_csv(df_kios), file_name='Stok_Kios.csv', mime='text/csv')
        st.write("---")
        df_log_kios = pd.read_sql_query("SELECT tanggal, nama_barang, jenis_transaksi, jumlah, pic FROM riwayat_kios ORDER BY id DESC", conn)
        st.dataframe(df_log_kios, use_container_width=True)
        if not df_log_kios.empty:
            st.download_button("📥 Ekspor Riwayat In/Out", data=convert_df_to_csv(df_log_kios), file_name='Riwayat_Kios.csv', mime='text/csv')
    conn.close()

# --- MENU: KARYAWAN DAPUR ---
elif menu == "🍳 Operasional & Dapur":
    st.title("🍳 Input Pemakaian Bahan Dapur (Karyawan)")
    df_b = get_daftar_bahan()
    if df_b.empty: st.warning("Bahan baku kosong!")
    else:
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            cari = st.text_input("🔍 Cari bahan:")
            df_f = df_b[df_b['nama_bahan'].str.lower().str.contains(cari.lower())] if cari else df_b
            pilih_b = st.selectbox("Pilih:", df_f['nama_bahan'].tolist() if not df_f.empty else ["Kosong"])
        with c2: qty = st.number_input("Jumlah (porsi/gram):", min_value=0.0, step=1.0)
        with c3:
            st.write(""); st.write("")
            if st.button("➕ Tambah"):
                if pilih_b != "Kosong" and qty > 0:
                    row = df_b[df_b['nama_bahan'] == pilih_b].iloc[0]
                    h_modal = row['harga_jual_internal'] if row['harga_jual_internal'] > 0 else row['harga_satuan']
                    sub = qty * h_modal
                    df_skrg = st.session_state.racikan_sementara
                    if pilih_b in df_skrg['Nama Bahan'].values:
                        df_skrg.loc[df_skrg['Nama Bahan'] == pilih_b, ["Jumlah Pakai", "Subtotal"]] = [qty, sub]
                    else:
                        tambah = pd.DataFrame([[pilih_b, qty, row['satuan'], sub]], columns=df_skrg.columns)
                        st.session_state.racikan_sementara = pd.concat([df_skrg, tambah], ignore_index=True)
                    st.rerun()
        
        st.write("---")
        if not st.session_state.racikan_sementara.empty:
            st.session_state.racikan_sementara = st.data_editor(st.session_state.racikan_sementara, use_container_width=True)
            tot_bahan = st.session_state.racikan_sementara['Subtotal'].sum()
            
            st.info(f"Total Biaya Bahan Sementra: Rp {tot_bahan:,.0f}")
            nama_menu = st.text_input("Nama Laporan/Menu yang dikerjakan:")
            if st.button("✅ Kunci & Potong Stok Cafe", type="primary"):
                if nama_menu:
                    conn = get_connection()
                    cursor = conn.cursor()
                    tgl = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    cursor.execute("INSERT INTO resep (nama_resep, total_hpp_bahan, tanggal_dibuat) VALUES (%s,%s,%s) ON CONFLICT (nama_resep) DO NOTHING", (nama_menu, tot_bahan, tgl))
                    for _, r in st.session_state.racikan_sementara.iterrows():
                        cursor.execute("UPDATE bahan_baku SET stok_cafe = COALESCE(stok_cafe,0) - %s WHERE nama_bahan = %s", (r['Jumlah Pakai'], r['Nama Bahan']))
                    conn.commit()
                    conn.close()
                    st.success("✅ Stok berhasil dipotong!")
                    time.sleep(1.5)
                    st.session_state.racikan_sementara = pd.DataFrame(columns=["Nama Bahan", "Jumlah Pakai", "Satuan", "Subtotal"])
                    st.rerun()

# --- MENU: MANAJEMEN USER ---
elif menu == "👥 Manajemen User":
    st.title("👥 Manajemen Akses Akun")
    conn = get_connection()
    df_users = pd.read_sql_query("SELECT username, role FROM users", conn)
    col1, col2 = st.columns([2, 1])
    with col1:
        st.dataframe(df_users, use_container_width=True)
        hapus_user = st.selectbox("Pilih User untuk dihapus:", df_users['username'].tolist())
        if st.button("Hapus Akun", type="primary"):
            if hapus_user == "owner": st.error("Owner tidak bisa dihapus!")
            else:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM users WHERE username=%s", (hapus_user,))
                conn.commit()
                st.success(f"Akun dihapus!")
                time.sleep(1.5)
                st.rerun()
    with col2:
        with st.form("add_user_form"):
            new_u = st.text_input("Username")
            new_p = st.text_input("Password", type="password")
            new_r = st.selectbox("Role", ["Gudang Kios", "Karyawan", "Admin", "Owner"])
            if st.form_submit_button("Simpan"):
                if new_u and new_p:
                    cursor = conn.cursor()
                    try:
                        cursor.execute("INSERT INTO users VALUES (%s, %s, %s)", (new_u.strip().lower(), new_p, new_r))
                        conn.commit()
                        st.success("Akun berhasil dibuat!")
                        time.sleep(1.5)
                        st.rerun()
                    except: st.error("Username terpakai!")
    conn.close()

# --- MENU LAINNYA (DIPADATKAN) ---
elif menu == "📊 Dashboard Analitik":
    st.title("📊 Laba Internal Gudang")
    conn = get_connection()
    df_log = pd.read_sql_query("SELECT * FROM riwayat_stok WHERE jenis_transaksi='Penjualan Internal'", conn)
    st.dataframe(df_log, use_container_width=True)
    conn.close()

elif menu == "📦 Manajemen Gudang Pusat":
    st.title("📦 Gudang Induk (Etnik Papua)")
    df_b = get_daftar_bahan()
    with st.form("form_gudang"):
        c1, c2, c3, c4 = st.columns(4)
        with c1: nama = st.text_input("Nama Barang")
        with c2: hrg = st.number_input("Total Harga Beli", min_value=0)
        with c3: qty = st.number_input("Isi (pcs/gram)", min_value=1)
        with c4: hrg_int = st.number_input("Harga Jual Cabang", min_value=0)
        sat = st.text_input("Satuan (Contoh: pcs)")
        if st.form_submit_button("Simpan ke Gudang Induk"):
            if nama:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("INSERT INTO bahan_baku (nama_bahan, harga_beli, jumlah_isi, satuan, harga_satuan, stok_gudang, harga_jual_internal) VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (nama_bahan) DO UPDATE SET stok_gudang = bahan_baku.stok_gudang + EXCLUDED.stok_gudang, harga_jual_internal=EXCLUDED.harga_jual_internal", (nama, hrg, qty, sat, hrg/qty, qty, hrg_int))
                conn.commit()
                conn.close()
                st.success("✅ Tersimpan!")
                time.sleep(1)
                st.rerun()
    st.dataframe(df_b, use_container_width=True)

elif menu == "🚚 Transfer ke Unit":
    st.title("🚚 Transfer Barang Internal")
    df_g = get_daftar_bahan()
    if not df_g.empty:
        c1, c2, c3 = st.columns(3)
        with c1: brg = st.selectbox("Barang:", df_g['nama_bahan'].tolist())
        with c2: qty = st.number_input("Jumlah:", min_value=1)
        with c3: tuj = st.radio("Tujuan:", ["Cafe", "Taman"])
        if st.button("Transfer", type="primary"):
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE bahan_baku SET stok_gudang = stok_gudang - %s WHERE nama_bahan = %s", (qty, brg))
            if tuj == "Cafe": cursor.execute("UPDATE bahan_baku SET stok_cafe = COALESCE(stok_cafe, 0) + %s WHERE nama_bahan = %s", (qty, brg))
            elif tuj == "Taman": cursor.execute("UPDATE bahan_baku SET stok_taman = COALESCE(stok_taman, 0) + %s WHERE nama_bahan = %s", (qty, brg))
            conn.commit()
            conn.close()
            st.success("✅ Terkirim!")
            time.sleep(1)
            st.rerun()

elif menu == "📂 Arsip & Harga Jual":
    st.title("📂 Arsip & Excel")
    conn = get_connection()
    df_r = pd.read_sql_query("SELECT * FROM resep", conn)
    st.dataframe(df_r, use_container_width=True)
    if not df_r.empty:
        st.download_button("📥 Ekspor Daftar Menu (Excel CSV)", data=convert_df_to_csv(df_r), file_name='Arsip_Menu.csv', mime='text/csv')
    conn.close()

elif menu == "🍽️ Cafe: HPP & Target":
    st.title("Fitur HPP ada di menu 'Operasional & Dapur' untuk mencatat bahan.")
