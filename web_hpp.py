import streamlit as st
import pandas as pd
import psycopg2
import time
from datetime import datetime

# ==========================================
# 1. PENGATURAN HALAMAN & KONEKSI SUPABASE
# ==========================================
st.set_page_config(page_title="ERP Cloud V5 (Multi-Role)", layout="wide", page_icon="🏢")

SUPABASE_URI = "postgresql://postgres.jskxygpvnbjgjjgsvwqf:ZeeyStore175@aws-0-ap-southeast-2.pooler.supabase.com:6543/postgres"

def get_connection():
    return psycopg2.connect(SUPABASE_URI)

def init_db():
    conn = get_connection()
    conn.autocommit = True 
    cursor = conn.cursor()
    
    # Tabel Users
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT,
            role TEXT
        )
    """)
    # Buat akun Owner default jika belum ada
    cursor.execute("INSERT INTO users (username, password, role) VALUES ('owner', 'owner123', 'Owner') ON CONFLICT DO NOTHING")
    
    # Tabel-tabel Sistem Gudang & Resep
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bahan_baku (
            nama_bahan TEXT PRIMARY KEY,
            harga_beli REAL, jumlah_isi REAL, satuan TEXT, harga_satuan REAL,
            stok_gudang REAL DEFAULT 0, stok_kios REAL DEFAULT 0,
            stok_cafe REAL DEFAULT 0, stok_taman REAL DEFAULT 0,
            harga_jual_internal REAL DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS resep (
            id SERIAL PRIMARY KEY, nama_resep TEXT UNIQUE,
            total_hpp_bahan REAL, total_operasional REAL, total_hpp_final REAL,
            harga_jual REAL DEFAULT 0, tanggal_dibuat TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS detail_resep (
            id SERIAL PRIMARY KEY, resep_id INTEGER, nama_bahan TEXT,
            jumlah_pakai REAL, satuan TEXT, subtotal_biaya REAL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS riwayat_stok (
            id SERIAL PRIMARY KEY, tanggal TEXT, nama_bahan TEXT,
            jenis_transaksi TEXT, jumlah REAL, keterangan TEXT,
            kerugian_rp REAL DEFAULT 0, laba_internal REAL DEFAULT 0,
            dari_gudang TEXT, ke_unit TEXT
        )
    """)
    
    try: cursor.execute("ALTER TABLE bahan_baku ADD COLUMN stok_taman REAL DEFAULT 0")
    except: pass 
        
    cursor.close()
    conn.close()

try: init_db()
except Exception as e: st.error(f"⚠️ Gagal inisialisasi tabel! Eror: {e}")

# ==========================================
# 2. SISTEM LOGIN & SESSION
# ==========================================
if 'sudah_login' not in st.session_state: st.session_state.sudah_login = False
if 'username' not in st.session_state: st.session_state.username = ""
if 'role' not in st.session_state: st.session_state.role = ""

if not st.session_state.sudah_login:
    st.title("🔐 Login Sistem ERP Etnik Papua")
    st.write("Silakan masukkan Username dan Password Anda.")
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
        else:
            st.error("❌ Username atau Password salah!")
    st.stop()

# ==========================================
# 3. NAVIGASI BERDASARKAN ROLE
# ==========================================
role = st.session_state.role
st.sidebar.title("🏢 ERP ETNIK PAPUA")
st.sidebar.write(f"👤 User: **{st.session_state.username}**")
st.sidebar.write(f"🛡️ Hak Akses: **{role}**")
if st.sidebar.button("🚪 Keluar / Logout"):
    st.session_state.sudah_login = False
    st.rerun()
st.sidebar.write("---")

# Mengatur menu apa saja yang bisa dilihat masing-masing Role
menu_options = ["🍳 Operasional & Dapur (Input Harian)"] # Karyawan cuma bisa lihat ini
if role in ["Owner", "Admin"]:
    menu_options = ["📊 Dashboard Analitik", "📦 Manajemen Gudang Pusat", "🚚 Penjualan ke Unit (Cabang)", "🍳 Operasional & Dapur (Input Harian)", "📂 Arsip & Harga Jual"]
