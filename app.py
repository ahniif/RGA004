import random
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, Response

# --- Konfigurasi Turnamen ---
MAX_PEMAIN = 32

# Inisialisasi Aplikasi Flask
app = Flask(__name__)

# --- Manajemen Data dengan Pandas (Simulasi Database) ---
if 'pemain_df' not in globals():
    # 'Total_Poin' di sini adalah Cumulative Score. 'Ranking_Poin' adalah W - L.
    pemain_df = pd.DataFrame(columns=['ID', 'Nama', 'Total_Poin', 'Games_Played', 'Total_Bye', 'W', 'L', 'T', 'Ranking_Poin'])
    pemain_df = pemain_df.set_index('ID')

if 'jadwal_df' not in globals():
    jadwal_df = pd.DataFrame(columns=['Putaran', 'Lapangan', 'Mode', 'Pemain_1_A', 'Pemain_1_B', 'Pemain_2_A', 'Pemain_2_B', 'Poin_Tim_1', 'Poin_Tim_2', 'Status'])
    jadwal_df.index.name = 'Match_ID' 

if 'next_player_id' not in globals():
    next_player_id = 1

if 'putaran_saat_ini' not in globals():
    putaran_saat_ini = 0

if 'next_match_id' not in globals():
    next_match_id = 1

if 'last_config' not in globals():
    last_config = {
        'num_lapangan': 1,
        'format_turnamen': 'Americano', 
        'mode_permainan': 'Double'
    }

# --- Fungsi Utility ---
def get_next_player_id():
    global next_player_id
    current_id = next_player_id
    next_player_id += 1
    return current_id

def get_next_match_id():
    global next_match_id
    current_id = next_match_id
    next_match_id += 1
    return current_id

def get_player_id(id_value):
    """Fungsi bantuan untuk mengonversi ID pemain menjadi integer yang aman."""
    if pd.notna(id_value):
        try:
            # Konversi eksplisit ke integer
            return int(id_value) 
        except (ValueError, TypeError):
            return None
    return None

def safe_get_player_id_list(id_list):
    """Fungsi bantuan untuk mengonversi list ID pemain menjadi integer yang aman."""
    cleaned_ids = []
    for id_value in id_list:
        p_id = get_player_id(id_value)
        if p_id is not None:
            cleaned_ids.append(p_id)
    return cleaned_ids
    
def hitung_wlt(pemain_df_input, jadwal_df_input):
    """
    Menghitung Win/Lose/Tie dan Ranking_Poin (W - L) 
    berdasarkan semua pertandingan Selesai.
    """
    
    pemain_df = pemain_df_input.copy()
    jadwal_df = jadwal_df_input.copy()
    
    # Inisialisasi kolom W/L/T dan Reset nilai untuk perhitungan baru
    for col in ['W', 'L', 'T']:
        if col not in pemain_df.columns:
            pemain_df[col] = 0
        pemain_df[col] = 0
    
    jadwal_selesai = jadwal_df[jadwal_df['Status'] == 'Selesai']
    
    for _, match in jadwal_selesai.iterrows():
        # Dapatkan ID pemain, pastikan bertipe integer jika valid
        p1a = get_player_id(match['Pemain_1_A'])
        p1b = get_player_id(match['Pemain_1_B'])
        p2a = get_player_id(match['Pemain_2_A'])
        p2b = get_player_id(match['Pemain_2_B'])
        
        poin1, poin2 = match['Poin_Tim_1'], match['Poin_Tim_2']
        
        # Pisahkan pemain tim 1 dan tim 2
        pemain_tim_1 = [p for p in [p1a, p1b] if p is not None]
        pemain_tim_2 = [p for p in [p2a, p2b] if p is not None]
        
        # Filtering agar hanya ID yang ada di index pemain_df yang dihitung
        pemain_tim_1 = [p for p in pemain_tim_1 if p in pemain_df.index]
        pemain_tim_2 = [p for p in pemain_tim_2 if p in pemain_df.index]
        
        if poin1 > poin2:
            # Tim 1 Menang, Tim 2 Kalah
            for p_id in pemain_tim_1:
                pemain_df.loc[p_id, 'W'] += 1
            for p_id in pemain_tim_2:
                pemain_df.loc[p_id, 'L'] += 1
        elif poin2 > poin1:
            # Tim 2 Menang, Tim 1 Kalah
            for p_id in pemain_tim_2:
                pemain_df.loc[p_id, 'W'] += 1
            for p_id in pemain_tim_1:
                pemain_df.loc[p_id, 'L'] += 1
        else:
            # Seri/Tie (poin1 == poin2)
            pemain_all = pemain_tim_1 + pemain_tim_2
            for p_id in pemain_all:
                pemain_df.loc[p_id, 'T'] += 1
                
    # --- KRUSIAL: Implementasi Ranking Poin = W - L ---
    if 'W' in pemain_df.columns and 'L' in pemain_df.columns:
        pemain_df['Ranking_Poin'] = pemain_df['W'] - pemain_df['L']
    else:
        pemain_df['Ranking_Poin'] = 0
                    
    return pemain_df
    
