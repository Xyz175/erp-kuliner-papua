import streamlit as st
import pandas as pd
import psycopg2
import time
from datetime import datetime

# ==========================================
# 1. KONFIGURASI HALAMAN & DATABASE CLOUD
# ==========================================
st.set_page_config(page_title="ERP Cloud V8 (Logical Edition)", layout="wide", page_icon="🏢")

SUPABASE_URI = "postgresql://postgres.jskxygpvnbjgjjgsvwqf:ZeeyStore175@aws-0-ap-southeast-2.pooler.supabase.com:6543/postgres"

def get_connection():
    return psycopg2.connect(SUPABASE_URI)

def init_db():
    conn = get_connection()
    conn.autocommit = True 
    cursor = conn.cursor()
    
    # Otak Otorisasi Pengguna
    cursor.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT)")
    cursor.execute("INSERT INTO users (username, password, role) VALUES ('owner', 'owner123', 'Owner') ON CONFLICT DO NOTHING")
    
    # Logika Database Cafe (Bahan Baku & Resep HPP)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bahan_baku (
            nama_bahan TEXT PRIMARY KEY, harga_beli REAL, jumlah_isi REAL, satuan TEXT, harga_satuan REAL,
            stok_gudang REAL DEFAULT 0, stok_cafe REAL DEFAULT 0, stok_taman REAL DEFAULT 0, harga_jual_internal REAL DEFAULT 0
        )
    """)
    cursor.execute("CREATE TABLE IF NOT EXISTS resep (id SERIAL PRIMARY KEY, nama_resep TEXT UNIQUE, total_hpp_bahan REAL, total_operasional REAL, total_hpp_final REAL, harga_jual REAL DEFAULT 0, tanggal_dibuat TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS detail_resep (id SERIAL PRIMARY KEY, resep_id INTEGER, nama_bahan TEXT, jumlah_pakai REAL, satuan TEXT, subtotal_biaya REAL)")
    cursor.execute("CREATE TABLE IF NOT EXISTS riwayat_stok (id SERIAL PRIMARY KEY, tanggal TEXT, nama_bahan TEXT, jenis_transaksi TEXT, jumlah REAL, keterangan TEXT, laba_internal REAL DEFAULT 0, dari_gudang TEXT, ke_unit TEXT)")
    
    # Logika Database Kios (Terpisah 100% dari HPP Cafe)
    cursor.execute("CREATE TABLE IF NOT EXISTS stok_kios_item (nama_barang TEXT PRIMARY KEY, stok REAL DEFAULT 0, satuan TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS riwayat_kios (id SERIAL PRIMARY KEY, tanggal TEXT, nama_barang TEXT, jenis_transaksi TEXT, jumlah REAL, pic TEXT)")
    
    cursor.close()
    conn.close()

try: init_db()
except Exception as e: st.error(f"⚠️ Gagal sinkronisasi arsitektur DB: {e}")

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
# 2. GERBANG UTAMA (SISTEM LOGIN)
# ==========================================
if not st.session_state.sudah_login:
    st.title("🔐 ERP Rumah Etnik Papua")
    st.write("Sistem logistik dan finansial terintegrasi cloud.")
    user_input = st.text_input("Username")
    pass_input = st.text_input("Password", type="password")
    if st.button("Masuk ke Sistem", type="primary"):
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
        else: st.error("❌ Akun tidak ditemukan atau password salah!")
    st.stop()

# ==========================================
# 3. FILTRASI LOGIS MENU BERDASARKAN ROLE
# ==========================================
role = st.session_state.role
st.sidebar.title("🏢 MENU KONTROL ERP")
st.sidebar.write(f"Pengguna: **{st.session_state.username}** ({role})")
if st.sidebar.button("🚪 Keluar (Logout)"):
    st.session_state.sudah_login = False
    st.rerun()
st.sidebar.write("---")

# Pembatasan Menu yang sangat logis
if role == "Gudang Kios":
    menu_options = ["📦 Gudang Kios (In/Out)"]
elif role == "Karyawan":
    menu_options = ["🍽️ Dapur Cafe: Input & Arsip HPP"]
elif role in ["Owner", "Admin"]:
    menu_options = ["📊 Dashboard Analitik", "📦 Gudang Induk (Pusat Pusat)", "🚚 Transfer Logistik ke Cabang", "🍽️ Dapur Cafe: Input & Arsip HPP", "📦 Gudang Kios (In/Out)", "📂 Laporan Akhir & Harga Jual"]

if role == "Owner":
    menu_options.append("👥 Manajemen Otoritas User")

menu = st.sidebar.radio("Pilih Halaman Kerja:", menu_options)

# ==========================================
# 4. IMPLEMENTASI LOGIKA HALAMAN
# ==========================================

# --- MENU A: DAPUR CAFE (INPUT & ARSIP HPP) ---
if menu == "🍽️ Dapur Cafe: Input & Arsip HPP":
    st.title("🍽️ Pusat Operasional Dapur & Manajemen HPP Cafe")
    tab_dapur, tab_arsip_cafe = st.tabs(["🍳 1. Input Pemakaian Dapur", "📜 2. Arsip Nilai HPP Menu"])
    
    with tab_dapur:
        st.subheader("Pencatatan Bahan Baku Masuk Menu")
        df_b = get_daftar_bahan()
        if df_b.empty: st.warning("Stok bahan baku di Cafe kosong. Mohon minta transfer barang ke Admin Gudang.")
        else:
            c1, c2, c3 = st.columns([2, 1, 1])
            with c1:
                cari = st.text_input("🔍 Ketik nama bahan baku Cafe:")
                df_f = df_b[df_b['nama_bahan'].str.lower().str.contains(cari.lower())] if cari else df_b
                pilih_b = st.selectbox("Pilih item bahan:", df_f['nama_bahan'].tolist() if not df_f.empty else ["Kosong"])
            with c2:
                qty = st.number_input("Volume/Jumlah Pakai:", min_value=0.0, step=1.0)
            with c3:
                st.write(""); st.write("")
                if st.button("➕ Tambah Bahan", use_container_width=True):
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
            
            st.subheader("⚡ Komponen Biaya Non-Bahan (Operasional)")
            co1, co2 = st.columns(2)
            with co1: waktu = st.number_input("Waktu Memasak/Meracik (Menit):", min_value=0.0, step=5.0)
            with co2: gas = st.number_input("Estimasi Gas yang Terpakai (Kg):", min_value=0.0, format="%.3f")
            
            biaya_ops = ((10000/60)*waktu) + ((3000/60)*waktu) + (gas * 18000)
            tot_final = tot_bahan + biaya_ops
            
            st.info(f"📊 Ringkasan Finansial: Modal Bahan: Rp {tot_bahan:,.0f} | Operasional Dapur: Rp {biaya_ops:,.0f} | HPP Pokok Menu: Rp {tot_final:,.2f}")
            
            cx1, cx2 = st.columns(2)
            with cx1: nama_menu = st.text_input("Beri Nama Menu Kuliner Baru:")
            with cx2:
                st.write(""); st.write("")
                if st.button("💾 Kunci Resep & Potong Stok Cafe", type="primary", use_container_width=True):
                    if nama_menu:
                        conn = get_connection()
                        cursor = conn.cursor()
                        tgl = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        cursor.execute("INSERT INTO resep (nama_resep, total_hpp_bahan, total_operasional, total_hpp_final, tanggal_dibuat) VALUES (%s,%s,%s,%s,%s) ON CONFLICT (nama_resep) DO UPDATE SET total_hpp_final=EXCLUDED.total_hpp_final", (nama_menu.strip(), tot_bahan, biaya_ops, tot_final, tgl))
                        cursor.execute("SELECT id FROM resep WHERE nama_resep=%s", (nama_menu.strip(),))
                        r_id = cursor.fetchone()[0]
                        cursor.execute("DELETE FROM detail_resep WHERE resep_id=%s", (r_id,))
                        
                        for _, r in st.session_state.racikan_sementara.iterrows():
                            cursor.execute("INSERT INTO detail_resep (resep_id, nama_bahan, jumlah_pakai, satuan, subtotal_biaya) VALUES (%s,%s,%s,%s,%s)", (r_id, r['Nama Bahan'], r['Jumlah Pakai'], r['Satuan'], r['Subtotal']))
                            cursor.execute("UPDATE bahan_baku SET stok_cafe = COALESCE(stok_cafe,0) - %s WHERE nama_bahan = %s", (r['Jumlah Pakai'], r['Nama Bahan']))
                        conn.commit()
                        conn.close()
                        st.success("✅ Resep Menu dikunci ke Cloud dan Stok Cabang Cafe otomatis terpotong!")
                        time.sleep(1.5)
                        st.session_state.racikan_sementara = pd.DataFrame(columns=["Nama Bahan", "Jumlah Pakai", "Satuan", "Subtotal"])
                        st.rerun()

    with tab_arsip_cafe:
        st.subheader("Daftar Pengeluaran & Kalkulasi HPP Cafe Terdata")
        try:
            conn = get_connection()
            df_c = pd.read_sql_query('SELECT nama_resep as "Nama Menu/Resep", total_hpp_bahan as "Modal Bahan (Rp)", total_operasional as "Biaya Kerja (Rp)", total_hpp_final as "Total HPP Final (Rp)", tanggal_dibuat as "Tanggal Pembuatan" FROM resep', conn)
            conn.close()
            st.dataframe(df_c, use_container_width=True)
            if not df_c.empty:
                st.download_button("📥 Unduh Laporan HPP Cafe (Excel CSV)", data=convert_df_to_csv(df_c), file_name='Arsip_HPP_Cafe.csv', mime='text/csv')
        except: st.info("Belum ada resep terdokumentasi.")

# --- MENU B: GUDANG KIOS ---
elif menu == "📦 Gudang Kios (In/Out)":
    st.title("📦 Tata Kelola Logistik Gudang Kios")
    tab_in, tab_out, tab_report = st.tabs(["📥 1. Barang Masuk Kios", "📤 2. Barang Keluar Kios", "📊 3. Laporan Stok & Excel"])
    conn = get_connection()
    df_kios = pd.read_sql_query("SELECT nama_barang, stok, satuan FROM stok_kios_item ORDER BY nama_barang ASC", conn)
    
    with tab_in:
        pilihan = ["-- Input Barang Baru --"] + (df_kios['nama_barang'].tolist() if not df_kios.empty else [])
        barang_masuk = st.selectbox("Pilih Komoditas Kios:", pilihan)
        c1, c2, c3 = st.columns(3)
        with c1: nama_baru = st.text_input("Nama Produk", value="" if barang_masuk == "-- Input Barang Baru --" else barang_masuk, disabled=(barang_masuk != "-- Input Barang Baru --"))
        with c2: qty_masuk = st.number_input("Kuantitas Masuk:", min_value=1.0, step=1.0)
        with c3: sat_baru = st.text_input("Kemasan/Satuan:", value="pcs" if barang_masuk == "-- Input Barang Baru --" else df_kios[df_kios['nama_barang']==barang_masuk]['satuan'].values[0])
        
        if st.button("📥 Validasi Masuk Kios", type="primary"):
            if nama_baru:
                cursor = conn.cursor()
                tgl = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("INSERT INTO stok_kios_item (nama_barang, stok, satuan) VALUES (%s, %s, %s) ON CONFLICT (nama_barang) DO UPDATE SET stok = stok_kios_item.stok + EXCLUDED.stok", (nama_baru.strip(), qty_masuk, sat_baru))
                cursor.execute("INSERT INTO riwayat_kios (tanggal, nama_barang, jenis_transaksi, jumlah, pic) VALUES (%s, %s, %s, %s, %s)", (tgl, nama_baru.strip(), 'Masuk', qty_masuk, st.session_state.username))
                conn.commit()
                st.success("✅ Mutasi barang masuk sukses dicatat!")
                time.sleep(1.5)
                st.rerun()

    with tab_out:
        if df_kios.empty: st.warning("Belum ada ketersediaan stok produk di Kios.")
        else:
            out1, out2 = st.columns(2)
            with out1: barang_keluar = st.selectbox("Pilih Produk Keluar:", df_kios['nama_barang'].tolist())
            stok_sisa = df_kios[df_kios['nama_barang']==barang_keluar]['stok'].values[0]
            with out2: qty_keluar = st.number_input(f"Kuantitas Keluar (Tersedia: {stok_sisa})", min_value=1.0, max_value=float(stok_sisa) if stok_sisa > 0 else 1.0, step=1.0)
            if st.button("📤 Validasi Keluar Kios", type="primary"):
                cursor = conn.cursor()
                tgl = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("UPDATE stok_kios_item SET stok = stok - %s WHERE nama_barang = %s", (qty_keluar, barang_keluar))
                cursor.execute("INSERT INTO riwayat_kios (tanggal, nama_barang, jenis_transaksi, jumlah, pic) VALUES (%s, %s, %s, %s, %s)", (tgl, barang_keluar, 'Keluar', qty_keluar, st.session_state.username))
                conn.commit()
                st.success("✅ Mutasi penjualan/keluar Kios berhasil dideklarasikan!")
                time.sleep(1.5)
                st.rerun()

    with tab_report:
        st.dataframe(df_kios, use_container_width=True)
        if not df_kios.empty:
            st.download_button("📥 Download Excel Stok Kios", data=convert_df_to_csv(df_kios), file_name='Stok_Kios_Realtime.csv', mime='text/csv')
        st.write("---")
        df_log_kios = pd.read_sql_query("SELECT tanggal as \"Waktu Mutasi\", nama_barang as \"Nama Barang\", jenis_transaksi as \"Status\", jumlah as \"Qty\", pic as \"Operator\" FROM riwayat_kios ORDER BY id DESC", conn)
        st.dataframe(df_log_kios, use_container_width=True)
    conn.close()

# --- MENU C: DASHBOARD ANALITIK (OWNER/ADMIN) ---
elif menu == "📊 Dashboard Analitik":
    st.title("📊 Pusat Kendali Finansial & Laba Bisnis")
    try:
        conn = get_connection()
        df_log = pd.read_sql_query("SELECT tanggal as \"Waktu\", nama_bahan as \"Nama Bahan\", jumlah as \"Volume\", ke_unit as \"Unit Cabang\", keterangan as \"Nilai Omset\", laba_internal as \"Profit internal (Rp)\" FROM riwayat_stok ORDER BY id DESC", conn)
        st.dataframe(df_log, use_container_width=True)
        if not df_log.empty:
            st.download_button("📥 Ekspor Laporan Profit Multi-Unit", data=convert_df_to_csv(df_log), file_name='Laporan_Profit_Pusat.csv', mime='text/csv')
        conn.close()
    except: st.warning("Menunggu sirkulasi data finansial...")

# --- MENU D: GUDANG INDUK (OWNER/ADMIN) ---
elif menu == "📦 Gudang Induk (Pusat Pusat)":
    st.title("📦 Manajemen Brankas Utama Gudang Induk")
    df_b = get_daftar_bahan()
    with st.form("form_pusat"):
        cc1, cc2, cc3 = st.columns(3)
        with cc1: nama = st.text_input("Nama Komoditas Baru:")
        with cc2: hrg = st.number_input("Nominal Belanja Kulakan (Total Rp):", min_value=0)
        with cc3: qty = st.number_input("Kuantitas Isi Volume:", min_value=1)
        hrg_int = st.number_input("Rencana Harga Jual Internal ke Dapur Cabang (Rp / Satuan):", min_value=0)
        sat = st.text_input("Satuan Ukuran (Contoh: gram, pcs, ml):")
        if st.form_submit_button("💾 Kunci Masuk Gudang Induk"):
            if nama:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("INSERT INTO bahan_baku (nama_bahan, harga_beli, jumlah_isi, satuan, harga_satuan, stok_gudang, harga_jual_internal) VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (nama_bahan) DO UPDATE SET stok_gudang = bahan_baku.stok_gudang + EXCLUDED.stok_gudang, harga_jual_internal=EXCLUDED.harga_jual_internal", (nama, hrg, qty, sat, hrg/qty, qty, hrg_int))
                conn.commit()
                conn.close()
                st.success("✅ Item masuk ke aset Gudang Induk!")
                time.sleep(1.5)
                st.rerun()
    st.write("---")
    st.subheader("Data Riwayat Stok Lintas Cabang")
    st.dataframe(df_b, use_container_width=True)

# --- MENU E: TRANSFER LOGISTIK (OWNER/ADMIN) ---
elif menu == "🚚 Transfer Logistik ke Cabang":
    st.title("🚚 Alokasi Barang Distribusi Internal")
    df_g = get_daftar_bahan()
    if df_g.empty: st.warning("Stok Gudang Induk kosong.")
    else:
        c1, c2, c3 = st.columns(3)
        with c1: brg = st.selectbox("Pilih Material:", df_g['nama_bahan'].tolist())
        with c2: qty = st.number_input("Banyaknya Kuantitas:", min_value=1)
        with c3: tuj = st.radio("Kirim Ke Cabang Mana?", ["Cafe", "Taman"])
        if st.button("🚀 Eksekusi Pengiriman", type="primary", use_container_width=True):
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE bahan_baku SET stok_gudang = stok_gudang - %s WHERE nama_bahan = %s", (qty, brg))
            if tuj == "Cafe": cursor.execute("UPDATE bahan_baku SET stok_cafe = COALESCE(stok_cafe, 0) + %s WHERE nama_bahan = %s", (qty, brg))
            elif tuj == "Taman": cursor.execute("UPDATE bahan_baku SET stok_taman = COALESCE(stok_taman, 0) + %s WHERE nama_bahan = %s", (qty, brg))
            conn.commit()
            conn.close()
            st.success("✅ Logistik bergeser, stok cabang bertambah!")
            time.sleep(1.5)
            st.rerun()

# --- MENU F: LAPORAN AKHIR & HARGA JUAL (OWNER/ADMIN) ---
elif menu == "📂 Laporan Akhir & Harga Jual":
    st.title("📂 Manajemen Dokumen Penjualan & Penetapan Laba")
    conn = get_connection()
    df_r = pd.read_sql_query("SELECT id, nama_resep as \"Menu/Paket\", total_hpp_final as \"HPP Dasar (Rp)\", harga_jual as \"Harga Jual Konsumen (Rp)\" FROM resep", conn)
    if df_r.empty: st.info("Belum ada resep terdokumentasi.")
    else:
        edited = st.data_editor(df_r, use_container_width=True, disabled=["id", "Menu/Paket", "HPP Dasar (Rp)"])
        if st.button("💾 Simpan Penyesuaian Harga Pasar", type="primary"):
            cursor = conn.cursor()
            for _, r in edited.iterrows():
                cursor.execute("UPDATE resep SET harga_jual=%s WHERE id=%s", (float(r['Harga Jual Konsumen (Rp)']), int(r['id'])))
            conn.commit()
            st.success("✅ Sinkronisasi harga jual baru berhasil!")
            time.sleep(1.5)
            st.rerun()
    conn.close()

# --- MENU G: MANAJEMEN USER (KHUSUS OWNER) ---
elif menu == "👥 Manajemen Otoritas User":
    st.title("👥 Pengaturan Hak Akses Karyawan")
    conn = get_connection()
    df_users = pd.read_sql_query("SELECT username as \"ID User\", role as \"Tingkat Akses\" FROM users", conn)
    col1, col2 = st.columns([2, 1])
    with col1:
        st.dataframe(df_users, use_container_width=True)
        hapus_user = st.selectbox("Hapus Akses Staf:", df_users['ID User'].tolist())
        if st.button("Hapus Akun Karyawan", type="primary"):
            if hapus_user == "owner": st.error("Akses Owner Mutlak tidak boleh dihapus!")
            else:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM users WHERE username=%s", (hapus_user,))
                conn.commit()
                st.success("✅ Akses dicabut!")
                time.sleep(1.5)
                st.rerun()
    with col2:
        with st.form("tambah_staf"):
            new_u = st.text_input("Username Baru:")
            new_p = st.text_input("Password Rahasia:", type="password")
            new_r = st.selectbox("Posisi Divisi:", ["Gudang Kios", "Karyawan", "Admin", "Owner"])
            if st.form_submit_button("💾 Daftarkan Karyawan"):
                if new_u and new_p:
                    cursor = conn.cursor()
                    try:
                        cursor.execute("INSERT INTO users VALUES (%s, %s, %s)", (new_u.strip().lower(), new_p, new_r))
                        conn.commit()
                        st.success("✅ Akun karyawan aktif!")
                        time.sleep(1.5)
                        st.rerun()
                    except: st.error("ID tersebut sudah terdaftar!")
    conn.close()
