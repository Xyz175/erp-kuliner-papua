import streamlit as st
import pandas as pd
import psycopg2
import time
from datetime import datetime

# ==========================================
# 1. PENGATURAN HALAMAN & KONEKSI SUPABASE
# ==========================================
st.set_page_config(page_title="ERP Cloud V7 (Excel & Kios)", layout="wide", page_icon="🏢")

SUPABASE_URI = "postgresql://postgres.jskxygpvnbjgjjgsvwqf:ZeeyStore175@aws-0-ap-southeast-2.pooler.supabase.com:6543/postgres"

def get_connection():
    return psycopg2.connect(SUPABASE_URI)

def init_db():
    conn = get_connection()
    conn.autocommit = True 
    cursor = conn.cursor()
    
    # Tabel Utama (Users, Bahan Baku Cafe, Resep)
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
    
    # 🌟 DATABASE BARU KHUSUS GUDANG KIOS (TERPISAH 100% DARI CAFE)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stok_kios_item (
            nama_barang TEXT PRIMARY KEY,
            stok REAL DEFAULT 0,
            satuan TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS riwayat_kios (
            id SERIAL PRIMARY KEY,
            tanggal TEXT,
            nama_barang TEXT,
            jenis_transaksi TEXT,
            jumlah REAL,
            pic TEXT
        )
    """)
    
    cursor.close()
    conn.close()

try: init_db()
except Exception as e: st.error(f"⚠️ Gagal inisialisasi database! Eror: {e}")

# Fungsi Ekspor Excel (CSV format untuk Streamlit murni)
def convert_df_to_csv(df):
    return df.to_csv(index=False).encode('utf-8')

# Session State
if 'racikan_sementara' not in st.session_state: st.session_state.racikan_sementara = pd.DataFrame(columns=["Nama Bahan", "Jumlah Pakai", "Satuan", "Subtotal"])
if 'paket_sementara' not in st.session_state: st.session_state.paket_sementara = pd.DataFrame(columns=["Nama Menu", "Jumlah Porsi", "HPP Satuan", "Subtotal HPP"])
if 'sudah_login' not in st.session_state: st.session_state.sudah_login = False

# ==========================================
# 2. SISTEM LOGIN DENGAN ROLE BARU
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
# 3. NAVIGASI BERDASARKAN ROLE
# ==========================================
role = st.session_state.role
st.sidebar.title("🏢 ERP MULTI-GUDANG V7")
st.sidebar.write(f"👤 User: **{st.session_state.username}**")
st.sidebar.write(f"🛡️ Hak Akses: **{role}**")
if st.sidebar.button("🚪 Keluar / Logout"):
    st.session_state.sudah_login = False
    st.rerun()
st.sidebar.write("---")

# Pengaturan Menu Hak Akses Ketat
if role == "Gudang Kios":
    menu_options = ["📦 Gudang Kios (In/Out)"] # Hanya bisa lihat ini!
elif role == "Karyawan":
    menu_options = ["🍽️ Cafe: Input Dapur"]
elif role in ["Owner", "Admin"]:
    menu_options = ["📊 Dashboard Analitik", "📦 Manajemen Gudang Pusat", "🚚 Penjualan Internal", "🍽️ Cafe: HPP & Target", "📦 Pembuatan Paket Kelompok", "📦 Gudang Kios (In/Out)", "📂 Arsip & Harga Jual"]

if role == "Owner":
    menu_options.append("👥 Manajemen User")

menu = st.sidebar.radio("Navigasi Sistem:", menu_options)

# ==========================================
# MENU 1: GUDANG KIOS (TERPISAH & KHUSUS)
# ==========================================
if menu == "📦 Gudang Kios (In/Out)":
    st.title("📦 Gudang Kios (Pencatatan Mandiri)")
    st.write("Area khusus pencatatan barang Kios (Rokok, Minuman, Snack). Data ini **terpisah** dari Gudang Induk / HPP Cafe.")
    
    tab_in, tab_out, tab_report = st.tabs(["📥 1. Barang Masuk Kios", "📤 2. Barang Keluar Kios", "📊 3. Laporan & Ekspor Excel"])
    
    conn = get_connection()
    df_kios = pd.read_sql_query("SELECT nama_barang, stok, satuan FROM stok_kios_item ORDER BY nama_barang ASC", conn)
    
    with tab_in:
        st.subheader("Catat Barang Masuk (Restok)")
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
                # Update/Insert Stok
                cursor.execute("INSERT INTO stok_kios_item (nama_barang, stok, satuan) VALUES (%s, %s, %s) ON CONFLICT (nama_barang) DO UPDATE SET stok = stok_kios_item.stok + EXCLUDED.stok", (nama_baru.strip(), qty_masuk, sat_baru))
                # Catat Riwayat
                cursor.execute("INSERT INTO riwayat_kios (tanggal, nama_barang, jenis_transaksi, jumlah, pic) VALUES (%s, %s, %s, %s, %s)", (tgl, nama_baru.strip(), 'Masuk', qty_masuk, st.session_state.username))
                conn.commit()
                st.success("✅ Barang Masuk Tercatat!")
                time.sleep(1.5)
                st.rerun()

    with tab_out:
        st.subheader("Catat Barang Keluar (Terjual / Diambil)")
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
        st.subheader("Laporan Stok Saat Ini (Kios)")
        st.dataframe(df_kios, use_container_width=True)
        if not df_kios.empty:
            csv_kios = convert_df_to_csv(df_kios)
            st.download_button(label="📥 Ekspor Stok Kios ke Excel (CSV)", data=csv_kios, file_name='Stok_Kios.csv', mime='text/csv')
            
        st.write("---")
        st.subheader("Riwayat Keluar Masuk (Log)")
        df_log_kios = pd.read_sql_query("SELECT tanggal as \"Waktu\", nama_barang as \"Barang\", jenis_transaksi as \"Status\", jumlah as \"Qty\", pic as \"Petugas\" FROM riwayat_kios ORDER BY id DESC", conn)
        st.dataframe(df_log_kios, use_container_width=True)
        if not df_log_kios.empty:
            csv_log = convert_df_to_csv(df_log_kios)
            st.download_button(label="📥 Ekspor Riwayat In/Out ke Excel (CSV)", data=csv_log, file_name='Riwayat_Kios.csv', mime='text/csv')
    conn.close()

# ==========================================
# MENU 2: MANAJEMEN USER (KHUSUS OWNER)
# ==========================================
elif menu == "👥 Manajemen User":
    st.title("👥 Manajemen Akses Akun")
    conn = get_connection()
    df_users = pd.read_sql_query("SELECT username as \"Username\", role as \"Hak Akses\" FROM users", conn)
    
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("📋 Daftar Pengguna")
        st.dataframe(df_users, use_container_width=True)
        hapus_user = st.selectbox("Pilih User untuk dihapus:", df_users['Username'].tolist())
        if st.button("Hapus Akun", type="primary"):
            if hapus_user == "owner": st.error("Owner tidak bisa dihapus!")
            else:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM users WHERE username=%s", (hapus_user,))
                conn.commit()
                st.success(f"Akun {hapus_user} dihapus!")
                time.sleep(1.5)
                st.rerun()
    with col2:
        st.subheader("➕ Akun Baru")
        with st.form("add_user_form"):
            new_u = st.text_input("Username")
            new_p = st.text_input("Password", type="password")
            new_r = st.selectbox("Role", ["Gudang Kios", "Karyawan", "Admin", "Owner"]) # Tambahan Role Kios
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

# ==========================================
# MENU 3: ARSIP & HARGA JUAL (DENGAN EXCEL EXPORT)
# ==========================================
elif menu == "📂 Arsip & Harga Jual":
    st.title("📂 Arsip Dokumen Pengeluaran & Harga Jual Cafe")
    try:
        conn = get_connection()
        df_resep = pd.read_sql_query('SELECT id as "ID", nama_resep as "Nama Menu/Paket", total_hpp_final as "HPP (Rp)", harga_jual as "Harga Jual (Rp)", tanggal_dibuat as "Waktu" FROM resep', conn)
        if df_resep.empty: st.info("Arsip masih kosong.")
        else:
            st.subheader("Atur Harga Jual Menu & Paket")
            edited = st.data_editor(df_resep, use_container_width=True, disabled=["ID", "Nama Menu/Paket", "HPP (Rp)", "Waktu"])
            
            c_btn1, c_btn2 = st.columns(2)
            with c_btn1:
                if st.button("💾 Simpan Perubahan Finansial", type="primary"):
                    cursor = conn.cursor()
                    for _, r in edited.iterrows():
                        cursor.execute("UPDATE resep SET harga_jual=%s WHERE id=%s", (float(r['Harga Jual (Rp)']), int(r['ID'])))
                    conn.commit()
                    st.success("✅ Sukses Memperbarui Finansial!")
                    time.sleep(1.5)
                    st.rerun()
            with c_btn2:
                # TOMBOL EXCEL UNTUK ARSIP CAFE
                csv_arsip = convert_df_to_csv(df_resep)
                st.download_button(label="📥 Ekspor Daftar Menu ke Excel (CSV)", data=csv_arsip, file_name='Arsip_Menu_Cafe.csv', mime='text/csv')
                
            st.write("---")
            pilih_r = st.selectbox("Pilih Arsip Menu/Paket untuk Dihapus:", df_resep['Nama Menu/Paket'].tolist())
            if st.button("🗑️ Hapus Dokumen Permanen"):
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM resep WHERE nama_resep=%s", (pilih_r,))
                r_id = cursor.fetchone()[0]
                cursor.execute("DELETE FROM detail_resep WHERE resep_id=%s", (r_id,))
                cursor.execute("DELETE FROM resep WHERE id=%s", (r_id,))
                conn.commit()
                st.success("✅ Dihapus!")
                time.sleep(1.5)
                st.rerun()
        conn.close()
    except: st.error("Gagal memuat arsip.")

# ... (Menu Dashboard, Gudang Induk, Transfer, dan Cafe dipersingkat di sini agar muat, Anda bisa menggunakan kode yang sama dengan V6 untuk menu tersebut karena fiturnya tidak berubah)
# Catatan: Karena batasan karakter, saya menyisipkan menu utama Kios, Ekspor, dan Manajemen User secara detail di atas. Menu Cafe dan Gudang Induk tetap menggunakan logika V6.