def buat_jadwal(pemain_df, putaran, num_lapangan, mode_permainan, format_turnamen):
    """
    Membuat jadwal baru dengan logika prioritas yang lebih adil.
    """
    # Pastikan kolom-kolom untuk sorting ada
    if 'Total_Bye' not in pemain_df.columns: pemain_df['Total_Bye'] = 0
    if 'Games_Played' not in pemain_df.columns: pemain_df['Games_Played'] = 0
    
    # Tambahkan atau perbarui Random_Tie_Breaker
    if 'Random_Tie_Breaker' not in pemain_df.columns or putaran % 5 == 1: # Regenerasi setiap 5 putaran
        pemain_df['Random_Tie_Breaker'] = [random.random() for _ in range(len(pemain_df))]
        
    # Perhitungan W/L/T dan Ranking_Poin sebelum sorting
    pemain_df_temp = hitung_wlt(pemain_df.copy(), jadwal_df.copy())
    
    # Kriteria Sorting Prioritas: 
    # Total_Bye DESC (Pemain yang paling sering bye diprioritaskan untuk bermain), 
    # Games_Played ASC (Pemain yang paling sedikit bermain diprioritaskan), 
    # Ranking_Poin DESC (Pemain dengan W-L tertinggi diprioritaskan), 
    # Random_Tie_Breaker ASC
    pemain_aktif_sorted = pemain_df_temp.sort_values(
        by=['Total_Bye', 'Games_Played', 'Ranking_Poin', 'Random_Tie_Breaker'], 
        ascending=[False, True, False, True] 
    ).index.tolist()
    
    players_per_court = 4 if mode_permainan == 'Double' else 2
    total_slots = num_lapangan * players_per_court
    
    pemain_potensial = pemain_aktif_sorted[:total_slots]
    
    pemain_yang_bermain_count = len(pemain_potensial) - (len(pemain_potensial) % players_per_court)
    pemain_bermain_ids = pemain_potensial[:pemain_yang_bermain_count]
    
    pemain_bermain = pemain_bermain_ids

    if len(pemain_bermain) < players_per_court:
        return []

    jadwal_baru = []
    
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
                    'Match_ID': get_next_match_id(),
                    'Putaran': putaran,
                    'Lapangan': lapangan_num,
                    'Mode': mode_permainan,
                    'Pemain_1_A': P1A, 'Pemain_1_B': P1B,
                    'Pemain_2_A': P2A, 'Pemain_2_B': P2B,
                    'Poin_Tim_1': 0, 'Poin_Tim_2': 0,
                    'Status': 'Belum Selesai'
                }
                jadwal_baru.append(match_data)
    
    # --- MEXICANO (Peringkat) ---
    elif format_turnamen == 'Mexicano':
        
        # Sorting Ulang berdasarkan Ranking_Poin untuk pairing Mexicano
        pemain_bermain_df_sorted = pemain_df_temp.loc[pemain_bermain].sort_values(
            by='Ranking_Poin', ascending=False
        ).index.tolist()
        
        mid_point = len(pemain_bermain_df_sorted) // 2
        peringkat_tinggi = pemain_bermain_df_sorted[:mid_point]
        peringkat_rendah = pemain_bermain_df_sorted[mid_point:]
        
        random.shuffle(peringkat_tinggi)
        random.shuffle(peringkat_rendah)
        
        if mode_permainan == 'Double':
            
            num_matches = len(peringkat_tinggi) // 2 
            
            for i in range(num_matches):
                H1 = peringkat_tinggi.pop(0)
                H2 = peringkat_tinggi.pop(0)
                L1 = peringkat_rendah.pop(0)
                L2 = peringkat_rendah.pop(0)

                # Pair: H1 & L1 vs H2 & L2
                P1A, P1B, P2A, P2B = H1, L1, H2, L2 
                
                lapangan_num = i + 1
                
                match_data = {
                    'Match_ID': get_next_match_id(),
                    'Putaran': putaran,
                    'Lapangan': lapangan_num,
                    'Mode': mode_permainan,
                    'Pemain_1_A': P1A, 'Pemain_1_B': P1B,
                    'Pemain_2_A': P2A, 'Pemain_2_B': P2B,
                    'Poin_Tim_1': 0, 'Poin_Tim_2': 0,
                    'Status': 'Belum Selesai'
                }
                jadwal_baru.append(match_data)
        
        elif mode_permainan == 'Single':
            
            num_matches = len(peringkat_tinggi)
            for i in range(num_matches):
                P1A = peringkat_tinggi[i]
                P2A = peringkat_rendah[i]
                
                lapangan_num = i + 1
                
                match_data = {
                    'Match_ID': get_next_match_id(),
                    'Putaran': putaran,
                    'Lapangan': lapangan_num,
                    'Mode': mode_permainan,
                    'Pemain_1_A': P1A, 'Pemain_1_B': None,
                    'Pemain_2_A': P2A, 'Pemain_2_B': None,
                    'Poin_Tim_1': 0, 'Poin_Tim_2': 0,
                    'Status': 'Belum Selesai'
                }
                jadwal_baru.append(match_data)
            
    return jadwal_baru

