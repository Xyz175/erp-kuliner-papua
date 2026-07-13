import streamlit as st
import pandas as pd
import psycopg2
import matplotlib.pyplot as plt
from datetime import datetime

# ==========================================
# 1. PENGATURAN HALAMAN & KONEKSI SUPABASE
# ==========================================
st.set_page_config(page_title="Sistem ERP Kuliner Cloud", layout="wide", page_icon="🍳")

# --- SISTEM LOGIN ---
if 'sudah_login' not in st.session_state:
    st.session_state.sudah_login = False

if not st.session_state.sudah_login:
    st.title("🔒 Sistem ERP Terkunci")
    st.write("Silakan masukkan Username dan Password Anda.")
    
    # Anda bisa mengganti "admin" dan "papua123" dengan kata sandi rahasia Anda sendiri
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    
    if st.button("Masuk / Login"):
        if username == "admin" and password == "papua123":
            st.session_state.sudah_login = True
            st.rerun()
        else:
            st.error("❌ Username atau Password salah!")
    st.stop() # Kode ini mencegah isi website di bawahnya dimuat sebelum login berhasil
# --- BATAS LOGIN ---

# KONEKSI DATABASE CLOUD (SUDAH BERHASIL TEMBUS!)
SUPABASE_URI = "postgresql://postgres.jskxygpvnbjgjjgsvwqf:ZeeyStore175@..."
# ... (lanjutan kode Anda ke bawah biarkan saja apa adanya)
# KONEKSI DATABASE CLOUD (SUDAH BERHASIL TEMBUS!)
SUPABASE_URI = "postgresql://postgres.jskxygpvnbjgjjgsvwqf:ZeeyStore175@aws-0-ap-southeast-2.pooler.supabase.com:6543/postgres"

def get_connection():
    return psycopg2.connect(SUPABASE_URI)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bahan_baku (
            nama_bahan TEXT PRIMARY KEY,
            harga_beli REAL,
            jumlah_isi REAL,
            satuan TEXT,
            harga_satuan REAL,
            stok_gudang REAL DEFAULT 0
        )
    """)
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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS riwayat_stok (
            id SERIAL PRIMARY KEY,
            tanggal TEXT,
            nama_bahan TEXT,
            jenis_transaksi TEXT,
            jumlah REAL,
            keterangan TEXT,
            kerugian_rp REAL DEFAULT 0
        )
    """)
    conn.commit()
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
# 2. MENU NAVIGASI (SIDEBAR)
# ==========================================
st.sidebar.title("🍳 ERP CLOUD SINKRON")
st.sidebar.write("---")
menu = st.sidebar.radio("Navigasi Sistem:", 
    ["📊 Dashboard & Grafik Analitik", "📦 Gudang & Stok Opname", "🍳 Racik Resep & Operasional", "📂 Arsip & Proyeksi Menu"]
)

def get_daftar_bahan():
    try:
        conn = get_connection()
        df = pd.read_sql_query("SELECT * FROM bahan_baku", conn)
        conn.close()
        return df
    except:
        return pd.DataFrame()

def bersihkan_angka(val):
    if pd.isna(val) or str(val).strip() == "": return 0.0
    val_str = str(val).lower().replace("rp", "").replace(" ", "").replace(",", "")
    try: return float(val_str)
    except ValueError: return 0.0

