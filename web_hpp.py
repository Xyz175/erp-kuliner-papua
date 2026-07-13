import streamlit as st
import pandas as pd
import psycopg2
import matplotlib.pyplot as plt
from datetime import datetime

# ==========================================
# 1. PENGATURAN HALAMAN & KONEKSI SUPABASE
# ==========================================
st.set_page_config(page_title="Sistem ERP Cloud V3 (Multi-Gudang & Taman)", layout="wide", page_icon="🏢")

# --- SISTEM LOGIN ---
if 'sudah_login' not in st.session_state:
    st.session_state.sudah_login = False

if not st.session_state.sudah_login:
    st.title("🔒 Sistem ERP Terkunci")
    st.write("Silakan masukkan Username dan Password Anda.")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    
    if st.button("Masuk / Login"):
        if username == "admin" and password == "papua123":
            st.session_state.sudah_login = True
            st.rerun()
        else:
            st.error("❌ Username atau Password salah!")
    st.stop()

# KONEKSI DATABASE CLOUD
SUPABASE_URI = "postgresql://postgres.jskxygpvnbjgjjgsvwqf:ZeeyStore175@aws-0-ap-southeast-2.pooler.supabase.com:6543/postgres"

def get_connection():
    return psycopg2.connect(SUPABASE_URI)

def init_db():
    conn = get_connection()
    conn.autocommit = True 
    cursor = conn.cursor()
    
    # 1. Tabel Bahan Baku (Gudang Induk, Kios, Cafe, dan Taman)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bahan_baku (
            nama_bahan TEXT PRIMARY KEY,
            harga_beli REAL,
            jumlah_isi REAL,
            satuan TEXT,
            harga_satuan REAL,
            stok_gudang REAL DEFAULT 0,
            stok_kios REAL DEFAULT 0,
            stok_cafe REAL DEFAULT 0,
            stok_taman REAL DEFAULT 0,
            harga_jual_internal REAL DEFAULT 0
        )
    """)
    # 2. Tabel Resep / Operasional
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS resep (
            id SERIAL PRIMARY KEY,
            nama_resep TEXT UNIQUE,
            total_hpp_bahan REAL,
            total_operasional REAL,
            total_hpp_final REAL,
            harga_jual REAL DEFAULT 0,
            tanggal_dibuat TEXT
        )
    """)
    # 3. Tabel Detail Resep
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS detail_resep (
            id SERIAL PRIMARY KEY,
            resep_id INTEGER,
            nama_bahan TEXT,
            jumlah_pakai REAL,
            satuan TEXT,
            subtotal_biaya REAL
        )
    """)
    # 4. Tabel Riwayat Stok & Penjualan Internal
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS riwayat_stok (
            id SERIAL PRIMARY KEY,
            tanggal TEXT,
            nama_bahan TEXT,
            jenis_transaksi TEXT,
            jumlah REAL,
            keterangan TEXT,
            kerugian_rp REAL DEFAULT 0,
            laba_internal REAL DEFAULT 0,
            dari_gudang TEXT,
            ke_unit TEXT
        )
    """)
    
    # SUNTIKAN KOLOM TAMAN JIKA BELUM ADA
    try: cursor.execute("ALTER TABLE bahan_baku ADD COLUMN stok_taman REAL DEFAULT 0")
    except: pass 
        
    cursor.close()
    conn.close()

try:
    init_db()
except Exception as e:
    st.error(f"⚠️ Gagal inisialisasi tabel! Eror: {e}")

if 'racikan_sementara' not in st.session_state:
    st.session_state.racikan_sementara = pd.DataFrame(columns=["Nama Bahan", "Jumlah Pakai", "Satuan", "Subtotal"])
if 'edit_resep_nama' not in st.session_state:
    st.session_state.edit_resep_nama = ""

