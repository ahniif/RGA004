import streamlit as st
import pandas as pd
# KOREKSI IMPOR: service_account_from_dict adalah cara yang benar
from gspread import Client, Spreadsheet
from gspread.service_account import service_account_from_dict # BARIS KOREKSI
from gspread_dataframe import set_with_dataframe, get_dataframe
import random
import json
import numpy as np

# --- KONFIGURASI GOOGLE SHEETS & INIT ---

# URL Google Sheet Anda
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1zNae6GRrJ1N1OlB0XfhnaBnkq22CW8-Bga5dLIGGda8/edit?usp=sharing"

@st.cache_resource(ttl=3600) # Cache koneksi klien selama 1 jam
def get_sheet_client():
    """Menginisialisasi koneksi gspread menggunakan Streamlit Secrets."""
    try:
        # Mengambil secrets dari st.secrets 
        secrets = st.secrets["gcp_service_account"]
        
        # Jika secrets adalah string (format JSON di Streamlit Cloud), parse dulu
        if isinstance(secrets, str):
            secrets = json.loads(secrets)
            
        # KOREKSI UTAMA LOGIKA: Mendapatkan Service Account Client dari dictionary secrets
        # service_account_info() yang lama diganti dengan service_account_from_dict()
        gc = service_account_from_dict(secrets)

        # gc adalah Client object, yang bisa membuka spreadsheet
        return gc.open_by_url(GOOGLE_SHEET_URL)
        
    except Exception as e:
        st.error(f"Gagal koneksi ke Google Sheets. Pastikan secrets dan URL sudah benar. Error: {e}")
        st.stop()
        return None

# --- FUNGSI LOAD & SAVE DATA ---

def load_data(sheet_name):
    """Memuat data dari sheet tertentu sebagai DataFrame."""
    try:
        sh = get_sheet_client()
        wks = sh.worksheet(sheet_name)
        
        # Load data, konversi kolom ID, dan set index
        df = get_dataframe(wks).dropna(how='all')
        
        if df.empty:
             # Membuat DataFrame kosong dengan kolom yang benar
             if sheet_name == 'Pemain':
                 return pd.DataFrame(columns=['ID', 'Nama', 'Total_Poin', 'Games_Played', 'Total_Bye', 'W', 'L', 'T']).set_index('ID')
             if sheet_name == 'Jadwal':
                 return pd.DataFrame(columns=['Match_ID', 'Putaran', 'Lapangan', 'Mode', 'Pemain_1_A', 'Pemain_1_B', 'Pemain_2_A', 'Pemain_2_B', 'Poin_Tim_1', 'Poin_Tim_2', 'Status']).set_index('Match_ID')
             return pd.DataFrame()
             
        
        # Konversi kolom ID yang relevan ke integer dan set index
        if sheet_name == 'Pemain':
            df['ID'] = df['ID'].astype(int, errors='ignore')
            df = df.set_index('ID')
        elif sheet_name == 'Jadwal':
            df['Match_ID'] = df['Match_ID'].astype(int, errors='ignore')
            df['Pemain_1_A'] = df['Pemain_1_A'].fillna(0).astype(int, errors='ignore')
            df['Pemain_1_B'] = df['Pemain_1_B'].fillna(0).astype(int, errors='ignore')
            df['Pemain_2_A'] = df['Pemain_2_A'].fillna(0).astype(int, errors='ignore')
            df['Pemain_2_B'] = df['Pemain_2_B'].fillna(0).astype(int, errors='ignore')
            df = df.set_index('Match_ID')
            
        return df

    except Exception as e:
        st.error(f"Error memuat data dari Sheets '{sheet_name}'. Cek nama sheet dan izin akses. {e}")
        return pd.DataFrame()

@st.cache_data(show_spinner=False)
def save_data(df, sheet_name):
    """Menyimpan DataFrame ke sheet tertentu."""
    try:
        sh = get_sheet_client()
        wks = sh.worksheet(sheet_name)
        
        # Mengubah indeks menjadi kolom sebelum menyimpan
        df_to_save = df.reset_index()
        
        # Mengganti NaN dengan string kosong atau nol agar gspread tidak error
        df_to_save = df_to_save.fillna(value='')
        
        # Hapus data lama dan simpan yang baru
        wks.clear()
        set_with_dataframe(wks, df_to_save)
        
        # Setelah save, clear cache untuk memuat data baru
        load_data.clear()
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Error menyimpan data ke Sheets: {e}")
        return False