# ==========================================
# 3. TAB: DASHBOARD & GRAFIK ANALITIK
# ==========================================
if menu == "📊 Dashboard & Grafik Analitik":
    st.title("📊 Dashboard Analitik Cloud (Real-time)")
    st.write("Data ini tersinkronisasi otomatis. Anda bisa menginput dari laptop, dan memantau grafiknya dari HP secara live!")
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM resep")
        total_resep = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT SUM(kerugian_rp) FROM riwayat_stok WHERE jenis_transaksi='Barang Hilang/Rugi'")
        total_rugi_gudang = cursor.fetchone()[0] or 0.0
        
        cursor.execute("SELECT SUM(harga_jual) FROM resep")
        total_omset_proyeksi = cursor.fetchone()[0] or 0.0
        
        cursor.execute("SELECT SUM(total_hpp_final) FROM resep")
        total_hpp_proyeksi = cursor.fetchone()[0] or 0.0
        
        # PERBAIKAN TANDA KUTIP UNTUK POSTGRESQL DI SINI
        df_log = pd.read_sql_query('SELECT tanggal as "Tanggal", nama_bahan as "Nama Bahan", jumlah as "Jumlah Hilang", keterangan as "Alasan/Keterangan", kerugian_rp as "Kerugian (Rp)" FROM riwayat_stok WHERE jenis_transaksi=\'Barang Hilang/Rugi\' ORDER BY id DESC', conn)
        conn.close()
        
        laba_bersih_proyeksi = total_omset_proyeksi - total_hpp_proyeksi
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Menu Aktif", f"{total_resep} Resep")
        c2.metric("Proyeksi Omset Penjualan", f"Rp {total_omset_proyeksi:,.0f}")
        c3.metric("Proyeksi Laba Bersih", f"Rp {laba_bersih_proyeksi:,.0f}", delta=f"Margin {((laba_bersih_proyeksi/total_omset_proyeksi)*100 if total_omset_proyeksi > 0 else 0):.1f}%")
        c4.metric("Kerugian Barang Hilang", f"Rp {total_rugi_gudang:,.0f}", delta=f"-Rp {total_rugi_gudang:,.0f}", delta_color="inverse")
        
        st.write("---")
        col_g1, col_g2 = st.columns(2)
        
        with col_g1:
            st.subheader("📈 Struktur Perbandingan Keuangan Total")
            if total_omset_proyeksi > 0:
                fig, ax = plt.subplots(figsize=(6, 4))
                kategori = ['Total HPP', 'Proyeksi Laba', 'Kerugian Gudang']
                nilai = [total_hpp_proyeksi, max(0, laba_bersih_proyeksi), total_rugi_gudang]
                ax.bar(kategori, nilai, color=['#ff6b6b', '#51cf66', '#fcc419'])
                ax.set_ylabel("Rupiah (Rp)")
                st.pyplot(fig)
            else:
                st.info("Grafik perbandingan modal akan muncul setelah Anda mengisi Harga Jual di Arsip Menu.")
                
        with col_g2:
            st.subheader("📜 Catatan Aktivitas Kehilangan Barang")
            st.dataframe(df_log, use_container_width=True)
    except Exception as e:
        st.warning(f"Menunggu sinkronisasi data perdana... ({e})")

