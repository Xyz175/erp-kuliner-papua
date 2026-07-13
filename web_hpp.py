import streamlit as st
import pandas as pd
import psycopg2
import time
from datetime import datetime

# ==========================================
# 1. PENGATURAN HALAMAN & KONEKSI SUPABASE
# ==========================================
st.set_page_config(page_title="ERP Cloud V6 (Cafe & Paket Menu)", layout="wide", page_icon="🍽️")

SUPABASE_URI = "postgresql://postgres.jskxygpvnbjgjjgsvwqf:ZeeyStore175@aws-0-ap-southeast-2.pooler.supabase.com:6543/postgres"

def get_connection():
    return psycopg2.connect(SUPABASE_URI)

def init_db():
    conn = get_connection()
    conn.autocommit = True 
    cursor = conn.cursor()
    
    # 1. Tabel Users
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT,
            role TEXT
        )
    """)
    cursor.execute("INSERT INTO users (username, password, role) VALUES ('owner', 'owner123', 'Owner') ON CONFLICT DO NOTHING")
    
    # 2. Tabel Bahan Baku
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bahan_baku (
            nama_bahan TEXT PRIMARY KEY,
            harga_beli REAL, jumlah_isi REAL, satuan TEXT, harga_satuan REAL,
            stok_gudang REAL DEFAULT 0, stok_cafe REAL DEFAULT 0, 
            stok_kios REAL DEFAULT 0, stok_taman REAL DEFAULT 0,
            harga_jual_internal REAL DEFAULT 0
        )
    """)
    
    # 3. Tabel Resep / Menu / Paket
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS resep (
            id SERIAL PRIMARY KEY, nama_resep TEXT UNIQUE,
            total_hpp_bahan REAL, total_operasional REAL, total_hpp_final REAL,
            harga_jual REAL DEFAULT 0, tanggal_dibuat TEXT
        )
    """)
    
    # 4. Tabel Detail Resep
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS detail_resep (
            id SERIAL PRIMARY KEY, resep_id INTEGER, nama_bahan TEXT,
            jumlah_pakai REAL, satuan TEXT, subtotal_biaya REAL
        )
    """)
    
    # 5. Tabel Riwayat Stok
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS riwayat_stok (
            id SERIAL PRIMARY KEY, tanggal TEXT, nama_bahan TEXT,
            jenis_transaksi TEXT, jumlah REAL, keterangan TEXT,
            kerugian_rp REAL DEFAULT 0, laba_internal REAL DEFAULT 0,
            dari_gudang TEXT, ke_unit TEXT
        )
    """)
    
    cursor.close()
    conn.close()

try: init_db()
except Exception as e: st.error(f"⚠️ Gagal inisialisasi database! Eror: {e}")

# Inisialisasi Session State untuk Draf Kerja Dapur & Paket
if 'racikan_sementara' not in st.session_state:
    st.session_state.racikan_sementara = pd.DataFrame(columns=["Nama Bahan", "Jumlah Pakai", "Satuan", "Subtotal"])
if 'paket_sementara' not in st.session_state:
    st.session_state.paket_sementara = pd.DataFrame(columns=["Nama Menu", "Jumlah Porsi", "HPP Satuan", "Subtotal HPP"])

# ==========================================
# 2. SISTEM LOGIN & SESSION
# ==========================================
if 'sudah_login' not in st.session_state: st.session_state.sudah_login = False
if 'username' not in st.session_state: st.session_state.username = ""
if 'role' not in st.session_state: st.session_state.role = ""

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
st.sidebar.title("🏢 ERP MULTI-GUDANG V6")
st.sidebar.write(f"👤 User: **{st.session_state.username}**")
st.sidebar.write(f"🛡️ Hak Akses: **{role}**")
if st.sidebar.button("🚪 Keluar / Logout"):
    st.session_state.sudah_login = False
    st.rerun()
st.sidebar.write("---")

# Pengaturan menu berdasarkan Hak Akses
menu_options = ["🍽️ Cafe: HPP & Target Penjualan", "📦 Pembuatan Paket Kelompok"]
if role in ["Owner", "Admin"]:
    menu_options = ["📊 Dashboard Analitik", "📦 Manajemen Gudang Pusat", "🚚 Penjualan ke Unit (Cabang)", "🍽️ Cafe: HPP & Target Penjualan", "📦 Pembuatan Paket Kelompok", "📂 Arsip & Harga Jual"]
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

def get_daftar_menu_tunggal():
    try:
        conn = get_connection()
        # Mengambil resep tunggal (bukan hasil paket kelompok)
        df = pd.read_sql_query("SELECT * FROM resep WHERE nama_resep NOT LIKE '[Paket%%]' ORDER BY nama_resep ASC", conn)
        conn.close()
        return df
    except: return pd.DataFrame()

# ==========================================
# MENU OWNER: MANAJEMEN USER
# ==========================================
if menu == "👥 Manajemen User (Admin/Staf)":
    st.title("👥 Manajemen Akses Karyawan & Admin")
    conn = get_connection()
    df_users = pd.read_sql_query("SELECT username as \"Username\", role as \"Hak Akses\" FROM users", conn)
    
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("📋 Daftar Pengguna")
        st.dataframe(df_users, use_container_width=True)
        hapus_user = st.selectbox("Pilih User untuk dihapus:", df_users['Username'].tolist())
        if st.button("Hapus Akun", type="primary"):
            if hapus_user == "owner": st.error("Owner utama tidak bisa dihapus!")
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
            new_r = st.selectbox("Role", ["Karyawan", "Admin", "Owner"])
            if st.form_submit_button("Simpan"):
                if new_u and new_p:
                    cursor = conn.cursor()
                    try:
                        cursor.execute("INSERT INTO users VALUES (%s, %s, %s)", (new_u.strip().lower(), new_p, new_r))
                        conn.commit()
                        st.success("Berhasil dibuat!")
                        time.sleep(1.5)
                        st.rerun()
                    except: st.error("Username sudah terpakai!")
    conn.close()

# ==========================================
# MENU: CAFE (HPP & TARGET PENJUALAN)
# ==========================================
elif menu == "🍽️ Cafe: HPP & Target Penjualan":
    st.title("🍽️ Pengelolaan HPP Dapur Cafe & Perencanaan Target")
    
    tab_hitung, tab_simulasi = st.tabs(["🍳 1. Hitung HPP Menu Tunggal", "📈 2. Perencanaan Target Penjualan"])
    
    with tab_hitung:
        st.subheader("Form Racik Menu Tunggal Cafe")
        st.write("Catat HPP barang kulakan yang telah dibeli dari Gudang Induk untuk dijadikan menu Cafe.")
        
        df_b = get_daftar_bahan()
        if df_b.empty: st.warning("Bahan baku kosong di gudang.")
        else:
            c1, c2, c3 = st.columns([2, 1, 1])
            with c1:
                cari = st.text_input("🔍 Cari bahan baku di rak Cafe:")
                df_f = df_b[df_b['nama_bahan'].str.lower().str.contains(cari.lower())] if cari else df_b
                pilih_b = st.selectbox("Pilih Bahan Baku:", df_f['nama_bahan'].tolist() if not df_f.empty else ["Kosong"])
            with c2:
                qty = st.number_input("Jumlah yang digunakan:", min_value=0.0, step=1.0)
            with c3:
                st.write("")
                st.write("")
                if st.button("➕ Masukkan ke Draf Menu"):
                    if pilih_b != "Kosong" and qty > 0:
                        row = df_b[df_b['nama_bahan'] == pilih_b].iloc[0]
                        # Gunakan harga jual internal dari gudang induk sebagai modal dapur cafe
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
            else: tot_bahan = 0.0
            
            st.subheader("⚡ Komponen Biaya Operasional Pembuatan")
            co1, co2 = st.columns(2)
            with co1: waktu = st.number_input("Waktu Pembuatan (Menit):", min_value=0.0, step=5.0)
            with co2: gas = st.number_input("Penggunaan Gas LPG (Kg):", min_value=0.0, format="%.3f")
            
            biaya_ops = ((10000/60)*waktu) + ((3000/60)*waktu) + (gas * 18000)
            tot_final = tot_bahan + biaya_ops
            
            st.info(f"📊 **Kalkulasi HPP Akhir Menu:** Modal Bahan: Rp {tot_bahan:,.0f} | Operasional: Rp {biaya_ops:,.0f} | **TOTAL HPP: Rp {tot_final:,.2f}**")
            
            cc1, cc2 = st.columns(2)
            with cc1: nama_menu = st.text_input("Nama Menu Tunggal Cafe Baru:")
            with cc2:
                st.write("")
                st.write("")
                if st.button("✅ Kunci & Simpan Menu Cafe", type="primary", use_container_width=True):
                    if nama_menu and not st.session_state.racikan_sementara.empty:
                        conn = get_connection()
                        cursor = conn.cursor()
                        tgl = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
                        cursor.execute("INSERT INTO resep (nama_resep, total_hpp_bahan, total_operasional, total_hpp_final, tanggal_dibuat) VALUES (%s,%s,%s,%s,%s) ON CONFLICT (nama_resep) DO UPDATE SET total_hpp_final=EXCLUDED.total_hpp_final", (nama_menu.strip(), tot_bahan, biaya_ops, tot_final, tgl))
                        cursor.execute("SELECT id FROM resep WHERE nama_resep=%s", (nama_menu.strip(),))
                        r_id = cursor.fetchone()[0]
                        cursor.execute("DELETE FROM detail_resep WHERE resep_id=%s", (r_id,))
                        
                        for _, r in st.session_state.racikan_sementara.iterrows():
                            cursor.execute("INSERT INTO detail_resep (resep_id, nama_bahan, jumlah_pakai, satuan, subtotal_biaya) VALUES (%s,%s,%s,%s,%s)", (r_id, r['Nama Bahan'], r['Jumlah Pakai'], r['Satuan'], r['Subtotal']))
                            # Potong stok khusus Gudang Cafe
                            cursor.execute("UPDATE bahan_baku SET stok_cafe = COALESCE(stok_cafe,0) - %s WHERE nama_bahan = %s", (r['Jumlah Pakai'], r['Nama Bahan']))
                        
                        conn.commit()
                        conn.close()
                        st.success("✅ Sukses! Menu tunggal Cafe berhasil disimpan dan stok gudang Cafe terpotong.")
                        time.sleep(1.5)
                        st.session_state.racikan_sementara = pd.DataFrame(columns=["Nama Bahan", "Jumlah Pakai", "Satuan", "Subtotal"])
                        st.rerun()

    with tab_simulasi:
        st.subheader("📈 Perencanaan Keuangan & Target Penjualan Cafe")
        st.write("Masukkan target porsi penjualan untuk melihat proyeksi modal berputar, laba kotor, dan laba bersih Cafe Anda.")
        
        df_m = get_daftar_menu_tunggal()
        if df_m.empty: st.warning("Belum ada menu tunggal kuliner yang terdaftar.")
        else:
            sim_menu = st.selectbox("Pilih Menu untuk Disimulasikan:", df_m['Nama Menu/Resep'].tolist() if 'Nama Menu/Resep' in df_m.columns else df_m['nama_resep'].tolist())
            
            # Ambil data HPP dasar menu terpilih
            row_m = df_m[df_m['nama_resep'] == sim_menu].iloc[0]
            hpp_satuan = float(row_m['total_hpp_final'])
            
            cs1, cs2 = st.columns(2)
            with cs1: target_porsi = st.number_input("Target Penjualan Hari/Bulan Ini (Porsi):", min_value=1, value=50)
            with cs2: harga_jual_porsi = st.number_input("Rencana Harga Jual per Porsi (Rp):", min_value=0, value=int(row_m['harga_jual']) if row_m['harga_jual'] > 0 else int(hpp_satuan * 1.5))
            
            # Perhitungan Proyeksi
            total_modal_butuh = hpp_satuan * target_porsi
            total_omset_target = harga_jual_porsi * target_porsi
            proyeksi_laba_bersih = total_omset_target - total_modal_butuh
            margin_persen = (proyeksi_laba_bersih / total_omset_target * 100) if total_omset_target > 0 else 0.0
            
            st.write("---")
            st.subheader("📊 Hasil Analisis Perencanaan Finansial")
            cx1, cx2, cx3 = st.columns(3)
            cx1.metric("💰 Total Modal yang Harus Siap", f"Rp {total_modal_butuh:,.2f}", "Uang Berputar Stok")
            cx2.metric("📈 Estimasi Pendapatan Kotor", f"Rp {total_omset_target:,.0f}")
            cx3.metric("✅ Estimasi Keuntungan Bersih", f"Rp {proyeksi_laba_bersih:,.2f}", f"{margin_persen:.1f}% Margin")

# ==========================================
# MENU: PEMBUATAN PAKET KELOMPOK
# ==========================================
elif menu == "📦 Pembuatan Paket Kelompok":
    st.title("📦 Pembuatan & Perhitungan HPP Paket Menu Kelompok")
    st.write("Satukan beberapa menu tunggal Cafe menjadi paket bundling khusus untuk porsi kelompok besar.")
    
    tipe_paket = st.radio("Pilih Kategori Jumlah Orang Paket:", ["Paket 1-3 Orang", "Paket 1-5 Orang", "Paket 1-7 Orang"], horizontal=True)
    
    df_menu_ada = get_daftar_menu_tunggal()
    if df_menu_ada.empty:
        st.warning("Silakan buat menu tunggal terlebih dahulu di menu Cafe sebelum membuat paket gabungan.")
    else:
        st.subheader("⚡ Langkah 1: Masukkan Komponen Menu Tunggal ke Dalam Paket")
        cp1, cp2, cp3 = st.columns([2, 1, 1])
        with cp1:
            menu_pilihan = st.selectbox("Pilih Menu Tunggal:", df_menu_ada['nama_resep'].tolist())
        with cp2:
            jumlah_porsi_menu = st.number_input("Berapa Porsi menu ini di dalam paket?", min_value=1, value=3)
        with cp3:
            st.write("")
            st.write("")
            if st.button("➕ Masukkan ke Paket"):
                row_selected = df_menu_ada[df_menu_ada['nama_resep'] == menu_pilihan].iloc[0]
                hpp_sat = float(row_selected['total_hpp_final'])
                sub_hpp = jumlah_porsi_menu * hpp_sat
                
                df_pkt = st.session_state.paket_sementara
                if menu_pilihan in df_pkt['Nama Menu'].values:
                    df_pkt.loc[df_pkt['Nama Menu'] == menu_pilihan, ["Jumlah Porsi", "Subtotal HPP"]] = [jumlah_porsi_menu, sub_hpp]
                else:
                    tambah_pkt = pd.DataFrame([[menu_pilihan, jumlah_porsi_menu, hpp_sat, sub_hpp]], columns=df_pkt.columns)
                    st.session_state.paket_sementara = pd.concat([df_pkt, tambah_pkt], ignore_index=True)
                st.rerun()
                
        st.write("---")
        st.subheader("📋 Isi Draf Komponen Paket Menu Kelompok")
        if not st.session_state.paket_sementara.empty:
            st.session_state.paket_sementara = st.data_editor(st.session_state.paket_sementara, use_container_width=True)
            total_hpp_paket_dasar = st.session_state.paket_sementara['Subtotal HPP'].sum()
        else:
            st.info("Paket masih kosong. Tambahkan komponen menu di atas.")
            total_hpp_paket_dasar = 0.0
            
        st.write("---")
        st.subheader("⚡ Langkah 2: Biaya Kemasan Khusus Paket & Konfirmasi Harga")
        c_pck1, c_pck2 = st.columns(2)
        with c_pck1:
            biaya_kotak_paket = st.number_input("Biaya Box Kemasan Besar / Sterofoam Paket (Rp):", min_value=0, value=5000)
        with c_pck2:
            harga_jual_paket = st.number_input("Rencana Harga Jual Paket Kelompok Ini (Rp):", min_value=0, value=int((total_hpp_paket_dasar + biaya_kotak_paket)*1.4))
            
        total_hpp_final_paket = total_hpp_paket_dasar + biaya_kotak_paket
        keuntungan_paket = harga_jual_paket - total_hpp_final_paket
        margin_paket_persen = (keuntungan_paket / harga_jual_paket * 100) if harga_jual_paket > 0 else 0.0
        
        st.info(f"📊 **Ringkasan Finansial Paket:** Total HPP Gabungan: Rp {total_hpp_final_paket:,.2f} | Rencana Jual: Rp {harga_jual_paket:,.0f} | **Estimasi Laba Bersih Paket: Rp {keuntungan_paket:,.2f} ({margin_paket_persen:.1f}%)**")
        
        st.write("---")
        st.subheader("💾 Langkah 3: Beri Nama & Kunci Paket ke Database Cloud")
        ck1, ck2 = st.columns(2)
        with ck1:
            nama_paket_kombinasi = st.text_input("Nama Kreatif Paket Kelompok:", placeholder="Contoh: Paket Etnik Premium Keluarga")
        with ck2:
            st.write("")
            st.write("")
            if st.button("💾 Kunci & Simpan Paket Kelompok", type="primary", use_container_width=True):
                if nama_paket_kombinasi and not st.session_state.paket_sementara.empty:
                    # Penamaan otomatis dengan tag kategori porsi orang agar kasir mudah membacanya
                    nama_paket_lengkap = f"[{tipe_paket}] {nama_paket_kombinasi.strip()}"
                    tgl_sekarang = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    conn = get_connection()
                    cursor = conn.cursor()
                    
                    # Simpan informasi paket ke dalam tabel utama resep
                    cursor.execute("""
                        INSERT INTO resep (nama_resep, total_hpp_bahan, total_operasional, total_hpp_final, harga_jual, tanggal_dibuat)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (nama_resep)
                        DO UPDATE SET total_hpp_final = EXCLUDED.total_hpp_final, harga_jual = EXCLUDED.harga_jual
                    """, (nama_paket_lengkap, total_hpp_paket_dasar, float(biaya_kotak_paket), total_hpp_final_paket, float(harga_jual_paket), tgl_sekarang))
                    
                    cursor.execute("SELECT id FROM resep WHERE nama_resep=%s", (nama_paket_lengkap,))
                    resep_id_paket = cursor.fetchone()[0]
                    cursor.execute("DELETE FROM detail_resep WHERE resep_id=%s", (resep_id_paket,))
                    
                    # Catat komponen menu penyusun paket ke detail_resep
                    for _, row_p in st.session_state.paket_sementara.iterrows():
                        cursor.execute("""
                            INSERT INTO detail_resep (resep_id, nama_bahan, jumlah_pakai, satuan, subtotal_biaya)
                            VALUES (%s, %s, %s, 'porsi', %s)
                        """, (resep_id_paket, row_p['Nama Menu'], row_p['Jumlah Porsi'], row_p['Subtotal HPP']))
                        
                    conn.commit()
                    conn.close()
                    
                    st.success(f"✅ Sukses! {nama_paket_lengkap} berhasil dikunci dan terdaftar 24 jam di Cloud.")
                    time.sleep(1.5)
                    st.session_state.paket_sementara = pd.DataFrame(columns=["Nama Menu", "Jumlah Porsi", "HPP Satuan", "Subtotal HPP"])
                    st.rerun()

# ==========================================
# MENUS LAINNYA (DASHBOARD, GUDANG, TRANSFER, ARSIP)
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
        st.metric("Laba Bersih Gudang Induk", f"Rp {total_laba_gudang:,.0f}")
        st.write("---")
        st.dataframe(df_log, use_container_width=True)
    except: st.warning("Menunggu data...")

elif menu == "📦 Manajemen Gudang Pusat":
    st.title("📦 Gudang Induk (Etnik Papua)")
    df_bahan_ada = get_daftar_bahan()
    pilihan_edit = "-- Input Produk Baru --"
    if not df_bahan_ada.empty:
        pilihan_edit = st.selectbox("Pilih barang untuk ditambah/diedit:", ["-- Input Produk Baru --"] + df_bahan_ada['nama_bahan'].tolist())
    
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
    with c2: entry_harga = st.number_input("Harga Beli Kulakan (Rp)", min_value=0.0, value=val_harga)
    with c3: entry_isi = st.number_input("Jumlah Isi", min_value=1.0, value=val_isi)
    with c4: entry_satuan = st.text_input("Satuan", value=val_satuan)
    with c5: entry_jual_int = st.number_input("Harga Jual ke Cabang/Unit (Rp)", min_value=0.0, value=val_jual_internal)
    
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
            st.success(f"✅ Produk berhasil disimpan!")
            time.sleep(1.5)
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
        with col1: bahan_transfer = st.selectbox("Pilih Barang:", df_g['nama_bahan'].tolist())
        data_b = df_g[df_g['nama_bahan'] == bahan_transfer].iloc[0]
        stok_induk = data_b['stok_gudang']
        
        with col2: qty_transfer = st.number_input(f"Berapa banyak? (Sisa Induk: {stok_induk})", min_value=1.0, max_value=float(stok_induk) if stok_induk > 0 else 1.0)
        with col3: unit_tujuan = st.radio("Unit Penerima:", ["Cafe", "Kios", "Taman"])
        
        if st.button(f"🛒 Konfirmasi Transfer ke {unit_tujuan}", type="primary", use_container_width=True):
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
                st.success(f"✅ Sukses mentransfer barang ke {unit_tujuan}!")
                time.sleep(1.5)
                st.rerun()
            else: st.error("Stok Gudang Induk kurang!")

elif menu == "📂 Arsip & Harga Jual":
    st.title("📂 Arsip Dokumen Pengeluaran & Harga Jual")
    try:
        conn = get_connection()
        df_resep = pd.read_sql_query('SELECT id as "ID", nama_resep as "Nama Laporan/Menu/Paket", total_hpp_final as "HPP Total (Rp)", harga_jual as "Harga Jual (Rp)", tanggal_dibuat as "Tanggal Kunci" FROM resep', conn)
        if df_resep.empty: st.info("Arsip masih kosong.")
        else:
            st.subheader("Atur Harga Jual Menu & Paket")
            edited = st.data_editor(df_resep, use_container_width=True, disabled=["ID", "Nama Laporan/Menu/Paket", "HPP Total (Rp)", "Tanggal Kunci"])
            if st.button("💾 Simpan Perubahan Finansial"):
                cursor = conn.cursor()
                for _, r in edited.iterrows():
                    cursor.execute("UPDATE resep SET harga_jual=%s WHERE id=%s", (float(r['Harga Jual (Rp)']), int(r['ID'])))
                conn.commit()
                st.success("✅ Sukses Memperbarui Finansial!")
                time.sleep(1.5)
                st.rerun()
                
            st.write("---")
            pilih_r = st.selectbox("Pilih Arsip Menu/Paket untuk Dihapus:", df_resep['Nama Laporan/Menu/Paket'].tolist())
            if st.button("🗑️ Hapus Dokumen Permanen", type="primary"):
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM resep WHERE nama_resep=%s", (pilih_r,))
                r_id = cursor.fetchone()[0]
                cursor.execute("DELETE FROM detail_resep WHERE resep_id=%s", (r_id,))
                cursor.execute("DELETE FROM resep WHERE id=%s", (r_id,))
                conn.commit()
                st.success("✅ Dokumen berhasil dihapus!")
                time.sleep(1.5)
                st.rerun()
        conn.close()
    except: st.error("Gagal memuat arsip.")
