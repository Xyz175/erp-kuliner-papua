import streamlit as st
import pandas as pd
import psycopg2
import matplotlib.pyplot as plt
from datetime import datetime

# ==========================================
# 1. PENGATURAN HALAMAN & KONEKSI SUPABASE
# ==========================================
st.set_page_config(page_title="Sistem ERP Cloud V2 (Multi-Gudang)", layout="wide", page_icon="🏢")

# --- SISTEM LOGIN ---
if 'sudah_login' not in st.session_state:
    st.session_state.sudah_login = False

if not st.session_state.sudah_login:
    st.title("🔒 Sistem ERP Terkunci")
    st.write("Silakan masukkan Username dan Password Anda.")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    
    # Ganti dengan username dan password rahasia Anda
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
    
    # 1. Tabel Bahan Baku (Sudah Multi-Gudang)
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
            harga_jual_internal REAL DEFAULT 0
        )
    """)
    # 2. Tabel Resep
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
    
    # SUNTIKAN KOLOM BARU JIKA SEBELUMNYA BELUM ADA
    kolom_baru = [
        "ALTER TABLE bahan_baku ADD COLUMN stok_kios REAL DEFAULT 0",
        "ALTER TABLE bahan_baku ADD COLUMN stok_cafe REAL DEFAULT 0",
        "ALTER TABLE bahan_baku ADD COLUMN harga_jual_internal REAL DEFAULT 0",
        "ALTER TABLE riwayat_stok ADD COLUMN laba_internal REAL DEFAULT 0",
        "ALTER TABLE riwayat_stok ADD COLUMN dari_gudang TEXT",
        "ALTER TABLE riwayat_stok ADD COLUMN ke_unit TEXT"
    ]
    for query in kolom_baru:
        try: cursor.execute(query)
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
st.sidebar.title("🏢 ERP MULTI-GUDANG")
st.sidebar.write("---")
menu = st.sidebar.radio("Navigasi Sistem:", 
    ["📊 Dashboard Analitik", "📦 Manajemen Gudang Pusat", "🚚 Penjualan ke Kios/Cafe", "🍳 Dapur (Racik Resep)", "📂 Arsip & Harga Jual"]
)

def get_daftar_bahan():
    try:
        conn = get_connection()
        df = pd.read_sql_query("SELECT * FROM bahan_baku", conn)
        conn.close()
        return df
    except:
        return pd.DataFrame()

# ==========================================
# 3. TAB: DASHBOARD ANALITIK
# ==========================================
if menu == "📊 Dashboard Analitik":
    st.title("📊 Laba Internal & Analitik Pusat")
    st.write("Pantau keuntungan yang didapat Gudang Utama (Etnik) dari hasil menjual bahan baku ke unit Kios dan Cafe.")
    
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
        c1.metric("Laba Bersih Gudang (Internal)", f"Rp {total_laba_gudang:,.0f}", "Omset Kasir Masuk")
        c2.metric("Kerugian Barang Hilang", f"Rp {total_rugi_gudang:,.0f}", delta=f"-Rp {total_rugi_gudang:,.0f}", delta_color="inverse")
        
        st.write("---")
        st.subheader("📜 Riwayat Penjualan Gudang ke Unit (Kios/Cafe)")
        st.dataframe(df_log, use_container_width=True)
    except Exception as e:
        st.warning(f"Menunggu sinkronisasi data perdana... ({e})")

# ==========================================
# 4. TAB: MANAJEMEN GUDANG PUSAT (ETNIK)
# ==========================================
elif menu == "📦 Manajemen Gudang Pusat":
    st.title("📦 Gudang Induk (Etnik Papua)")
    st.write("Hanya barang yang masuk ke Gudang Utama yang diinput di sini.")
    
    df_bahan_ada = get_daftar_bahan()
    pilihan_edit = "-- Tambah Barang Baru --"
    if not df_bahan_ada.empty:
        pilihan_edit = st.selectbox("💡 Pilih barang untuk diedit / ditambah stoknya:", ["-- Tambah Barang Baru --"] + df_bahan_ada['nama_bahan'].tolist())
    
    val_nama, val_harga, val_isi, val_satuan, val_jual_internal = "", 0.0, 1.0, "pcs", 0.0
    if pilihan_edit != "-- Tambah Barang Baru --":
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
    with c4: entry_satuan = st.text_input("Satuan (gr/pcs/ml)", value=val_satuan)
    with c5: entry_jual_int = st.number_input("Harga Jual ke Kasir Unit (Rp)", min_value=0.0, value=val_jual_internal, help="Contoh: Jika modal Rp1, jual ke Cafe Rp2 per gram.")
    
    if st.button("💾 Beli & Masukkan ke Gudang Induk (Etnik)", type="primary"):
        if entry_nama:
            h_satuan = entry_harga / entry_isi
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT stok_gudang FROM bahan_baku WHERE nama_bahan=%s", (entry_nama,))
            res = cursor.fetchone()
            stok_sekarang = (res[0] if res else 0) + entry_isi if pilihan_edit == "-- Tambah Barang Baru --" else entry_isi 
            
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
            st.success(f"Berhasil dimasukkan ke Gudang Etnik!")
            st.rerun()

    st.write("---")
    st.subheader("📋 Status Tiga Gudang Sekaligus (Induk, Kios, Cafe)")
    df_tampil = get_daftar_bahan()
    if not df_tampil.empty:
        df_tampil = df_tampil[['nama_bahan', 'harga_satuan', 'harga_jual_internal', 'stok_gudang', 'stok_kios', 'stok_cafe', 'satuan']]
        df_tampil.columns = ['Nama Barang', 'Modal/Satuan', 'Harga Jual ke Unit', 'STOK INDUK', 'STOK KIOS', 'STOK CAFE', 'Satuan']
        st.dataframe(df_tampil, use_container_width=True)

# ==========================================
# 5. TAB: DISTRIBUSI (JUAL KE KIOS/CAFE)
# ==========================================
elif menu == "🚚 Penjualan ke Kios/Cafe":
    st.title("🚚 Transfer & Penjualan Internal")
    st.write("Keluarkan barang dari Gudang Induk, transfer ke Kios/Cafe. Ini akan dihitung sebagai penjualan oleh Gudang.")
    
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
        with col3: unit_tujuan = st.radio("Jual/Transfer Ke Mana?", ["Kios", "Cafe"])
        
        total_modal = qty_transfer * harga_modal
        total_jual = qty_transfer * harga_jual_internal
        laba = total_jual - total_modal
        
        st.info(f"**Kalkulasi Kasir:** Gudang Etnik menjual ke {unit_tujuan} seharga **Rp {total_jual:,.0f}**. Laba Gudang: **Rp {laba:,.0f}**")
        
        if st.button(f"🛒 Konfirmasi Penjualan & Transfer ke {unit_tujuan}", type="primary", use_container_width=True):
            if stok_induk >= qty_transfer:
                tgl = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                conn = get_connection()
                cursor = conn.cursor()
                
                # Kurangi stok induk
                cursor.execute("UPDATE bahan_baku SET stok_gudang = stok_gudang - %s WHERE nama_bahan = %s", (qty_transfer, bahan_transfer))
                
                # Tambah stok unit
                if unit_tujuan == "Kios":
                    cursor.execute("UPDATE bahan_baku SET stok_kios = COALESCE(stok_kios, 0) + %s WHERE nama_bahan = %s", (qty_transfer, bahan_transfer))
                else:
                    cursor.execute("UPDATE bahan_baku SET stok_cafe = COALESCE(stok_cafe, 0) + %s WHERE nama_bahan = %s", (qty_transfer, bahan_transfer))
                
                # Catat Keuntungan Internal
                cursor.execute("""
                    INSERT INTO riwayat_stok (tanggal, nama_bahan, jenis_transaksi, jumlah, keterangan, laba_internal, dari_gudang, ke_unit) 
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                """, (tgl, bahan_transfer, 'Penjualan Internal', qty_transfer, str(total_jual), laba, 'Gudang Etnik', unit_tujuan))
                
                conn.commit()
                cursor.close()
                conn.close()
                st.success(f"Sukses! {bahan_transfer} telah dibayar oleh Kasir {unit_tujuan} dan stok sudah berpindah.")
                st.rerun()
            else:
                st.error("Stok Gudang Induk tidak mencukupi!")

# ==========================================
# 6. TAB: DAPUR / RACIK RESEP
# ==========================================
elif menu == "🍳 Dapur (Racik Resep)":
    st.title("🍳 Ruang Kerja Meracik Resep")
    
    unit_pembuat = st.radio("Resep ini dibuat di dapur mana? (Stok akan dipotong dari sini)", ["Cafe", "Kios"])
    
    df_b = get_daftar_bahan()
    if df_b.empty:
        st.warning("⚠️ Silakan isi data Bahan Baku di menu Gudang terlebih dahulu!")
    else:
        st.subheader("1. Tambahkan Bahan ke Komponen Menu")
        col_c1, col_c2, col_c3 = st.columns([2, 1, 1])
        with col_c1:
            kata_kunci = st.text_input("🔍 Cari bahan baku:")
            filtered_bahan = df_b[df_b['nama_bahan'].str.lower().str.contains(kata_kunci.lower())] if kata_kunci else df_b
            pilih_b = st.selectbox("Pilih Bahan:", filtered_bahan['nama_bahan'].tolist() if not filtered_bahan.empty else ["Tidak ditemukan"])
        
        with col_c2:
            satuan_label = f"Jumlah ({df_b[df_b['nama_bahan']==pilih_b].iloc[0]['satuan']}):" if (pilih_b != "Tidak ditemukan" and not filtered_bahan.empty) else "Jumlah"
            j_pakai = st.number_input(satuan_label, min_value=0.0, step=1.0)
            
        with col_c3:
            st.write("")
            st.write("")
            if st.button("➕ Masukkan ke Resep", use_container_width=True):
                if pilih_b != "Tidak ditemukan" and j_pakai > 0:
                    data_row = df_b[df_b['nama_bahan'] == pilih_b].iloc[0]
                    # Harga HPP dapur Cafe/Kios menggunakan Harga Jual Internal (karena mereka beli dari gudang induk)
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
        st.subheader("🛒 Draf Racikan Resep Saat Ini")
        if not st.session_state.racikan_sementara.empty:
            edited_df = st.data_editor(st.session_state.racikan_sementara, use_container_width=True, num_rows="dynamic")
            st.session_state.racikan_sementara = edited_df
            tot_bahan = st.session_state.racikan_sementara['Subtotal'].sum()
        else:
            st.info("Draf racikan resep masih kosong.")
            tot_bahan = 0.0

        st.write("---")
        st.subheader("⚡ 2. Komponen Biaya Operasional")
        col_op1, col_op2 = st.columns(2)
        with col_op1: waktu_menit = st.number_input("Waktu Pembuatan (Menit):", min_value=0.0, step=5.0)
        with col_op2: gas_digunakan = st.number_input("Estimasi Gas LPG (Kg):", min_value=0.0, format="%.3f", step=0.010)
            
        biaya_gaji = (10000 / 60) * waktu_menit
        biaya_listrik = (3000 / 60) * waktu_menit
        biaya_gas = gas_digunakan * 18000
        
        tot_operasional = biaya_gaji + biaya_listrik + biaya_gas
        tot_final_hpp = tot_bahan + tot_operasional
        
        res_c1, res_c2, res_c3 = st.columns(3)
        res_c1.metric("HPP Bahan Baku (Beli ke Gudang)", f"Rp {tot_bahan:,.2f}")
        res_c2.metric("HPP Operasional", f"Rp {tot_operasional:,.2f}")
        res_c3.metric("TOTAL HPP MENU", f"Rp {tot_final_hpp:,.2f}")

        st.write("---")
        st.subheader("💾 3. Konfirmasi & Kunci Simpan Menu")
        col_s1, col_s2 = st.columns(2)
        with col_s1: nama_menu_final = st.text_input("Beri Nama Menu/Resep Akhir:", value=st.session_state.edit_resep_nama)
        with col_s2:
            st.write("")
            st.write("")
            if st.button("✅ Kunci & Simpan Menu ke Cloud", use_container_width=True, type="primary"):
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
                        
                        # POTONG STOK DARI UNIT PEMBUAT (CAFE / KIOS)
                        if unit_pembuat == "Cafe":
                            cursor.execute("UPDATE bahan_baku SET stok_cafe = COALESCE(stok_cafe,0) - %s WHERE nama_bahan = %s", (r['Jumlah Pakai'], r['Nama Bahan']))
                        else:
                            cursor.execute("UPDATE bahan_baku SET stok_kios = COALESCE(stok_kios,0) - %s WHERE nama_bahan = %s", (r['Jumlah Pakai'], r['Nama Bahan']))
                        
                    conn.commit()
                    cursor.close()
                    conn.close()
                    
                    st.success(f"Resep '{nama_menu_final}' tersimpan di Cloud & Stok {unit_pembuat} terpotong!")
                    st.session_state.racikan_sementara = pd.DataFrame(columns=["Nama Bahan", "Jumlah Pakai", "Satuan", "Subtotal"])
                    st.session_state.edit_resep_nama = ""
                    st.rerun()

# ==========================================
# 7. TAB: ARSIP & HARGA JUAL
# ==========================================
elif menu == "📂 Arsip & Harga Jual":
    st.title("📂 Arsip Dokumen Resep Cloud")
    
    try:
        conn = get_connection()
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
                    df_det = pd.read_sql_query(f'SELECT nama_bahan as "Komponen Bahan", jumlah_pakai as "Jumlah Pakai", satuan as "Satuan", subtotal_biaya as "Biaya (Rp)" FROM detail_resep WHERE resep_id={r_id}', conn)
                    st.dataframe(df_det, use_container_width=True)
            with col_ax2:
                if st.button("⚙️ Tarik Kembali Data untuk Di-edit", use_container_width=True):
                    cursor = conn.cursor()
                    cursor.execute("SELECT id FROM resep WHERE nama_resep=%s", (pilih_r,))
                    r_id = cursor.fetchone()[0]
                    df_det = pd.read_sql_query(f'SELECT nama_bahan as "Nama Bahan", jumlah_pakai as "Jumlah Pakai", satuan as "Satuan", subtotal_biaya as "Subtotal" FROM detail_resep WHERE resep_id={r_id}', conn)
                    st.session_state.racikan_sementara = df_det
                    st.session_state.edit_resep_nama = pilih_r
                    st.success("Berhasil ditarik! Silakan edit di tab 'Dapur (Racik Resep)'.")
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