# ----------------------------------------------------
#                    ROUTE APLIKASI
# ----------------------------------------------------

@app.route('/')
def index():
    global pemain_df, jadwal_df, putaran_saat_ini, last_config

    # Inisialisasi kolom W/L/T, Games_Played, Total_Bye jika belum ada
    for col in ['W', 'L', 'T', 'Games_Played', 'Total_Bye', 'Ranking_Poin', 'Random_Tie_Breaker']:
         if col not in pemain_df.columns:
              pemain_df[col] = 0
    
    peringkat = pd.DataFrame()
    if not pemain_df.empty:
        # Panggil fungsi W/L/T dan Ranking_Poin (W-L)
        pemain_df_temp = hitung_wlt(pemain_df.copy(), jadwal_df.copy())
        
        peringkat = pemain_df_temp.copy()
        
        # --- KRUSIAL: LOGIKA RANKING BARU ---
        # 1. Ranking_Poin (W - L) DESC
        # 2. T (Tie) DESC
        # 3. Random_Tie_Breaker ASC
        peringkat = peringkat.sort_values(
            by=['Ranking_Poin', 'T', 'Random_Tie_Breaker'], 
            ascending=[False, False, True]
        )
        peringkat['Peringkat'] = range(1, len(peringkat) + 1)
        # ------------------------------------
        
        # Mengubah Index 'ID' menjadi Kolom 'ID'
        peringkat = peringkat.reset_index(names=['ID'])
        

    jadwal_saat_ini = jadwal_df[jadwal_df['Putaran'] == putaran_saat_ini].reset_index()
    jadwal_untuk_template = []
    
    can_reshuffle = False
    current_mode = last_config['mode_permainan'] 
    current_format = last_config['format_turnamen'] 
    pemain_bye = []

    if not jadwal_saat_ini.empty:
        current_mode = jadwal_saat_ini.loc[0, 'Mode']
        current_format = last_config['format_turnamen'] 
        
        # 1. Tentukan Pemain yang Dapat Bye (Logika sama seperti di buat_jadwal)
        pemain_df_temp = hitung_wlt(pemain_df.copy(), jadwal_df.copy())
             
        pemain_potensial_idx = pemain_df_temp.sort_values(
            by=['Total_Bye', 'Games_Played', 'Ranking_Poin', 'Random_Tie_Breaker'], 
            ascending=[False, True, False, True]
        ).index.tolist()
        
        id_cols = ['Pemain_1_A', 'Pemain_1_B', 'Pemain_2_A', 'Pemain_2_B']
        pemain_yang_bermain_id = set()
        
        for col in id_cols:
            if col in jadwal_saat_ini.columns:
                # Ambil ID dan konversi ke integer yang aman
                safe_ids = [get_player_id(id_val) for id_val in jadwal_saat_ini[col].tolist()]
                pemain_yang_bermain_id.update([id for id in safe_ids if id is not None])

        players_per_court = 4 if current_mode == 'Double' else 2
        num_courts_used = len(jadwal_saat_ini)
        max_players_scheduled = num_courts_used * players_per_court
        
        # Ambil daftar pemain yang seharusnya bermain (sesuai prioritas)
        pemain_ranked = pemain_potensial_idx[:max_players_scheduled + players_per_court]
        
        # Pemain yang Bye
        pemain_bye_ids = [id for id in pemain_ranked if id not in pemain_yang_bermain_id]
        
        # Karena kita hanya menampilkan, kita gunakan pemain_df asli
        pemain_bye = pemain_df.loc[pemain_bye_ids]['Nama'].tolist() 
        
        # 2. Logika Jadwal dan Reshuffle
        if (jadwal_saat_ini['Status'] == 'Belum Selesai').all():
            can_reshuffle = True
            
        if not pemain_df.empty:
            jadwal_dengan_nama = jadwal_saat_ini.copy()
            
            for col in id_cols:
                if col in jadwal_dengan_nama.columns and jadwal_dengan_nama[col].notna().any():
                    # Merge menggunakan ID pemain untuk mendapatkan nama
                    jadwal_dengan_nama = jadwal_dengan_nama.merge(
                        pemain_df[['Nama']], 
                        left_on=col, 
                        right_index=True, 
                        how='left', 
                        suffixes=('', f'_{col}_Nama')
                    )
                    jadwal_dengan_nama = jadwal_dengan_nama.rename(columns={'Nama': f'{col}_Nama'})

            jadwal_untuk_template = jadwal_dengan_nama.to_dict('records')
    
    if putaran_saat_ini == 0:
        pemain_bye = []


    return render_template(
        'index.html', 
        peringkat=peringkat.to_dict('records'),
        jadwal=jadwal_untuk_template,
        putaran=putaran_saat_ini,
        max_lapangan_pilihan=[1, 2, 3, 4],
        can_reshuffle=can_reshuffle,
        current_mode=current_mode,
        current_format=current_format,
        pemain_bye=pemain_bye
    )