# --- FUNGSI UTILITY ---

def get_next_id(df, id_col_name):
    """Mendapatkan ID berikutnya berdasarkan kolom ID di DataFrame."""
    if df.empty or id_col_name not in df.index.names:
        return 1
    return df.index.max() + 1

def hitung_wlt(pemain_df_copy, jadwal_df_copy):
    """Menghitung Win/Lose/Tie dari DataFrame data yang sudah di-fetch."""
    if 'W' not in pemain_df_copy.columns:
        pemain_df_copy['W'] = 0
        pemain_df_copy['L'] = 0
        pemain_df_copy['T'] = 0

    pemain_df_copy['W'] = 0
    pemain_df_copy['L'] = 0
    pemain_df_copy['T'] = 0
    
    jadwal_selesai = jadwal_df_copy[jadwal_df_copy['Status'] == 'Selesai']
    
    for _, match in jadwal_selesai.iterrows():
        # Pastikan ID adalah integer dan bukan NaN
        p1a = int(match['Pemain_1_A']) if pd.notna(match['Pemain_1_A']) and match['Pemain_1_A'] else None
        p1b = int(match['Pemain_1_B']) if pd.notna(match['Pemain_1_B']) and match['Pemain_1_B'] else None
        p2a = int(match['Pemain_2_A']) if pd.notna(match['Pemain_2_A']) and match['Pemain_2_A'] else None
        p2b = int(match['Pemain_2_B']) if pd.notna(match['Pemain_2_B']) and match['Pemain_2_B'] else None

        poin1, poin2 = match['Poin_Tim_1'], match['Poin_Tim_2']
        
        pemain_tim_1 = [p for p in [p1a, p1b] if p is not None]
        pemain_tim_2 = [p for p in [p2a, p2b] if p is not None]
        
        if poin1 > poin2:
            for p_id in pemain_tim_1:
                if p_id in pemain_df_copy.index: pemain_df_copy.loc[p_id, 'W'] += 1
            for p_id in pemain_tim_2:
                if p_id in pemain_df_copy.index: pemain_df_copy.loc[p_id, 'L'] += 1
        elif poin2 > poin1:
            for p_id in pemain_tim_2:
                if p_id in pemain_df_copy.index: pemain_df_copy.loc[p_id, 'W'] += 1
            for p_id in pemain_tim_1:
                if p_id in pemain_df_copy.index: pemain_df_copy.loc[p_id, 'L'] += 1
        else: # Seri
            pemain_all = pemain_tim_1 + pemain_tim_2
            for p_id in pemain_all:
                if p_id in pemain_df_copy.index: pemain_df_copy.loc[p_id, 'T'] += 1
                    
    return pemain_df_copy