if role == "Owner":
    menu_options.append("👥 Manajemen User (Admin/Staf)")

menu = st.sidebar.radio("Navigasi Sistem:", menu_options)

def get_daftar_bahan():
    try:
        conn = get_connection()
        df = pd.read_sql_query("SELECT * FROM bahan_baku ORDER BY nama_bahan ASC", conn)
        conn.close()
        return df
    except: return pd.DataFrame()

# ==========================================
# 4. MENU 1: MANAJEMEN USER (KHUSUS OWNER)
# ==========================================
if menu == "👥 Manajemen User (Admin/Staf)":
    st.title("👥 Manajemen Akses Karyawan & Admin")
    st.write("Di sini Owner bisa membuatkan akun untuk staf atau menghapus akun staf yang sudah keluar.")
    
    conn = get_connection()
    df_users = pd.read_sql_query("SELECT username as \"Username\", role as \"Hak Akses / Posisi\" FROM users", conn)
    
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("📋 Daftar Pengguna Saat Ini")
        st.dataframe(df_users, use_container_width=True)
        
        st.subheader("🗑️ Hapus Akun Staf")
        hapus_user = st.selectbox("Pilih Username yang akan dihapus:", df_users['Username'].tolist())
        if st.button("Hapus Akun Ini", type="primary"):
            if hapus_user == "owner":
                st.error("Akun Owner utama tidak boleh dihapus!")
            else:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM users WHERE username=%s", (hapus_user,))
                conn.commit()
                st.success(f"Akun {hapus_user} berhasil dihapus!")
                time.sleep(1)
                st.rerun()
                
    with col2:
        st.subheader("➕ Tambah Akun Baru")
        with st.form("tambah_user"):
            new_u = st.text_input("Username Baru (tanpa spasi)")
            new_p = st.text_input("Password", type="password")
            new_r = st.selectbox("Posisi / Hak Akses", ["Karyawan", "Admin", "Owner"])
            
            if st.form_submit_button("Simpan Akun"):
                if new_u and new_p:
                    cursor = conn.cursor()
                    try:
                        cursor.execute("INSERT INTO users (username, password, role) VALUES (%s, %s, %s)", (new_u.lower(), new_p, new_r))
                        conn.commit()
                        st.success(f"Akun {new_u} berhasil dibuat!")
                        time.sleep(1)
                        st.rerun()
                    except:
                        st.error("Username tersebut sudah dipakai! Gunakan yang lain.")
                else:
                    st.error("Username dan password tidak boleh kosong!")
    conn.close()

# ==========================================
# 5. MENU LAINNYA (DASHBOARD, GUDANG, TRANSFER, DAPUR)
# ==========================================
elif menu == "📊 Dashboard Analitik":
    st.title("📊 Laba Internal & Analitik Pusat")
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(laba_internal) FROM riwayat_stok WHERE jenis_transaksi='Penjualan Internal'")
        total_laba_gudang = cursor.fetchone()[0] or 0.0
        df_log = pd.read_sql_query('SELECT tanggal as "Waktu", nama_bahan as "Barang", jumlah as "Qty", ke_unit as "Pembeli", keterangan as "Total Jual (Rp)", laba_internal as "Laba Gudang (Rp)" FROM riwayat_stok WHERE jenis_transaksi=\'Penjualan Internal\' ORDER BY id DESC', conn)
        conn.close()
        
        st.metric("Laba Bersih Gudang Induk", f"Rp {total_laba_gudang:,.0f}", "Omset Unit Masuk")
        st.write("---")
        st.subheader("📜 Riwayat Distribusi Gudang ke Semua Unit")
        st.dataframe(df_log, use_container_width=True)
    except: st.warning("Menunggu sinkronisasi data...")