@app.route('/tambah_pemain', methods=['POST'])
def tambah_pemain():
    global pemain_df
    nama = request.form.get('nama_pemain')
    
    if nama and len(pemain_df) < MAX_PEMAIN:
        new_id = get_next_player_id()
        # Inisialisasi lengkap
        new_row = pd.DataFrame([{'ID': new_id, 'Nama': nama, 'Total_Poin': 0, 'Games_Played': 0, 'Total_Bye': 0, 'W': 0, 'L': 0, 'T': 0, 'Ranking_Poin': 0}])
        new_row = new_row.set_index('ID')
        pemain_df = pd.concat([pemain_df, new_row])
        
    return redirect(url_for('index'))

@app.route('/hapus_pemain/<int:player_id>', methods=['POST'])
def hapus_pemain(player_id):
    global pemain_df, jadwal_df, putaran_saat_ini
    
    if player_id in pemain_df.index:
        # Hapus pemain dari DataFrame pemain
        pemain_df.drop(player_id, inplace=True)
        
        # Hapus match yang BELUM SELESAI di putaran saat ini jika pemain terlibat
        cols_to_check = ['Pemain_1_A', 'Pemain_1_B', 'Pemain_2_A', 'Pemain_2_B']
        
        jadwal_saat_ini_idx = jadwal_df[jadwal_df['Putaran'] == putaran_saat_ini].index
        
        indices_to_drop = []
        for idx in jadwal_saat_ini_idx:
            is_involved = False
            # Menggunakan .loc untuk akses yang lebih aman dan eksplisit
            for col in cols_to_check:
                match_id_value = get_player_id(jadwal_df.loc[idx, col])

                if match_id_value == player_id:
                    is_involved = True
                    break
            
            if is_involved and jadwal_df.loc[idx, 'Status'] == 'Belum Selesai':
                indices_to_drop.append(idx)
        
        if indices_to_drop:
            jadwal_df.drop(indices_to_drop, inplace=True)
            
        # Perbarui W/L/T dan Ranking_Poin setelah menghapus pemain
        pemain_df = hitung_wlt(pemain_df, jadwal_df)
        pemain_df.drop(columns=['Ranking_Poin'], errors='ignore', inplace=True) # Hapus kolom sementara

        # Jika semua match di putaran saat ini terhapus, kembalikan putaran_saat_ini ke putaran sebelumnya
        if putaran_saat_ini > 0 and jadwal_df[jadwal_df['Putaran'] == putaran_saat_ini].empty:
            putaran_saat_ini -= 1

    return redirect(url_for('index'))


