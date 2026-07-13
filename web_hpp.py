import streamlit as st
import pandas as pd
import psycopg2
import matplotlib.pyplot as plt
from datetime import datetime
import time  # TAMBAHAN: Modul untuk memberi jeda waktu notifikasi

# ==========================================
# 1. PENGATURAN HALAMAN & KONEKSI SUPABASE
# ==========================================
st.set_page_config(page_title="Sistem ERP Cloud V4 (Multi-Gudang)", layout="wide", page_icon="🏢")

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
            kerugian_rp REAL DEFAULT 0,
            laba_internal REAL DEFAULT 0,
            dari_gudang TEXT,
            ke_unit TEXT
        )
    """)
    
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
st.sidebar.title("🏢 ERP MULTI-GUDANG V4")
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
    st.write("⚠️ **Aturan Sistem:** Semua barang baru **WAJIB** diinput ke Gudang Induk terlebih dahulu.")
    
    df_bahan_ada = get_daftar_bahan()
    pilihan_edit = "-- Input Produk Baru / Kulakan Baru --"
    if not df_bahan_ada.empty:
        pilihan_edit = st.selectbox("💡 Pilih barang untuk diedit/ditambah:", ["-- Input Produk Baru / Kulakan Baru --"] + df_bahan_ada['nama_bahan'].tolist())
    
    val_nama, val_harga, val_isi, val_satuan, val_jual_internal = "", 0.0, 1.0, "pcs", 0.0
    if pilihan_edit != "-- Input Produk Baru / Kulakan Baru --":
        row_edit = df_bahan_ada[df_bahan_ada['nama_bahan'] == pilihan_edit].iloc[0]
        val_nama = row_edit['nama_bahan']
        val_harga = float(row_edit['harga_beli'])
        val_isi = float(row_edit['jumlah_isi'])
        val_satuan = row_edit['satuan']
        val_jual_internal = float(row_edit.get('harga_jual_internal', 0))
        
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: entry_nama = st.text_input("Nama Barang", value=val_nama)
    with c2: entry_harga = st.number_input("Total Harga Beli (Rp)", min_value=0.0, value=val_harga)
    with c3: entry_isi = st.number_input("Jumlah Isi", min_value=1.0, value=val_isi)
    with c4: entry_satuan = st.text_input("Satuan", value=val_satuan)
    with c5: entry_jual_int = st.number_input("Harga Jual ke Unit (Rp/Satuan)", min_value=0.0, value=val_jual_internal)
    
    if st.button("💾 Simpan & Masukkan ke Gudang Induk", type="primary"):
        if entry_nama:
            h_satuan = entry_harga / entry_isi
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT stok_gudang FROM bahan_baku WHERE nama_bahan=%s", (entry_nama,))
            res = cursor.fetchone()
            stok_sekarang = (res[0] if res else 0) + entry_isi if pilihan_edit == "-- Input Produk Baru / Kulakan Baru --" else entry_isi 
            
            cursor.execute("""
                INSERT INTO bahan_baku (nama_bahan, harga_beli, jumlah_isi, satuan, harga_satuan, stok_gudang, harga_jual_internal) 
                VALUES (%s, %s, %s, %s, %s, %s, %s) 
                ON CONFLICT (nama_bahan) 
                DO UPDATE SET harga_beli=EXCLUDED.harga_beli, jumlah_isi=EXCLUDED.jumlah_isi, 
                satuan=EXCLUDED.satuan, harga_satuan=EXCLUDED.harga_satuan, harga_jual_internal=EXCLUDED.harga_jual_internal
            """, (entry_nama.strip(), entry_harga, entry_isi, entry_satuan.strip(), h_satuan, stok_sekarang, entry_jual_int))
            conn.commit()
            cursor.close()
            conn.close()
            
            # NOTIFIKASI SUKSES (DITAHAN 1.5 DETIK AGAR TERBACA)
            st.success(f"✅ Berhasil dimasukkan ke Gudang Induk!")
            time.sleep(1.5)
            st.rerun()

    st.write("---")
    st.subheader("📋 Status Empat Pintu Gudang")
    df_tampil = get_daftar_bahan()
    if not df_tampil.empty:
        df_tampil = df_tampil[['nama_bahan', 'harga_satuan', 'harga_jual_internal', 'stok_gudang', 'stok_cafe', 'stok_kios', 'stok_taman', 'satuan']]
        df_tampil.columns = ['Nama Barang', 'Modal Dasar', 'Jual Internal', 'INDUK (Pusat)', 'CAFE', 'KIOS', 'TAMAN/HOMESTAY', 'Satuan']
        st.dataframe(df_tampil, use_container_width=True)

# ==========================================
# 5. TAB: DISTRIBUSI (JUAL KE UNIT)
# ==========================================
elif menu == "🚚 Penjualan ke Unit (Cabang)":
    st.title("🚚 Transfer & Penjualan Internal")
    
    df_g = get_daftar_bahan()
    if df_g.empty:
        st.warning("Gudang induk masih kosong.")
    else:
        col1, col2, col3 = st.columns(3)
        with col1: bahan_transfer = st.selectbox("Pilih Barang dari Gudang Induk:", df_g['nama_bahan'].tolist())
        
        data_b = df_g[df_g['nama_bahan'] == bahan_transfer].iloc[0]
        stok_induk = data_b['stok_gudang']
        harga_modal = data_b['harga_satuan']
        harga_jual_internal = data_b.get('harga_jual_internal', harga_modal)
        
        with col2: qty_transfer = st.number_input(f"Keluarkan Berapa? (Sisa: {stok_induk} {data_b['satuan']})", min_value=1.0, max_value=float(stok_induk) if stok_induk > 0 else 1.0)
        with col3: unit_tujuan = st.radio("Jual/Transfer Ke Mana?", ["Cafe", "Kios", "Taman"])
        
        total_modal = qty_transfer * harga_modal
        total_jual = qty_transfer * harga_jual_internal
        laba = total_jual - total_modal
        
        st.info(f"**Nota Internal:** Gudang Etnik menjual ke {unit_tujuan} seharga **Rp {total_jual:,.0f}**. Laba Gudang: **Rp {laba:,.0f}**")
        
        if st.button(f"🛒 Konfirmasi Transfer ke {unit_tujuan}", type="primary", use_container_width=True):
            if stok_induk >= qty_transfer:
                tgl = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                conn = get_connection()
                cursor = conn.cursor()
                
                cursor.execute("UPDATE bahan_baku SET stok_gudang = stok_gudang - %s WHERE nama_bahan = %s", (qty_transfer, bahan_transfer))
                
                if unit_tujuan == "Cafe":
                    cursor.execute("UPDATE bahan_baku SET stok_cafe = COALESCE(stok_cafe, 0) + %s WHERE nama_bahan = %s", (qty_transfer, bahan_transfer))
                elif unit_tujuan == "Kios":
                    cursor.execute("UPDATE bahan_baku SET stok_kios = COALESCE(stok_kios, 0) + %s WHERE nama_bahan = %s", (qty_transfer, bahan_transfer))
                elif unit_tujuan == "Taman":
                    cursor.execute("UPDATE bahan_baku SET stok_taman = COALESCE(stok_taman, 0) + %s WHERE nama_bahan = %s", (qty_transfer, bahan_transfer))
                
                cursor.execute("""
                    INSERT INTO riwayat_stok (tanggal, nama_bahan, jenis_transaksi, jumlah, keterangan, laba_internal, dari_gudang, ke_unit) 
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                """, (tgl, bahan_transfer, 'Penjualan Internal', qty_transfer, str(total_jual), laba, 'Gudang Etnik', unit_tujuan))
                
                conn.commit()
                cursor.close()
                conn.close()
                
                # NOTIFIKASI SUKSES
                st.success(f"✅ Sukses! {qty_transfer} {data_b['satuan']} {bahan_transfer} telah berpindah ke {unit_tujuan}.")
                time.sleep(1.5)
                st.rerun()
            else:
                st.error("Stok Gudang Induk tidak mencukupi!")

# ==========================================
# 6. TAB: OPERASIONAL & DAPUR
# ==========================================
elif menu == "🍳 Operasional & Dapur":
    st.title("🍳 Ruang Penggunaan & Resep")
    unit_pembuat = st.radio("Unit Operasional:", ["Cafe (Dapur Makanan)", "Kios (Jajanan/Minuman)", "Taman (Kebersihan/Homestay)"])
    
    df_b = get_daftar_bahan()
    if df_b.empty:
        st.warning("⚠️ Belum ada barang di database!")
    else:
        st.subheader("1. Gunakan Barang / Bahan")
        col_c1, col_c2, col_c3 = st.columns([2, 1, 1])
        with col_c1:
            kata_kunci = st.text_input("🔍 Cari barang/bahan:")
            filtered_bahan = df_b[df_b['nama_bahan'].str.lower().str.contains(kata_kunci.lower())] if kata_kunci else df_b
            pilih_b = st.selectbox("Pilih:", filtered_bahan['nama_bahan'].tolist() if not filtered_bahan.empty else ["Tidak ditemukan"])
        
        with col_c2:
            satuan_label = f"Jumlah ({df_b[df_b['nama_bahan']==pilih_b].iloc[0]['satuan']}):" if (pilih_b != "Tidak ditemukan" and not filtered_bahan.empty) else "Jumlah"
            j_pakai = st.number_input(satuan_label, min_value=0.0, step=1.0)
            
        with col_c3:
            st.write("")
            st.write("")
            if st.button("➕ Tambah ke Catatan", use_container_width=True):
                if pilih_b != "Tidak ditemukan" and j_pakai > 0:
                    data_row = df_b[df_b['nama_bahan'] == pilih_b].iloc[0]
                    h_sat = data_row.get('harga_jual_internal', data_row['harga_satuan'])
                    if h_sat <= 0: h_sat = data_row['harga_satuan']
                    
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
        st.subheader(f"🛒 Draf Penggunaan {unit_pembuat}")
        if not st.session_state.racikan_sementara.empty:
            edited_df = st.data_editor(st.session_state.racikan_sementara, use_container_width=True, num_rows="dynamic")
            st.session_state.racikan_sementara = edited_df
            tot_bahan = st.session_state.racikan_sementara['Subtotal'].sum()
        else:
            st.info("Draf masih kosong.")
            tot_bahan = 0.0

        st.write("---")
        st.subheader("⚡ 2. Komponen Biaya Tenaga/Listrik")
        col_op1, col_op2 = st.columns(2)
        with col_op1: waktu_menit = st.number_input("Waktu Pengerjaan (Menit):", min_value=0.0, step=5.0)
        with col_op2: gas_digunakan = st.number_input("Estimasi Gas LPG (Kg):", min_value=0.0, format="%.3f", step=0.010)
            
        biaya_gaji = (10000 / 60) * waktu_menit
        biaya_listrik = (3000 / 60) * waktu_menit
        biaya_gas = gas_digunakan * 18000
        
        tot_operasional = biaya_gaji + biaya_listrik + biaya_gas
        tot_final_hpp = tot_bahan + tot_operasional
        
        res_c1, res_c2, res_c3 = st.columns(3)
        res_c1.metric("Biaya Barang/Bahan", f"Rp {tot_bahan:,.2f}")
        res_c2.metric("Biaya Operasional", f"Rp {tot_operasional:,.2f}")
        res_c3.metric("TOTAL HPP KESELURUHAN", f"Rp {tot_final_hpp:,.2f}")

        st.write("---")
        st.subheader("💾 3. Kunci Pemakaian & Simpan Laporan")
        col_s1, col_s2 = st.columns(2)
        with col_s1: nama_menu_final = st.text_input("Nama Laporan/Menu Akhir:", value=st.session_state.edit_resep_nama)
        with col_s2:
            st.write("")
            st.write("")
            if st.button("✅ Kunci Data ke Cloud", use_container_width=True, type="primary"):
                if nama_menu_final and not st.session_state.racikan_sementara.empty:
                    tgl_entri = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    conn = get_connection()
                    cursor = conn.cursor()
                    
                    cursor.execute("""
                        INSERT INTO resep (nama_resep, total_hpp_bahan, total_operasional, total_hpp_final, tanggal_dibuat) 
                        VALUES (%s, %s, %s, %s, %s) 
                        ON CONFLICT (nama_resep) 
                        DO UPDATE SET total_hpp_bahan=EXCLUDED.total_hpp_bahan, total_operasional=EXCLUDED.total_operasional, total_hpp_final=EXCLUDED.total_hpp_final
                    """, (f"[{unit_pembuat.split()[0]}] {nama_menu_final}", tot_bahan, tot_operasional, tot_final_hpp, tgl_entri))
                    
                    cursor.execute("SELECT id FROM resep WHERE nama_resep=%s", (f"[{unit_pembuat.split()[0]}] {nama_menu_final}",))
                    r_id = cursor.fetchone()[0]
                    cursor.execute("DELETE FROM detail_resep WHERE resep_id=%s", (r_id,))
                    
                    for _, r in st.session_state.racikan_sementara.iterrows():
                        cursor.execute("INSERT INTO detail_resep (resep_id, nama_bahan, jumlah_pakai, satuan, subtotal_biaya) VALUES (%s,%s,%s,%s,%s)",
                                       (r_id, r['Nama Bahan'], r['Jumlah Pakai'], r['Satuan'], r['Subtotal']))
                        
                        if "Cafe" in unit_pembuat:
                            cursor.execute("UPDATE bahan_baku SET stok_cafe = COALESCE(stok_cafe,0) - %s WHERE nama_bahan = %s", (r['Jumlah Pakai'], r['Nama Bahan']))
                        elif "Kios" in unit_pembuat:
                            cursor.execute("UPDATE bahan_baku SET stok_kios = COALESCE(stok_kios,0) - %s WHERE nama_bahan = %s", (r['Jumlah Pakai'], r['Nama Bahan']))
                        elif "Taman" in unit_pembuat:
                            cursor.execute("UPDATE bahan_baku SET stok_taman = COALESCE(stok_taman,0) - %s WHERE nama_bahan = %s", (r['Jumlah Pakai'], r['Nama Bahan']))
                        
                    conn.commit()
                    cursor.close()
                    conn.close()
                    
                    # NOTIFIKASI SUKSES
                    st.success(f"✅ Data tersimpan & Stok otomatis terpotong!")
                    time.sleep(1.5)
                    
                    st.session_state.racikan_sementara = pd.DataFrame(columns=["Nama Bahan", "Jumlah Pakai", "Satuan", "Subtotal"])
                    st.session_state.edit_resep_nama = ""
                    st.rerun()

# ==========================================
# 7. TAB: ARSIP & HARGA JUAL
# ==========================================
elif menu == "📂 Arsip & Harga Jual":
    st.title("📂 Arsip Dokumen Pengeluaran / Resep")
    
    try:
        conn = get_connection()
        df_resep = pd.read_sql_query('SELECT id as "ID", nama_resep as "Nama Laporan/Menu", total_hpp_final as "HPP Pokok (Rp)", harga_jual as "Harga Jual Saat Ini (Rp)", tanggal_dibuat as "Tanggal Kunci" FROM resep', conn)
        
        if df_resep.empty:
            st.info("Belum ada arsip di database cloud.")
            conn.close()
        else:
            st.subheader("1. Atur Finansial Harga Jual Akhir (Bila Ada)")
            editor_resep = st.data_editor(df_resep, use_container_width=True, disabled=["ID", "Nama Laporan/Menu", "HPP Pokok (Rp)", "Tanggal Kunci"])
            
            if st.button("💾 Simpan Perubahan Harga Jual"):
                cursor = conn.cursor()
                for _, r in editor_resep.iterrows():
                    cursor.execute("UPDATE resep SET harga_jual=%s WHERE id=%s", (float(r['Harga Jual Saat Ini (Rp)']), int(r['ID'])))
                conn.commit()
                st.success("✅ Harga jual diperbarui!")
                time.sleep(1)
                st.rerun()
                
            st.write("---")
            st.subheader("🛠️ 2. Pusat Aksi Arsip")
            pilih_r = st.selectbox("Pilih Laporan/Menu yang Ingin Dikelola:", df_resep['Nama Laporan/Menu'].tolist())
            
            col_ax1, col_ax2, col_ax3 = st.columns(3)
            with col_ax1:
                if st.button("🔍 Buka Rincian Detail", use_container_width=True):
                    cursor = conn.cursor()
                    cursor.execute("SELECT id FROM resep WHERE nama_resep=%s", (pilih_r,))
                    r_id = cursor.fetchone()[0]
                    df_det = pd.read_sql_query(f'SELECT nama_bahan as "Barang/Bahan", jumlah_pakai as "Jumlah Pakai", satuan as "Satuan", subtotal_biaya as "Biaya (Rp)" FROM detail_resep WHERE resep_id={r_id}', conn)
                    st.dataframe(df_det, use_container_width=True)
            with col_ax2:
                if st.button("⚙️ Tarik Kembali Data untuk Di-edit", use_container_width=True):
                    cursor = conn.cursor()
                    cursor.execute("SELECT id FROM resep WHERE nama_resep=%s", (pilih_r,))
                    r_id = cursor.fetchone()[0]
                    df_det = pd.read_sql_query(f'SELECT nama_bahan as "Nama Bahan", jumlah_pakai as "Jumlah Pakai", satuan as "Satuan", subtotal_biaya as "Subtotal" FROM detail_resep WHERE resep_id={r_id}', conn)
                    st.session_state.racikan_sementara = df_det
                    nama_bersih = pilih_r.split("] ")[-1] if "]" in pilih_r else pilih_r
                    st.session_state.edit_resep_nama = nama_bersih
                    st.success("✅ Berhasil ditarik! Silakan edit di tab 'Operasional & Dapur'.")
                    time.sleep(1.5)
            with col_ax3:
                if st.button("🗑️ Hapus Laporan Permanen", use_container_width=True, type="primary"):
                    cursor = conn.cursor()
                    cursor.execute("SELECT id FROM resep WHERE nama_resep=%s", (pilih_r,))
                    r_id = cursor.fetchone()[0]
                    cursor.execute("DELETE FROM detail_resep WHERE resep_id=%s", (r_id,))
                    cursor.execute("DELETE FROM resep WHERE id=%s", (r_id,))
                    conn.commit()
                    st.rerun()
            conn.close()
    except Exception as e:
        st.error(f"Gagal memuat arsip. Eror: {e}")