elif menu == "📦 Manajemen Gudang Pusat":
    st.title("📦 Gudang Induk (Etnik Papua)")
    df_bahan_ada = get_daftar_bahan()
    pilihan_edit = "-- Input Produk Baru --"
    if not df_bahan_ada.empty:
        pilihan_edit = st.selectbox("Pilih barang untuk diedit/ditambah:", ["-- Input Produk Baru --"] + df_bahan_ada['nama_bahan'].tolist())
    
    val_nama, val_harga, val_isi, val_satuan, val_jual_internal = "", 0.0, 1.0, "pcs", 0.0
    if pilihan_edit != "-- Input Produk Baru --":
        row_edit = df_bahan_ada[df_bahan_ada['nama_bahan'] == pilihan_edit].iloc[0]
        val_nama = row_edit['nama_bahan']
        val_harga = float(row_edit['harga_beli'])
        val_isi = float(row_edit['jumlah_isi'])
        val_satuan = row_edit['satuan']
        val_jual_internal = float(row_edit.get('harga_jual_internal', 0))
        
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: entry_nama = st.text_input("Nama Barang", value=val_nama)
    with c2: entry_harga = st.number_input("Harga Beli (Rp)", min_value=0.0, value=val_harga)
    with c3: entry_isi = st.number_input("Jumlah Isi", min_value=1.0, value=val_isi)
    with c4: entry_satuan = st.text_input("Satuan", value=val_satuan)
    with c5: entry_jual_int = st.number_input("Harga Jual Internal (Rp)", min_value=0.0, value=val_jual_internal)
    
    if st.button("💾 Simpan ke Gudang Induk", type="primary"):
        if entry_nama:
            h_satuan = entry_harga / entry_isi
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT stok_gudang FROM bahan_baku WHERE nama_bahan=%s", (entry_nama,))
            res = cursor.fetchone()
            stok_sekarang = (res[0] if res else 0) + entry_isi if pilihan_edit == "-- Input Produk Baru --" else entry_isi 
            
            cursor.execute("""
                INSERT INTO bahan_baku (nama_bahan, harga_beli, jumlah_isi, satuan, harga_satuan, stok_gudang, harga_jual_internal) 
                VALUES (%s, %s, %s, %s, %s, %s, %s) 
                ON CONFLICT (nama_bahan) 
                DO UPDATE SET harga_beli=EXCLUDED.harga_beli, jumlah_isi=EXCLUDED.jumlah_isi, 
                satuan=EXCLUDED.satuan, harga_satuan=EXCLUDED.harga_satuan, harga_jual_internal=EXCLUDED.harga_jual_internal
            """, (entry_nama.strip(), entry_harga, entry_isi, entry_satuan.strip(), h_satuan, stok_sekarang, entry_jual_int))
            conn.commit()
            conn.close()
            st.success(f"✅ Tersimpan!")
            time.sleep(1)
            st.rerun()

    st.write("---")
    if not df_bahan_ada.empty:
        df_tampil = df_bahan_ada[['nama_bahan', 'harga_satuan', 'harga_jual_internal', 'stok_gudang', 'stok_cafe', 'stok_kios', 'stok_taman', 'satuan']]
        df_tampil.columns = ['Nama Barang', 'Modal Dasar', 'Jual Internal', 'INDUK', 'CAFE', 'KIOS', 'TAMAN', 'Satuan']
        st.dataframe(df_tampil, use_container_width=True)