@app.route('/mulai_putaran', methods=['POST'])
def mulai_putaran():
    global putaran_saat_ini, jadwal_df, last_config
    
    num_lapangan = int(request.form.get('num_lapangan', 1))
    format_turnamen = request.form.get('format_turnamen')
    mode_permainan = request.form.get('mode_permainan') 

    players_per_court = 4 if mode_permainan == 'Double' else 2

    if len(pemain_df) < players_per_court:
        return redirect(url_for('index')) 

    # Hapus jadwal putaran yang belum selesai
    jadwal_df = jadwal_df[jadwal_df['Status'] == 'Selesai'] 
    
    putaran_saat_ini += 1
    
    # Simpan konfigurasi yang dipilih
    last_config['num_lapangan'] = num_lapangan
    last_config['format_turnamen'] = format_turnamen
    last_config['mode_permainan'] = mode_permainan
    
    # Pastikan pemain_df memiliki Games_Played dan Total_Bye sebelum masuk ke buat_jadwal
    if 'Games_Played' not in pemain_df.columns: pemain_df['Games_Played'] = 0
    if 'Total_Bye' not in pemain_df.columns: pemain_df['Total_Bye'] = 0

    # Jadwal dibuat menggunakan Ranking_Poin = W - L untuk prioritas pemain
    new_matches = buat_jadwal(pemain_df, putaran_saat_ini, num_lapangan, mode_permainan, format_turnamen)
    
    if new_matches:
        new_jadwal_df = pd.DataFrame(new_matches)
        new_jadwal_df.set_index('Match_ID', inplace=True) 
        jadwal_df = pd.concat([jadwal_df, new_jadwal_df])
        
    return redirect(url_for('index'))

@app.route('/kocok_ulang', methods=['POST'])
def kocok_ulang():
    global jadwal_df, putaran_saat_ini, last_config
    
    jadwal_saat_ini = jadwal_df[jadwal_df['Putaran'] == putaran_saat_ini]
    
    if not jadwal_saat_ini.empty and (jadwal_saat_ini['Status'] == 'Belum Selesai').all():
        
        # Hapus jadwal putaran saat ini yang belum selesai
        jadwal_df = jadwal_df[jadwal_df['Putaran'] != putaran_saat_ini]

        num_lapangan = len(jadwal_saat_ini['Lapangan'].unique()) 
        format_turnamen = request.form.get('format_turnamen_ulang')
        mode_permainan = request.form.get('mode_permainan_ulang') 
        
        # Update last_config
        last_config['num_lapangan'] = num_lapangan
        last_config['format_turnamen'] = format_turnamen
        last_config['mode_permainan'] = mode_permainan

        # Pastikan pemain_df memiliki Games_Played dan Total_Bye sebelum masuk ke buat_jadwal
        if 'Games_Played' not in pemain_df.columns: pemain_df['Games_Played'] = 0
        if 'Total_Bye' not in pemain_df.columns: pemain_df['Total_Bye'] = 0
        
        new_matches = buat_jadwal(pemain_df, putaran_saat_ini, num_lapangan, mode_permainan, format_turnamen)

        if new_matches:
            new_jadwal_df = pd.DataFrame(new_matches)
            new_jadwal_df.set_index('Match_ID', inplace=True) 
            jadwal_df = pd.concat([jadwal_df, new_jadwal_df])

    return redirect(url_for('index'))