# ==========================================
# 4. TAB: GUDANG & STOK OPNAME
# ==========================================
elif menu == "📦 Gudang & Stok Opname":
    st.title("📦 Manajemen Gudang Cloud (Real-time)")
    
    t1, t2, t3 = st.tabs(["➕ Tambah/Edit Bahan Baku", "🔍 Stok Opname (Cari Barang Hilang)", "🗑️ Reset Data Gudang"])
    
    with t1:
        df_bahan_ada = get_daftar_bahan()
        pilihan_edit = "-- Tambah Bahan Baru --"
        if not df_bahan_ada.empty:
            pilihan_edit = st.selectbox("💡 Pilih bahan untuk edit (atau biarkan kosong untuk tambah baru):", ["-- Tambah Bahan Baru --"] + df_bahan_ada['nama_bahan'].tolist())
        
        val_nama, val_harga, val_isi, val_satuan = "", 0.0, 1.0, "gr"
        if pilihan_edit != "-- Tambah Bahan Baru --":
            row_edit = df_bahan_ada[df_bahan_ada['nama_bahan'] == pilihan_edit].iloc[0]
            val_nama = row_edit['nama_bahan']
            val_harga = float(row_edit['harga_beli'])
            val_isi = float(row_edit['jumlah_isi'])
            val_satuan = row_edit['satuan']
            
        col1, col2, col3, col4 = st.columns(4)
        with col1: entry_nama = st.text_input("Nama Bahan Baku (ex: Air Galon)", value=val_nama)
        with col2: entry_harga = st.number_input("Harga Beli Total (Rp)", min_value=0.0, step=1000.0, value=val_harga)
        with col3: entry_isi = st.number_input("Satuan Isi/Volume (ex: 19000)", min_value=1.0, step=1.0, value=val_isi)
        with col4: entry_satuan = st.text_input("Teks Satuan (gr / ml / pcs)", value=val_satuan)
        
        col_btn1, col_btn2 = st.columns([3, 1])
        with col_btn1:
            if st.button("💾 Simpan / Perbarui Bahan Baku ke Cloud", use_container_width=True):
                if entry_nama and entry_satuan:
                    h_satuan = entry_harga / entry_isi
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute("SELECT stok_gudang FROM bahan_baku WHERE nama_bahan=%s", (entry_nama,))
                    stok_lama = cursor.fetchone()
                    stok_sekarang = stok_lama[0] if stok_lama else entry_isi
                    
                    cursor.execute("""
                        INSERT INTO bahan_baku (nama_bahan, harga_beli, jumlah_isi, satuan, harga_satuan, stok_gudang) 
                        VALUES (%s, %s, %s, %s, %s, %s) 
                        ON CONFLICT (nama_bahan) 
                        DO UPDATE SET harga_beli=EXCLUDED.harga_beli, jumlah_isi=EXCLUDED.jumlah_isi, 
                        satuan=EXCLUDED.satuan, harga_satuan=EXCLUDED.harga_satuan, stok_gudang=EXCLUDED.stok_gudang
                    """, (entry_nama.strip(), entry_harga, entry_isi, entry_satuan.strip(), h_satuan, stok_sekarang))
                    conn.commit()
                    cursor.close()
                    conn.close()
                    st.success(f"Berhasil tersimpan di Cloud: {entry_nama}")
                    st.rerun()
        with col_btn2:
            if pilihan_edit != "-- Tambah Bahan Baru --":
                if st.button("🗑️ Hapus Bahan Ini", use_container_width=True, type="primary"):
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM bahan_baku WHERE nama_bahan=%s", (pilihan_edit,))
                    conn.commit()
                    conn.close()
                    st.rerun()
                    
        st.write("---")
        file_upload = st.file_uploader("Upload File Excel Bahan Baku untuk Impor Massal", type=["xlsx", "xls"])
        if file_upload:
            try:
                df_ex = pd.read_excel(file_upload)
                conn = get_connection()
                cursor = conn.cursor()
                for _, r in df_ex.dropna(subset=['Nama Bahan Baku']).iterrows():
                    n = str(r['Nama Bahan Baku']).strip()
                    h = bersihkan_angka(r['Harga Beli'])
                    j = bersihkan_angka(r['Jumlah Isi'])
                    s = str(r['Satuan']).strip()
                    j = 1.0 if j <= 0 else j
                    cursor.execute("""
                        INSERT INTO bahan_baku (nama_bahan, harga_beli, jumlah_isi, satuan, harga_satuan, stok_gudang) 
                        VALUES (%s, %s, %s, %s, %s, %s) 
                        ON CONFLICT (nama_bahan) 
                        DO UPDATE SET harga_beli=EXCLUDED.harga_beli, jumlah_isi=EXCLUDED.jumlah_isi, 
                        satuan=EXCLUDED.satuan, harga_satuan=EXCLUDED.harga_satuan
                    """, (n, h, j, s, h/j, j))
                conn.commit()
                conn.close()
                st.success("Sukses sinkronisasi massal dari Excel ke Cloud!")
                st.rerun()
            except Exception as e: st.error(f"Format salah! {e}")

    with t2:
        st.subheader("🔍 Audit Fisik Gudang (Deteksi Barang Hilang)")
        df_gudang = get_daftar_bahan()
        if df_gudang.empty:
            st.info("Belum ada barang di gudang cloud.")
        else:
            col_au1, col_au2, col_au3 = st.columns(3)
            with col_au1: bahan_audit = st.selectbox("Pilih Barang Gudang:", df_gudang['nama_bahan'].tolist())
            with col_au2: stok_riil_fisik = st.number_input("Jumlah Riil Fisik di Dapur:", min_value=0.0, step=1.0)
            with col_au3: ket_audit = st.text_input("Keterangan/Alasan")
            
            if st.button("🚨 Konfirmasi Hasil Audit Stok Opname", use_container_width=True):
                data_b = df_gudang[df_gudang['nama_bahan'] == bahan_audit].iloc[0]
                stok_sistem = data_b['stok_gudang']
                harga_sat = data_b['harga_satuan']
                
                if stok_riil_fisik < stok_sistem:
                    selisih_hilang = stok_sistem - stok_riil_fisik
                    kerugian = selisih_hilang * harga_sat
                    tgl_skrg = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute("UPDATE bahan_baku SET stok_gudang=%s WHERE nama_bahan=%s", (stok_riil_fisik, bahan_audit))
                    cursor.execute("INSERT INTO riwayat_stok (tanggal, nama_bahan, jenis_transaksi, jumlah, keterangan, kerugian_rp) VALUES (%s,%s,%s,%s,%s,%s)",
                                   (tgl_skrg, bahan_audit, 'Barang Hilang/Rugi', selisih_hilang, ket_audit, kerugian))
                    conn.commit()
                    conn.close()
                    st.warning(f"Audit Cloud Selesai! Kerugian tercatat: Rp {kerugian:,.2f}")
                    st.rerun()
                else:
                    st.success("Stok aman, tidak ada barang hilang yang terdeteksi.")

    with t3:
        if st.button("⚠️ HAPUS TOTAL DATA CLOUD (BAHAN BAKU & RIWAYAT)", type="primary", use_container_width=True):
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("TRUNCATE TABLE bahan_baku CASCADE")
            cursor.execute("TRUNCATE TABLE riwayat_stok CASCADE")
            conn.commit()
            conn.close()
            st.rerun()

    st.write("---")
    st.subheader("📋 Status Terkini Inventaris Gudang Cloud")
    df_tampil = get_daftar_bahan()
    if not df_tampil.empty:
        df_tampil.columns = ['Nama Bahan Baku', 'Harga Beli Master (Rp)', 'Kapasitas Isi', 'Satuan', 'Harga Pokok Satuan (Rp)', 'Sisa Stok Aktif']
        st.dataframe(df_tampil, use_container_width=True)