# ==========================================
# 2. MENU NAVIGASI
# ==========================================
st.sidebar.title("🏢 ERP MULTI-GUDANG V3")
st.sidebar.write("---")
menu = st.sidebar.radio("Navigasi Sistem:", 
    ["📊 Dashboard Analitik", "📦 Manajemen Gudang Pusat", "🚚 Penjualan ke Unit (Cabang)", "🍳 Operasional & Dapur", "📂 Arsip & Harga Jual"]
)

def get_daftar_bahan():
    try:
        conn = get_connection()
        df = pd.read_sql_query("SELECT * FROM bahan_baku ORDER BY nama_bahan ASC", conn)
        conn.close()
        return df
    except:
        return pd.DataFrame()

# ==========================================
# 3. TAB: DASHBOARD ANALITIK
# ==========================================
if menu == "📊 Dashboard Analitik":
    st.title("📊 Laba Internal & Analitik Pusat")
    st.write("Pantau keuntungan yang didapat Gudang Utama (Etnik) dari hasil menjual bahan baku ke unit Kios, Cafe, dan Taman.")
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT SUM(laba_internal) FROM riwayat_stok WHERE jenis_transaksi='Penjualan Internal'")
        total_laba_gudang = cursor.fetchone()[0] or 0.0
        
        cursor.execute("SELECT SUM(kerugian_rp) FROM riwayat_stok WHERE jenis_transaksi='Barang Hilang/Rugi'")
        total_rugi_gudang = cursor.fetchone()[0] or 0.0
        
        df_log = pd.read_sql_query('SELECT tanggal as "Waktu", nama_bahan as "Barang", jumlah as "Qty", ke_unit as "Pembeli", keterangan as "Total Jual (Rp)", laba_internal as "Laba Gudang (Rp)" FROM riwayat_stok WHERE jenis_transaksi=\'Penjualan Internal\' ORDER BY id DESC', conn)
        conn.close()
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Laba Bersih Gudang Induk", f"Rp {total_laba_gudang:,.0f}", "Omset Unit Masuk")
        c2.metric("Kerugian Barang Hilang", f"Rp {total_rugi_gudang:,.0f}", delta=f"-Rp {total_rugi_gudang:,.0f}", delta_color="inverse")
        
        st.write("---")
        st.subheader("📜 Riwayat Distribusi Gudang ke Semua Unit")
        st.dataframe(df_log, use_container_width=True)
    except Exception as e:
        st.warning(f"Menunggu sinkronisasi data... ({e})")

# ==========================================
# 4. TAB: MANAJEMEN GUDANG PUSAT
# ==========================================
elif menu == "📦 Manajemen Gudang Pusat":
    st.title("📦 Gudang Induk (Etnik Papua)")
    st.write("⚠️ **Aturan Sistem:** Semua barang baru (milik Kios, Cafe, atau Taman) **WAJIB** diinput ke Gudang Induk terlebih dahulu di halaman ini, lalu didistribusikan melalui menu Transfer.")
    
    df_bahan_ada = get_daftar_bahan()
    pilihan_edit = "-- Input Produk Baru / Kulakan Baru --"
    if not df_bahan_ada.empty:
        pilihan_edit = st.selectbox("💡 Pilih barang untuk diedit/ditambah, atau biarkan di pilihan pertama untuk Produk Baru:", ["-- Input Produk Baru / Kulakan Baru --"] + df_bahan_ada['nama_bahan'].tolist())
    
    val_nama, val_harga, val_isi, val_satuan, val_jual_internal = "", 0.0, 1.0, "pcs", 0.0
    if pilihan_edit != "-- Input Produk Baru / Kulakan Baru --":
        row_edit = df_bahan_ada[df_bahan_ada['nama_bahan'] == pilihan_edit].iloc[0]
        val_nama = row_edit['nama_bahan']
        val_harga = float(row_edit['harga_beli'])
        val_isi = float(row_edit['jumlah_isi'])
        val_satuan = row_edit['satuan']
        val_jual_internal = float(row_edit.get('harga_jual_internal', 0))
        
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: entry_nama = st.text_input("Nama Barang (Merek/