@app.route('/input_skor/<int:match_id>', methods=['POST'])
def input_skor(match_id):
    global jadwal_df, pemain_df, putaran_saat_ini, last_config
    
    try:
        skor_tim_1 = int(request.form.get('skor_tim_1', 0))
        skor_tim_2 = int(request.form.get('skor_tim_2', 0))
    except ValueError:
        return redirect(url_for('index'))
    
    if skor_tim_1 >= 0 and skor_tim_2 >= 0:
        
        if match_id in jadwal_df.index:
            
            match_row = jadwal_df.loc[match_id]
            
            # Mendapatkan ID pemain yang aman (INTEGER)
            pemain_ids_team_1 = safe_get_player_id_list([match_row['Pemain_1_A'], match_row['Pemain_1_B']])
            pemain_ids_team_2 = safe_get_player_id_list([match_row['Pemain_2_A'], match_row['Pemain_2_B']])
            
            pemain_ids_all = pemain_ids_team_1 + pemain_ids_team_2

            # 1. Kurangi Poin Lama & Games_Played Lama (untuk update skor/reset)
            # Perhitungan ini HANYA untuk "Total_Poin" (Cumulative Score) dan "Games_Played"
            if match_row['Status'] == 'Selesai':
                poin_lama_tim_1 = match_row['Poin_Tim_1']
                poin_lama_tim_2 = match_row['Poin_Tim_2']
                
                games_played_lama = poin_lama_tim_1 + poin_lama_tim_2

                for id in pemain_ids_team_1:
                    if id in pemain_df.index:
                        pemain_df.loc[id, 'Total_Poin'] -= poin_lama_tim_1
                        pemain_df.loc[id, 'Games_Played'] -= games_played_lama
                
                for id in pemain_ids_team_2:
                    if id in pemain_df.index:
                        pemain_df.loc[id, 'Total_Poin'] -= poin_lama_tim_2
                        pemain_df.loc[id, 'Games_Played'] -= games_played_lama
                        
            # 2. Tambah Games_Played Baru
            total_points_in_match = skor_tim_1 + skor_tim_2
            for id in pemain_ids_all:
                 if id in pemain_df.index:
                     pemain_df.loc[id, 'Games_Played'] += total_points_in_match 
                         
            # 3. Update Jadwal
            jadwal_df.loc[match_id, ['Poin_Tim_1', 'Poin_Tim_2']] = [skor_tim_1, skor_tim_2]
            jadwal_df.loc[match_id, 'Status'] = 'Selesai'
            
            # 4. Tambah Poin Baru ke Total Poin Pemain (Cumulative Score)
            for id in pemain_ids_team_1:
                if id in pemain_df.index:
                    pemain_df.loc[id, 'Total_Poin'] += skor_tim_1

            for id in pemain_ids_team_2:
                if id in pemain_df.index:
                    pemain_df.loc[id, 'Total_Poin'] += skor_tim_2

            # 5. HITUNG ULANG W/L/T & Ranking_Poin (W-L)
            pemain_df_temp = hitung_wlt(pemain_df.copy(), jadwal_df.copy())
            
            # Update kembali W, L, T, dan Ranking_Poin ke pemain_df global
            for col in ['W', 'L', 'T', 'Ranking_Poin']:
                if col in pemain_df_temp.columns:
                    pemain_df[col] = pemain_df_temp[col]

    
    # --- Otomatis Buat Jadwal Putaran Berikutnya ---
    current_round_matches = jadwal_df[jadwal_df['Putaran'] == putaran_saat_ini]
    
    if not current_round_matches.empty and (current_round_matches['Status'] == 'Selesai').all():
        
        # Hapus semua jadwal putaran yang BELUM SELESAI
        jadwal_df = jadwal_df[jadwal_df['Putaran'] < putaran_saat_ini] 
        
        putaran_saat_ini += 1
        
        num_lapangan = last_config['num_lapangan']
        format_turnamen = last_config['format_turnamen']
        mode_permainan = last_config['mode_permainan']
        
        # INCREMENT Total_Bye untuk pemain yang "Bye" di putaran sebelumnya
        prev_putaran = putaran_saat_ini - 1
        
        # Perbarui W/L/T dan Ranking_Poin sebelum menentukan Bye
        pemain_df_temp = hitung_wlt(pemain_df.copy(), jadwal_df.copy())
        
        # Pastikan pemain_df memiliki semua kolom untuk sorting
        for col in ['Games_Played', 'Total_Bye', 'Ranking_Poin', 'Random_Tie_Breaker']:
             if col not in pemain_df_temp.columns: pemain_df_temp[col] = 0
        
        players_per_court = 4 if mode_permainan == 'Double' else 2
        num_courts = last_config['num_lapangan']
        max_players_to_be_scheduled = num_courts * players_per_court
        
        # Logika sorting harus sama persis dengan yang ada di buat_jadwal
        pemain_potensial_prev = pemain_df_temp.sort_values(
            by=['Total_Bye', 'Games_Played', 'Ranking_Poin', 'Random_Tie_Breaker'], 
            ascending=[False, True, False, True]
        ).index.tolist()
        
        # Jumlah pemain yang diprioritaskan untuk dipertimbangkan bermain 
        pemain_potensial_prev = pemain_potensial_prev[:max_players_to_be_scheduled + players_per_court]
        
        # Ambil pemain yang BENAR-BENAR bermain di putaran sebelumnya
        prev_matches = jadwal_df[jadwal_df['Putaran'] == prev_putaran]
        
        # Gunakan fungsi bantuan untuk mendapatkan ID integer yang aman
        players_who_played_prev = set()
        for col in ['Pemain_1_A', 'Pemain_1_B', 'Pemain_2_A', 'Pemain_2_B']:
            safe_ids = safe_get_player_id_list(prev_matches[col].tolist())
            players_who_played_prev.update(safe_ids)
        
        # Pemain yang Bye adalah pemain yang diprioritaskan tapi tidak bermain
        players_on_bye_prev = [id for id in pemain_potensial_prev if id not in players_who_played_prev]
        
        # Increment Total_Bye (di pemain_df global)
        pemain_df.loc[players_on_bye_prev, 'Total_Bye'] += 1
        
        
        new_matches = buat_jadwal(pemain_df, putaran_saat_ini, num_lapangan, mode_permainan, format_turnamen)
        
        if new_matches:
            new_jadwal_df = pd.DataFrame(new_matches)
            new_jadwal_df.set_index('Match_ID', inplace=True) 
            jadwal_df = pd.concat([jadwal_df, new_jadwal_df])
            
    return redirect(url_for('index'))