# ==========================================
# 5. TAB: RACIK RESEP & OPERASIONAL
# ==========================================
elif menu == "🍳 Racik Resep & Operasional":
    st.title("🍳 Ruang Kerja Meracik Resep Menu Cloud")
    
    df_b = get_daftar_bahan()
    if df_b.empty:
        st.warning("⚠️ Silakan isi data Bahan Baku di menu Gudang terlebih dahulu!")
    else:
        st.subheader("1. Tambahkan Bahan ke Komponen Menu")
        col_c1, col_c2, col_c3 = st.columns([2, 1, 1])
        with col_c1:
            kata_kunci = st.text_input("🔍 Ketik di sini untuk mencari nama bahan baku:")
            filtered_bahan = df_b[df_b['nama_bahan'].str.lower().str.contains(kata_kunci.lower())] if kata_kunci else df_b
            pilih_b = st.selectbox("Pilih dari Hasil Pencarian Bahan:", filtered_bahan['nama_bahan'].tolist() if not filtered_bahan.empty else ["Tidak ditemukan"])
        
        with col_c2:
            satuan_label = f"Jumlah Pakai ({df_b[df_b['nama_bahan']==pilih_b].iloc[0]['satuan']}):" if (pilih_b != "Tidak ditemukan" and not filtered_bahan.empty) else "Jumlah"
            j_pakai = st.number_input(satuan_label, min_value=0.0, step=1.0)
            
        with col_c3:
            st.write("")
            st.write("")
            if st.button("➕ Masukkan ke Resep", use_container_width=True):
                if pilih_b != "Tidak ditemukan" and j_pakai > 0:
                    data_row = df_b[df_b['nama_bahan'] == pilih_b].iloc[0]
                    h_sat = data_row['harga_satuan']
                    sat_txt = data_row['satuan']
                    sub = j_pakai * h_sat
                    
                    df_skrg = st.session_state.racikan_sementara
                    if pilih_b in df_skrg['Nama Bahan'].values:
                        df_skrg.loc[df_skrg['Nama Bahan'] == pilih_b, ["Jumlah Pakai", "Subtotal"]] = [j_pakai, sub]
                    else:
                        tambah_row = pd.DataFrame([[pilih_b, j_pakai, sat_txt, sub]], columns=df_skrg.columns)
                        st.session_state.racikan_sementara = pd.concat([df_skrg, tambah_row], ignore_index=True)
                    st.rerun()

        st.write("---")
        st.subheader("🛒 Draf Racikan Resep Saat Ini")
        if not st.session_state.racikan_sementara.empty:
            edited_df = st.data_editor(st.session_state.racikan_sementara, use_container_width=True, num_rows="dynamic")
            st.session_state.racikan_sementara = edited_df
            tot_bahan = st.session_state.racikan_sementara['Subtotal'].sum()
        else:
            st.info("Draf racikan resep masih kosong.")
            tot_bahan = 0.0

        st.write("---")
        st.subheader("⚡ 2. Komponen Biaya Operasional Pembuatan Menu")
        col_op1, col_op2 = st.columns(2)
        with col_op1: waktu_menit = st.number_input("Total Waktu Pembuatan Menu (Menit):", min_value=0.0, step=5.0)
        with col_op2: gas_digunakan = st.number_input("Estimasi Pemakaian Gas LPG (Kg):", min_value=0.0, format="%.3f", step=0.010)
            
        biaya_gaji = (10000 / 60) * waktu_menit
        biaya_listrik = (3000 / 60) * waktu_menit
        biaya_gas = gas_digunakan * 18000
        
        tot_operasional = biaya_gaji + biaya_listrik + biaya_gas
        tot_final_hpp = tot_bahan + tot_operasional
        
        st.write("---")
        st.subheader("💰 Ringkasan Kalkulasi HPP Menu")
        res_c1, res_c2, res_c3 = st.columns(3)
        res_c1.metric("HPP Bahan Baku", f"Rp {tot_bahan:,.2f}")
        res_c2.metric("HPP Operasional", f"Rp {tot_operasional:,.2f}")
        res_c3.metric("TOTAL HPP PER PORSI MENU", f"Rp {tot_final_hpp:,.2f}")
        
        if tot_final_hpp > 0:
            fig, ax = plt.subplots(figsize=(5, 3))
            labels = ['Bahan Baku', 'Gaji Karyawan', 'Listrik', 'Gas LPG']
            sizes = [tot_bahan, biaya_gaji, biaya_listrik, biaya_gas]
            labels = [l for l, s in zip(labels, sizes) if s > 0]
            sizes = [s for s in sizes if s > 0]
            ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90, colors=['#4dabf7', '#ffc078', '#ff8787', '#b2f2bb'])
            ax.axis('equal')
            st.pyplot(fig)

        st.write("---")
        st.subheader("💾 3. Konfirmasi & Kunci Simpan Menu")
        col_s1, col_s2 = st.columns(2)
        with col_s1: nama_menu_final = st.text_input("Beri Nama Menu/Resep Akhir:", value=st.session_state.edit_resep_nama)
        with col_s2:
            st.write("")
            st.write("")
            if st.button("✅ Kunci & Simpan Menu ke Cloud Supabase", use_container_width=True, type="primary"):
                if nama_menu_final and not st.session_state.racikan_sementara.empty:
                    tgl_entri = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    conn = get_connection()
                    cursor = conn.cursor()
                    
                    cursor.execute("""
                        INSERT INTO resep (nama_resep, total_hpp_bahan, total_operasional, total_hpp_final, tanggal_dibuat) 
                        VALUES (%s, %s, %s, %s, %s) 
                        ON CONFLICT (nama_resep) 
                        DO UPDATE SET total_hpp_bahan=EXCLUDED.total_hpp_bahan, total_operasional=EXCLUDED.total_operasional, total_hpp_final=EXCLUDED.total_hpp_final
                    """, (nama_menu_final, tot_bahan, tot_operasional, tot_final_hpp, tgl_entri))
                    
                    cursor.execute("SELECT id FROM resep WHERE nama_resep=%s", (nama_menu_final,))
                    r_id = cursor.fetchone()[0]
                    cursor.execute("DELETE FROM detail_resep WHERE resep_id=%s", (r_id,))
                    
                    for _, r in st.session_state.racikan_sementara.iterrows():
                        cursor.execute("INSERT INTO detail_resep (resep_id, nama_bahan, jumlah_pakai, satuan, subtotal_biaya) VALUES (%s,%s,%s,%s,%s)",
                                       (r_id, r['Nama Bahan'], r['Jumlah Pakai'], r['Satuan'], r['Subtotal']))
                        cursor.execute("UPDATE bahan_baku SET stok_gudang = stok_gudang - %s WHERE nama_bahan = %s", (r['Jumlah Pakai'], r['Nama Bahan']))
                        
                    conn.commit()
                    cursor.close()
                    conn.close()
                    
                    st.success(f"Resep '{nama_menu_final}' tersimpan di Cloud & Stok otomatis terpotong!")
                    st.session_state.racikan_sementara = pd.DataFrame(columns=["Nama Bahan", "Jumlah Pakai", "Satuan", "Subtotal"])
                    st.session_state.edit_resep_nama = ""
                    st.rerun()