def buat_jadwal(pemain_df, putaran, num_lapangan, mode_permainan, format_turnamen):
    """Membuat jadwal baru."""
    
    if 'Total_Bye' not in pemain_df.columns:
         pemain_df['Total_Bye'] = 0
         
    pemain_df['Rank_Poin'] = pemain_df['Total_Poin'].rank(method='min', ascending=False)
    
    pemain_aktif_sorted = pemain_df.sort_values(
        by=['Total_Bye', 'Rank_Poin'], 
        ascending=[False, False] 
    ).index.tolist()
    
    players_per_court = 4 if mode_permainan == 'Double' else 2
    total_slots = num_lapangan * players_per_court
    
    pemain_potensial = pemain_aktif_sorted[:total_slots]
    
    pemain_yang_bermain_count = len(pemain_potensial) - (len(pemain_potensial) % players_per_court)
    pemain_bermain = pemain_potensial[:pemain_yang_bermain_count]
    
    if len(pemain_bermain) < players_per_court:
        return []

    jadwal_baru = []
    jadwal_df_full = load_data('Jadwal')
    next_match_id = get_next_id(jadwal_df_full, 'Match_ID')
    
    # --- AMERICANO (Acak) ---
    if format_turnamen == 'Americano':
        random.shuffle(pemain_bermain)
        
        for i in range(0, len(pemain_bermain), players_per_court):
            grup_pemain = pemain_bermain[i:i+players_per_court]
            
            if len(grup_pemain) == players_per_court:
                lapangan_num = (i // players_per_court) + 1
                
                if mode_permainan == 'Double':
                    P1A, P1B, P2A, P2B = grup_pemain
                else: # Single
                    P1A, P2A = grup_pemain
                    P1B, P2B = None, None
                
                match_data = {
                    'Match_ID': next_match_id,
                    'Putaran': putaran,
                    'Lapangan': lapangan_num,
                    'Mode': mode_permainan,
                    'Pemain_1_A': P1A, 'Pemain_1_B': P1B,
                    'Pemain_2_A': P2A, 'Pemain_2_B': P2B,
                    'Poin_Tim_1': 0, 'Poin_Tim_2': 0,
                    'Status': 'Belum Selesai'
                }
                jadwal_baru.append(match_data)
                next_match_id += 1
        
    # --- MEXICANO (Peringkat) ---
    elif format_turnamen == 'Mexicano':
        
        pemain_bermain_df_sorted = pemain_df.loc[pemain_bermain].sort_values(
            by=['Total_Poin', 'ID'], ascending=[False, True]
        ).index.tolist()
        
        mid_point = len(pemain_bermain_df_sorted) // 2
        peringkat_tinggi = pemain_bermain_df_sorted[:mid_point]
        peringkat_rendah = pemain_bermain_df_sorted[mid_point:]
        
        random.shuffle(peringkat_tinggi)
        random.shuffle(peringkat_rendah)
        
        num_matches = len(pemain_bermain_df_sorted) // 2
        
        for i in range(num_matches):
            lapangan_num = i + 1
            
            # Memastikan tidak ada IndexError
            if i >= len(peringkat_tinggi) or i >= len(peringkat_rendah):
                 continue

            if mode_permainan == 'Double':
                if i*2 + 1 < len(peringkat_tinggi) and i*2 + 1 < len(peringkat_rendah):
                    H1, H2 = peringkat_tinggi[i*2], peringkat_tinggi[i*2 + 1]
                    L1, L2 = peringkat_rendah[i*2], peringkat_rendah[i*2 + 1]
                    P1A, P1B, P2A, P2B = H1, L1, H2, L2 
                else:
                    continue 
            
            elif mode_permainan == 'Single':
                P1A = peringkat_tinggi[i]
                P2A = peringkat_rendah[i]
                P1B, P2B = None, None

            match_data = {
                'Match_ID': next_match_id,
                'Putaran': putaran,
                'Lapangan': lapangan_num,
                'Mode': mode_permainan,
                'Pemain_1_A': P1A, 'Pemain_1_B': P1B,
                'Pemain_2_A': P2A, 'Pemain_2_B': P2B,
                'Poin_Tim_1': 0, 'Poin_Tim_2': 0,
                'Status': 'Belum Selesai'
            }
            jadwal_baru.append(match_data)
            next_match_id += 1
            
    return jadwal_baru

# --- FUNGSI AKSI (Menggunakan Session State untuk sementara dan Save ke Sheets) ---

def tambah_pemain_action(nama):
    pemain_df = load_data('Pemain')
    if nama and len(pemain_df) < 32:
        new_id = get_next_id(pemain_df, 'ID')
        
        new_row = pd.DataFrame([{
            'Nama': nama, 
            'Total_Poin': 0, 'Games_Played': 0, 'Total_Bye': 0, 
            'W': 0, 'L': 0, 'T': 0
        }], index=[new_id])
        new_row.index.name = 'ID'
        
        pemain_df = pd.concat([pemain_df, new_row])
        save_data(pemain_df, 'Pemain')
        st.success(f"Pemain '{nama}' berhasil ditambahkan.")

def hapus_pemain_action(player_id):
    pemain_df = load_data('Pemain')
    jadwal_df = load_data('Jadwal')
    
    if player_id in pemain_df.index:
        # Hapus pemain
        pemain_df.drop(player_id, inplace=True)
        
        # Hapus match yang melibatkan pemain tersebut
        cols_to_check = ['Pemain_1_A', 'Pemain_1_B', 'Pemain_2_A', 'Pemain_2_B']
        
        # Hapus match yang ID pemainnya ada di kolom manapun
        mask = jadwal_df.apply(lambda row: any(row[col] == player_id for col in cols_to_check), axis=1)
        jadwal_df = jadwal_df[~mask]
        
        save_data(pemain_df, 'Pemain')
        save_data(jadwal_df, 'Jadwal')
        st.success("Pemain dan jadwal terkait berhasil dihapus.")

def mulai_putaran_action(num_lapangan, format_turnamen, mode_permainan):
    pemain_df = load_data('Pemain')
    jadwal_df = load_data('Jadwal')
    
    putaran_saat_ini = jadwal_df['Putaran'].max() if not jadwal_df.empty else 0
    new_putaran = putaran_saat_ini + 1

    players_per_court = 4 if mode_permainan == 'Double' else 2

    if len(pemain_df) < players_per_court:
        st.warning(f"Minimal {players_per_court} pemain diperlukan untuk mode {mode_permainan}.")
        return

    # Hitung Total_Bye dan update
    pemain_bermain_sebelumnya_id = set(jadwal_df[jadwal_df['Putaran'] == putaran_saat_ini][['Pemain_1_A', 'Pemain_1_B', 'Pemain_2_A', 'Pemain_2_B']].stack().dropna().tolist())
    pemain_bye_ids = [id for id in pemain_df.index.tolist() if id not in pemain_bermain_sebelumnya_id]
    
    for id in pemain_bye_ids:
        if id in pemain_df.index:
             pemain_df.loc[id, 'Total_Bye'] += 1
    
    # Simpan konfigurasi putaran saat ini
    st.session_state['last_config'] = {
        'num_lapangan': num_lapangan,
        'format_turnamen': format_turnamen,
        'mode_permainan': mode_permainan
    }
    
    new_matches = buat_jadwal(pemain_df, new_putaran, num_lapangan, mode_permainan, format_turnamen)
    
    if new_matches:
        new_jadwal_df = pd.DataFrame(new_matches).set_index('Match_ID')
        new_jadwal_df.index.name = 'Match_ID'
        
        # Pastikan kolom-kolom pemain yang kosong diisi None/np.nan
        for col in ['Pemain_1_B', 'Pemain_2_B']:
            if col not in new_jadwal_df.columns:
                 new_jadwal_df[col] = np.nan
        
        jadwal_df = pd.concat([jadwal_df, new_jadwal_df])
        
        save_data(pemain_df, 'Pemain')
        save_data(jadwal_df, 'Jadwal')
        st.success(f"Jadwal Putaran {new_putaran} berhasil dibuat!")
    else:
        st.warning("Tidak cukup pemain untuk membuat jadwal.")


def kocok_ulang_action(putaran_saat_ini, num_lapangan, mode_permainan):
    pemain_df = load_data('Pemain')
    jadwal_df = load_data('Jadwal')
    
    # 1. Hapus match putaran saat ini yang belum selesai
    jadwal_df_lama = jadwal_df[jadwal_df['Putaran'] != putaran_saat_ini]
    
    # 2. Buat jadwal baru (selalu Americano saat kocok ulang)
    format_turnamen = 'Americano'
    
    new_matches = buat_jadwal(pemain_df, putaran_saat_ini, num_lapangan, mode_permainan, format_turnamen)

    if new_matches:
        new_jadwal_df = pd.DataFrame(new_matches).set_index('Match_ID')
        new_jadwal_df.index.name = 'Match_ID'
        
        jadwal_df_baru = pd.concat([jadwal_df_lama, new_jadwal_df])
        save_data(jadwal_df_baru, 'Jadwal')
        st.success("Jadwal putaran saat ini berhasil dikocok ulang.")
    else:
        st.error("Gagal mengocok ulang. Cek jumlah pemain.")
        
def input_skor_action(match_id, skor_tim_1, skor_tim_2):
    pemain_df = load_data('Pemain')
    jadwal_df = load_data('Jadwal')
    putaran_saat_ini = jadwal_df['Putaran'].max() if not jadwal_df.empty else 0
    
    if match_id in jadwal_df.index:
        match_row = jadwal_df.loc[match_id]
        
        p1a = int(match_row['Pemain_1_A']) if pd.notna(match_row['Pemain_1_A']) and match_row['Pemain_1_A'] else None
        p1b = int(match_row['Pemain_1_B']) if pd.notna(match_row['Pemain_1_B']) and match_row['Pemain_1_B'] else None
        p2a = int(match_row['Pemain_2_A']) if pd.notna(match_row['Pemain_2_A']) and match_row['Pemain_2_A'] else None
        p2b = int(match_row['Pemain_2_B']) if pd.notna(match_row['Pemain_2_B']) and match_row['Pemain_2_B'] else None

        pemain_ids_team_1 = [id for id in [p1a, p1b] if id is not None]
        pemain_ids_team_2 = [id for id in [p2a, p2b] if id is not None]
        
        poin_lama_tim_1 = match_row['Poin_Tim_1'] if match_row['Status'] == 'Selesai' else 0
        poin_lama_tim_2 = match_row['Poin_Tim_2'] if match_row['Status'] == 'Selesai' else 0
        
        games_played_change = (skor_tim_1 + skor_tim_2) - (poin_lama_tim_1 + poin_lama_tim_2)
        
        # Update Poin dan Games Played Pemain
        for id in pemain_ids_team_1:
            pemain_df.loc[id, 'Total_Poin'] = pemain_df.loc[id, 'Total_Poin'] - poin_lama_tim_1 + skor_tim_1
            pemain_df.loc[id, 'Games_Played'] = pemain_df.loc[id, 'Games_Played'] + games_played_change
        
        for id in pemain_ids_team_2:
            pemain_df.loc[id, 'Total_Poin'] = pemain_df.loc[id, 'Total_Poin'] - poin_lama_tim_2 + skor_tim_2
            pemain_df.loc[id, 'Games_Played'] = pemain_df.loc[id, 'Games_Played'] + games_played_change
            
        # Update Jadwal
        jadwal_df.loc[match_id, ['Poin_Tim_1', 'Poin_Tim_2', 'Status']] = [skor_tim_1, skor_tim_2, 'Selesai']
        
        save_data(pemain_df, 'Pemain')
        save_data(jadwal_df, 'Jadwal')
        
        st.success("Skor berhasil disimpan dan Total Poin pemain diperbarui.")
        
        # --- Cek Otomatis Buat Putaran Berikutnya ---
        current_round_matches = jadwal_df[jadwal_df['Putaran'] == putaran_saat_ini]
        if not current_round_matches.empty and (current_round_matches['Status'] == 'Selesai').all():
            st.info("Semua pertandingan di putaran ini selesai. Membuat jadwal putaran berikutnya...")
            
            # Gunakan config terakhir yang disimpan di session state
            config = st.session_state.get('last_config', {'num_lapangan': 1, 'format_turnamen': 'Americano', 'mode_permainan': 'Double'})
            mulai_putaran_action(config['num_lapangan'], config['format_turnamen'], config['mode_permainan'])
        

# --- ANTARMUKA UTAMA STREAMLIT ---

def main_app():
    
    st.set_page_config(page_title="Tenis Scoring", layout="wide")

    # Ambil data terbaru dari Sheets
    pemain_df_full = load_data('Pemain')
    jadwal_df_full = load_data('Jadwal')
    
    putaran_saat_ini = jadwal_df_full['Putaran'].max() if not jadwal_df_full.empty else 0
    jadwal_saat_ini = jadwal_df_full[jadwal_df_full['Putaran'] == putaran_saat_ini]
    
    # Tentukan konfigurasi putaran saat ini
    if not jadwal_saat_ini.empty:
        current_mode = jadwal_saat_ini['Mode'].iloc[0]
        # Ini hanya perkiraan, karena format tidak disimpan
        current_format = "Americano" if current_mode == 'Double' else "Mexicano" 
        num_lapangan = len(jadwal_saat_ini['Lapangan'].unique())
        st.session_state['last_config'] = {'num_lapangan': num_lapangan, 'format_turnamen': current_format, 'mode_permainan': current_mode}
    else:
         current_mode = "Double"
         current_format = "Americano"

    # --- HEADER & STYLING ---
    st.markdown(
        """
        <style>
        .header-box {
            background-color: #460046; /* purple */
            color: #ffffff;
            padding: 15px;
            text-align: center;
            font-size: 2.2em;
            font-weight: 900;
            font-family: 'Playfair Display', serif;
        }
        .sub-header-haniif {
            background-color: #006400; /* green */
            color: #ffd700; /* gold */
            padding: 5px;
            font-size: 0.9em;
            font-weight: 600;
            letter-spacing: 1px;
        }
        .bye-info {
            background-color: #ffe0b2;
            padding: 10px;
            border-radius: 5px;
            border-left: 5px solid #ff9800;
            margin-bottom: 10px;
        }
        </style>
        """, 
        unsafe_allow_html=True
    )
    
    st.markdown(f'<div class="sub-header-haniif">Tournament Manager: **Haniif\'s Edition**</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="header-box">Tenis Scoring</div>', unsafe_allow_html=True)
    st.write("---")
    
    
    # --- BAGIAN TAMBAH PEMAIN ---
    st.subheader('👥 Tambah Pemain')
    col_input, col_btn = st.columns([3, 1])
    with col_input:
        nama_pemain = st.text_input("Nama Pemain Baru", key="input_nama", label_visibility="collapsed", placeholder="Nama Pemain Baru")
    with col_btn:
        if st.button("➕ Tambah Pemain", use_container_width=True):
            if nama_pemain:
                tambah_pemain_action(nama_pemain)
                st.rerun()
            else:
                 st.warning("Masukkan nama pemain.")
    
    # --- BAGIAN PERINGKAT ---
    st.subheader('📊 Peringkat Saat Ini')
    if not pemain_df_full.empty:
        # Hitung W/L/T dan Peringkat
        peringkat_df = hitung_wlt(pemain_df_full.copy(), jadwal_df_full.copy())
        peringkat_df['Peringkat'] = peringkat_df['Total_Poin'].rank(method='min', ascending=False).astype(int)
        peringkat_df = peringkat_df.sort_values(by=['Peringkat', 'Total_Poin'], ascending=[True, False])
        
        kolom_tampil = ['Peringkat', 'Nama', 'Total_Poin', 'W', 'L', 'T', 'Games_Played']
        
        st.dataframe(
            peringkat_df[kolom_tampil].reset_index(names=['ID']),
            hide_index=True,
            column_order=kolom_tampil
        )
        
        # Form Hapus Pemain
        with st.expander("Hapus Pemain"):
            player_to_delete = st.selectbox(
                "Pilih pemain yang akan dihapus:", 
                options=peringkat_df.reset_index().set_index('ID')['Nama'],
                key="del_player"
            )
            if st.button("❌ Hapus Pemain Terpilih", help="Menghapus pemain akan menghapus semua data dan jadwal terkait."):
                if st.warning("Apakah Anda yakin? Data akan hilang secara permanen."):
                     hapus_pemain_action(st.session_state.del_player)
                     st.rerun()

    else:
        st.info("Belum ada pemain terdaftar.")
    
    st.write("---")

    # --- BAGIAN MULAI PUTARAN ---
    st.subheader(f'🚀 Atur Putaran Berikutnya (Putaran {putaran_saat_ini + 1})')
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        mode = st.selectbox("Mode Permainan:", ['Double', 'Single'], key="mode_pilih")
    with col2:
        format_turn = st.selectbox("Format Turnamen:", ['Americano', 'Mexicano'], key="format_pilih")
    with col3:
        lapangan = st.selectbox("Jumlah Lapangan:", [1, 2, 3, 4], key="lapangan_pilih")
    with col4:
        st.write("") # Spacer
        if st.button(f"Buat Jadwal Putaran {putaran_saat_ini + 1}", type="primary", use_container_width=True):
            mulai_putaran_action(lapangan, format_turn, mode)
            st.rerun()
            
    st.write("---")

    # --- BAGIAN JADWAL SAAT INI ---
    if putaran_saat_ini > 0 and not jadwal_saat_ini.empty:
        
        st.subheader(f'📅 Jadwal Putaran {putaran_saat_ini} (Mode: {current_mode} — Lapangan: {num_lapangan})')

        pemain_yang_bermain_id = set(jadwal_saat_ini[['Pemain_1_A', 'Pemain_1_B', 'Pemain_2_A', 'Pemain_2_B']].stack().dropna().tolist())
        pemain_bye_ids = [id for id in pemain_df_full.index.tolist() if id not in pemain_yang_bermain_id]
        
        if pemain_bye_ids:
            pemain_bye_nama = pemain_df_full.loc[pemain_bye_ids]['Nama'].tolist()
            st.markdown(f'<div class="bye-info">👋 **Bye (Tidak Bermain) di Putaran Ini:** {", ".join(pemain_bye_nama)}</div>', unsafe_allow_html=True)
            
        
        can_reshuffle = (jadwal_saat_ini['Status'] == 'Belum Selesai').all()
        
        if can_reshuffle:
            if st.button("🔄 Kocok Ulang Putaran Ini (Americano)", help="Hanya bisa dilakukan jika belum ada skor yang masuk."):
                kocok_ulang_action(putaran_saat_ini, num_lapangan, current_mode)
                st.rerun()

        for match_id, match in jadwal_saat_ini.iterrows():
            
            p1a = int(match['Pemain_1_A']) if pd.notna(match['Pemain_1_A']) and match['Pemain_1_A'] else None
            p1b = int(match['Pemain_1_B']) if pd.notna(match['Pemain_1_B']) and match['Pemain_1_B'] else None
            p2a = int(match['Pemain_2_A']) if pd.notna(match['Pemain_2_A']) and match['Pemain_2_A'] else None
            p2b = int(match['Pemain_2_B']) if pd.notna(match['Pemain_2_B']) and match['Pemain_2_B'] else None

            
            nama_p1a = pemain_df_full.loc[p1a, 'Nama'] if p1a in pemain_df_full.index else 'N/A'
            nama_p1b = pemain_df_full.loc[p1b, 'Nama'] if p1b in pemain_df_full.index else ''
            nama_p2a = pemain_df_full.loc[p2a, 'Nama'] if p2a in pemain_df_full.index else 'N/A'
            nama_p2b = pemain_df_full.loc[p2b, 'Nama'] if p2b in pemain_df_full.index else ''
            
            with st.container(border=True):
                st.markdown(f"**Lapangan {match.Lapangan}** | Status: **{match.Status}**", unsafe_allow_html=True)
                
                if match.Mode == 'Double':
                    team1 = f"**{nama_p1a} & {nama_p1b}**"
                    team2 = f"**{nama_p2a} & {nama_p2b}**"
                else:
                    team1 = f"**{nama_p1a}**"
                    team2 = f"**{nama_p2a}**"

                st.markdown(f"**Pertandingan:** 💜 Tim 1 ({team1}) vs 💚 Tim 2 ({team2})")

                col_s1, col_s2, col_btn_s = st.columns([1, 1, 1])
                
                with col_s1:
                    skor_1 = st.number_input(f"Skor Tim 1 (💜) - Match {match_id}", value=int(match.Poin_Tim_1), min_value=0, key=f"s1_{match_id}")
                with col_s2:
                    skor_2 = st.number_input(f"Skor Tim 2 (💚) - Match {match_id}", value=int(match.Poin_Tim_2), min_value=0, key=f"s2_{match_id}")
                with col_btn_s:
                    st.write("")
                    if st.button("Simpan/Update Skor", key=f"btn_{match_id}", type="secondary", use_container_width=True):
                        input_skor_action(match_id, skor_1, skor_2)
                        st.rerun()

    else:
        st.info("Belum ada jadwal putaran aktif.")
        
    st.write("---")
    
    # --- AKHIRI TURNAMEN (Rekap Visual) ---
    st.subheader('🛑 Rekap Skor Akhir')
    if putaran_saat_ini > 0:
        st.info("Data final sudah ditampilkan di bagian 'Peringkat Saat Ini'.")
    else:
        st.warning("Mulai setidaknya satu putaran untuk melihat rekap final.")

if __name__ == '__main__':
    # Initialize session state for first run
    if 'last_config' not in st.session_state:
        st.session_state['last_config'] = {'num_lapangan': 1, 'format_turnamen': 'Americano', 'mode_permainan': 'Double'}
    
    main_app()