# ROUTE BARU: Menampilkan Rekap Visual
@app.route('/rekap_visual')
def rekap_visual():
    global pemain_df, jadwal_df
    
    # 1. Hitung W/L/T dan Ranking_Poin (W-L) final
    pemain_final = hitung_wlt(pemain_df.copy(), jadwal_df.copy())
    
    # --- KRUSIAL: LOGIKA RANKING BARU ---
    # 1. Ranking_Poin (W - L) DESC
    # 2. T (Tie) DESC
    # 3. Random_Tie_Breaker ASC
    pemain_final = pemain_final.sort_values(
        by=['Ranking_Poin', 'T', 'Random_Tie_Breaker'], 
        ascending=[False, False, True]
    )
    pemain_final['Peringkat'] = range(1, len(pemain_final) + 1)
    # ------------------------------------
    
    # 2. Siapkan data untuk template
    kolom_rekap = [
        'Peringkat', 
        'Nama', 
        'Ranking_Poin', # Menggunakan Ranking_Poin (W-L)
        'Total_Poin',   # Total_Poin (Cumulative Score) tetap disertakan
        'W', 'L', 'T', 
        'Games_Played'
    ]
    rekap_df = pemain_final.reset_index()
    
    # Tambahkan kolom Ranking_Poin ke rekap_df jika belum ada (hanya untuk keamanan)
    if 'Ranking_Poin' not in rekap_df.columns: rekap_df['Ranking_Poin'] = 0
    
    rekap_df = rekap_df[kolom_rekap].reset_index(drop=True)
    
    return render_template(
        'rekap.html', 
        rekap=rekap_df.to_dict('records')
    )

if __name__ == '__main__':
    app.run(debug=True)