# ==========================================
# 6. TAB: ARSIP & PROYEKSI MENU (EDIT & SIMULASI)
# ==========================================
elif menu == "📂 Arsip & Proyeksi Menu":
    st.title("📂 Arsip Dokumen Resep & Finansial Cloud")
    
    try:
        conn = get_connection()
        # PERBAIKAN TANDA KUTIP
        df_resep = pd.read_sql_query('SELECT id as "ID", nama_resep as "Nama Menu/Resep", total_hpp_final as "HPP Pokok (Rp)", harga_jual as "Harga Jual Saat Ini (Rp)", tanggal_dibuat as "Tanggal Kunci" FROM resep', conn)
        
        if df_resep.empty:
            st.info("Belum ada resep kuliner di database cloud.")
            conn.close()
        else:
            st.subheader("1. Atur Finansial Harga Jual Menu")
            editor_resep = st.data_editor(df_resep, use_container_width=True, disabled=["ID", "Nama Menu/Resep", "HPP Pokok (Rp)", "Tanggal Kunci"])
            
            if st.button("💾 Simpan Perubahan Harga Jual"):
                cursor = conn.cursor()
                for _, r in editor_resep.iterrows():
                    cursor.execute("UPDATE resep SET harga_jual=%s WHERE id=%s", (float(r['Harga Jual Saat Ini (Rp)']), int(r['ID'])))
                conn.commit()
                st.success("Harga jual cloud diperbarui!")
                st.rerun()
                
            st.write("---")
            st.subheader("🛠️ 2. Pusat Aksi Resep")
            pilih_r = st.selectbox("Pilih Resep yang Ingin Dikelola:", df_resep['Nama Menu/Resep'].tolist())
            
            col_ax1, col_ax2, col_ax3 = st.columns(3)
            with col_ax1:
                if st.button("🔍 Buka Rincian Detail Bahan", use_container_width=True):
                    cursor = conn.cursor()
                    cursor.execute("SELECT id FROM resep WHERE nama_resep=%s", (pilih_r,))
                    r_id = cursor.fetchone()[0]
                    # PERBAIKAN TANDA KUTIP
                    df_det = pd.read_sql_query(f'SELECT nama_bahan as "Komponen Bahan", jumlah_pakai as "Jumlah Pakai", satuan as "Satuan", subtotal_biaya as "Biaya (Rp)" FROM detail_resep WHERE resep_id={r_id}', conn)
                    st.dataframe(df_det, use_container_width=True)
            with col_ax2:
                if st.button("⚙️ Tarik Kembali Data untuk Di-edit", use_container_width=True):
                    cursor = conn.cursor()
                    cursor.execute("SELECT id FROM resep WHERE nama_resep=%s", (pilih_r,))
                    r_id = cursor.fetchone()[0]
                    # PERBAIKAN TANDA KUTIP
                    df_det = pd.read_sql_query(f'SELECT nama_bahan as "Nama Bahan", jumlah_pakai as "Jumlah Pakai", satuan as "Satuan", subtotal_biaya as "Subtotal" FROM detail_resep WHERE resep_id={r_id}', conn)
                    st.session_state.racikan_sementara = df_det
                    st.session_state.edit_resep_nama = pilih_r
                    st.success("Berhasil ditarik! Silakan edit di tab '2. Racik Resep & Operasional'.")
            with col_ax3:
                if st.button("🗑️ Hapus Menu Ini Permanen", use_container_width=True, type="primary"):
                    cursor = conn.cursor()
                    cursor.execute("SELECT id FROM resep WHERE nama_resep=%s", (pilih_r,))
                    r_id = cursor.fetchone()[0]
                    cursor.execute("DELETE FROM detail_resep WHERE resep_id=%s", (r_id,))
                    cursor.execute("DELETE FROM resep WHERE id=%s", (r_id,))
                    conn.commit()
                    st.rerun()
            conn.close()
    except Exception as e:
        st.error(f"Gagal memuat arsip dari cloud. Eror: {e}")