elif menu == "🚚 Penjualan ke Unit (Cabang)":
    st.title("🚚 Transfer & Penjualan Internal")
    df_g = get_daftar_bahan()
    if df_g.empty: st.warning("Gudang induk masih kosong.")
    else:
        col1, col2, col3 = st.columns(3)
        with col1: bahan_transfer = st.selectbox("Barang dari Gudang Induk:", df_g['nama_bahan'].tolist())
        data_b = df_g[df_g['nama_bahan'] == bahan_transfer].iloc[0]
        stok_induk = data_b['stok_gudang']
        
        with col2: qty_transfer = st.number_input(f"Keluarkan Berapa? (Sisa: {stok_induk})", min_value=1.0, max_value=float(stok_induk) if stok_induk > 0 else 1.0)
        with col3: unit_tujuan = st.radio("Tujuan Transfer?", ["Cafe", "Kios", "Taman"])
        
        if st.button(f"🛒 Transfer ke {unit_tujuan}", type="primary"):
            if stok_induk >= qty_transfer:
                tgl = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                laba = (qty_transfer * data_b.get('harga_jual_internal', data_b['harga_satuan'])) - (qty_transfer * data_b['harga_satuan'])
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("UPDATE bahan_baku SET stok_gudang = stok_gudang - %s WHERE nama_bahan = %s", (qty_transfer, bahan_transfer))
                
                if unit_tujuan == "Cafe": cursor.execute("UPDATE bahan_baku SET stok_cafe = COALESCE(stok_cafe, 0) + %s WHERE nama_bahan = %s", (qty_transfer, bahan_transfer))
                elif unit_tujuan == "Kios": cursor.execute("UPDATE bahan_baku SET stok_kios = COALESCE(stok_kios, 0) + %s WHERE nama_bahan = %s", (qty_transfer, bahan_transfer))
                elif unit_tujuan == "Taman": cursor.execute("UPDATE bahan_baku SET stok_taman = COALESCE(stok_taman, 0) + %s WHERE nama_bahan = %s", (qty_transfer, bahan_transfer))
                
                cursor.execute("INSERT INTO riwayat_stok (tanggal, nama_bahan, jenis_transaksi, jumlah, laba_internal, dari_gudang, ke_unit) VALUES (%s,%s,%s,%s,%s,%s,%s)", 
                               (tgl, bahan_transfer, 'Penjualan Internal', qty_transfer, laba, 'Gudang Etnik', unit_tujuan))
                conn.commit()
                conn.close()
                st.success(f"✅ Sukses transfer ke {unit_tujuan}!")
                time.sleep(1)
                st.rerun()
            else: st.error("Stok Gudang Induk tidak mencukupi!")

elif menu == "🍳 Operasional & Dapur (Input Harian)":
    st.title("🍳 Ruang Penggunaan & Resep")
    unit_pembuat = st.radio("Unit Operasional (Pilih sesuai tempat Anda bekerja):", ["Cafe", "Kios", "Taman"])
    
    if 'racikan_sementara' not in st.session_state: st.session_state.racikan_sementara = pd.DataFrame(columns=["Nama Bahan", "Jumlah Pakai", "Satuan", "Subtotal"])
    
    df_b = get_daftar_bahan()
    if df_b.empty: st.warning("Belum ada barang di database!")
    else:
        col_c1, col_c2, col_c3 = st.columns([2, 1, 1])
        with col_c1:
            kata_kunci = st.text_input("🔍 Cari barang/bahan:")
            filtered_bahan = df_b[df_b['nama_bahan'].str.lower().str.contains(kata_kunci.lower())] if kata_kunci else df_b
            pilih_b = st.selectbox("Pilih:", filtered_bahan['nama_bahan'].tolist() if not filtered_bahan.empty else ["Tidak ditemukan"])
        with col_c2:
            j_pakai = st.number_input("Jumlah Penggunaan", min_value=0.0, step=1.0)
        with col_c3:
            st.write("")
            st.write("")
            if st.button("➕ Tambah ke Draf"):
                if pilih_b != "Tidak ditemukan" and j_pakai > 0:
                    data_row = df_b[df_b['nama_bahan'] == pilih_b].iloc[0]
                    h_sat = data_row.get('harga_jual_internal', data_row['harga_satuan'])
                    if h_sat <= 0: h_sat = data_row['harga_satuan']
                    sub = j_pakai * h_sat
                    df_skrg = st.session_state.racikan_sementara
                    if pilih_b in df_skrg['Nama Bahan'].values:
                        df_skrg.loc[df_skrg['Nama Bahan'] == pilih_b, ["Jumlah Pakai", "Subtotal"]] = [j_pakai, sub]
                    else:
                        tambah_row = pd.DataFrame([[pilih_b, j_pakai, data_row['satuan'], sub]], columns=df_skrg.columns)
                        st.session_state.racikan_sementara = pd.concat([df_skrg, tambah_row], ignore_index=True)
                    st.rerun()

        st.write("---")
        if not st.session_state.racikan_sementara.empty:
            edited_df = st.data_editor(st.session_state.racikan_sementara, use_container_width=True)
            st.session_state.racikan_sementara = edited_df
            tot_bahan = st.session_state.racikan_sementara['Subtotal'].sum()
        else: tot_bahan = 0.0

        col_s1, col_s2 = st.columns(2)
        with col_s1: nama_menu_final = st.text_input("Nama Laporan/Menu Akhir:")
        with col_s2:
            st.write("")
            st.write("")
            if st.button("✅ Kunci Laporan & Potong Stok Unit", type="primary"):
                if nama_menu_final and not st.session_state.racikan_sementara.empty:
                    conn = get_connection()
                    cursor = conn.cursor()
                    tgl_entri = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    nama_unik = f"[{unit_pembuat}] {nama_menu_final}"
                    
                    cursor.execute("INSERT INTO resep (nama_resep, total_hpp_bahan, tanggal_dibuat) VALUES (%s, %s, %s) ON CONFLICT (nama_resep) DO UPDATE SET total_hpp_bahan=EXCLUDED.total_hpp_bahan", (nama_unik, tot_bahan, tgl_entri))
                    cursor.execute("SELECT id FROM resep WHERE nama_resep=%s", (nama_unik,))
                    r_id = cursor.fetchone()[0]
                    cursor.execute("DELETE FROM detail_resep WHERE resep_id=%s", (r_id,))
                    
                    for _, r in st.session_state.racikan_sementara.iterrows():
                        cursor.execute("INSERT INTO detail_resep (resep_id, nama_bahan, jumlah_pakai, satuan, subtotal_biaya) VALUES (%s,%s,%s,%s,%s)", (r_id, r['Nama Bahan'], r['Jumlah Pakai'], r['Satuan'], r['Subtotal']))
                        if unit_pembuat == "Cafe": cursor.execute("UPDATE bahan_baku SET stok_cafe = COALESCE(stok_cafe,0) - %s WHERE nama_bahan = %s", (r['Jumlah Pakai'], r['Nama Bahan']))
                        elif unit_pembuat == "Kios": cursor.execute("UPDATE bahan_baku SET stok_kios = COALESCE(stok_kios,0) - %s WHERE nama_bahan = %s", (r['Jumlah Pakai'], r['Nama Bahan']))
                        elif unit_pembuat == "Taman": cursor.execute("UPDATE bahan_baku SET stok_taman = COALESCE(stok_taman,0) - %s WHERE nama_bahan = %s", (r['Jumlah Pakai'], r['Nama Bahan']))
                        
                    conn.commit()
                    conn.close()
                    st.success("✅ Data tersimpan & Stok unit terpotong!")
                    time.sleep(1)
                    st.session_state.racikan_sementara = pd.DataFrame(columns=["Nama Bahan", "Jumlah Pakai", "Satuan", "Subtotal"])
                    st.rerun()

elif menu == "📂 Arsip & Harga Jual":
    st.title("📂 Arsip Dokumen Pengeluaran / Resep")
    try:
        conn = get_connection()
        df_resep = pd.read_sql_query('SELECT id as "ID", nama_resep as "Nama Laporan/Menu", total_hpp_bahan as "Total Biaya (Rp)", tanggal_dibuat as "Tanggal Kunci" FROM resep', conn)
        if df_resep.empty: st.info("Belum ada arsip.")
        else:
            st.dataframe(df_resep, use_container_width=True)
            pilih_r = st.selectbox("Pilih Laporan/Menu untuk dihapus:", df_resep['Nama Laporan/Menu'].tolist())
            if st.button("🗑️ Hapus Laporan Permanen", type="primary"):
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM resep WHERE nama_resep=%s", (pilih_r,))
                r_id = cursor.fetchone()[0]
                cursor.execute("DELETE FROM detail_resep WHERE resep_id=%s", (r_id,))
                cursor.execute("DELETE FROM resep WHERE id=%s", (r_id,))
                conn.commit()
                st.rerun()
        conn.close()
    except: st.error("Gagal memuat arsip.")
