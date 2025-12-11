import random
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, Response

# --- Konfigurasi Turnamen ---
MAX_PEMAIN = 32

# Inisialisasi Aplikasi Flask
app = Flask(__name__)

# --- Manajemen Data dengan Pandas (Simulasi Database) ---
if 'pemain_df' not in globals():
    # Menambahkan 'Ranking_W_L' untuk peringkat berbasis W-L
    pemain_df = pd.DataFrame(columns=['ID', 'Nama', 'Total_Poin', 'Games_Played', 'Total_Bye', 'W', 'L', 'T', 'Ranking_W_L'])
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
    
# Fungsi Baru untuk menghitung Games Played (Revisi #1)
def hitung_games_played_per_round(pemain_df_input, jadwal_df_input):
    """
    Menghitung Games_Played sebagai jumlah total pertandingan (round) 
    yang diikuti oleh setiap pemain yang statusnya 'Selesai'.
    """
    pemain_df = pemain_df_input[['Nama']].copy() # Hanya ambil Nama untuk merge
    if 'Games_Played' not in pemain_df.columns:
        pemain_df['Games_Played'] = 0
    pemain_df['Games_Played'] = 0 # RESET Games_Played
    
    jadwal_selesai = jadwal_df_input[jadwal_df_input['Status'] == 'Selesai']
    
    for _, match in jadwal_selesai.iterrows():
        # Ambil semua ID pemain yang berpartisipasi dalam match ini
        id_cols = ['Pemain_1_A', 'Pemain_1_B', 'Pemain_2_A', 'Pemain_2_B']
        pemain_dalam_match = [match[col] for col in id_cols] 
        
        # Hanya hitung 1 Games_Played per pemain per pertandingan
        for p_id in set([p for p in pemain_dalam_match if p is not None and p in pemain_df.index]):
            pemain_df.loc[p_id, 'Games_Played'] += 1
                
    return pemain_df[['Games_Played']]


# Fungsi W/L/T yang direvisi (Revisi #2)
def hitung_wlt(pemain_df_input, jadwal_df_input):
    """
    Menghitung Win/Lose/Tie berdasarkan hasil pertandingan Selesai.
    Juga menambahkan Ranking_W_L (W - L).
    """
    pemain_df = pemain_df_input.copy()
    
    # Inisialisasi kolom W/L/T jika belum ada
    for col in ['W', 'L', 'T', 'Ranking_W_L']:
        if col not in pemain_df.columns:
            pemain_df[col] = 0

    # Reset nilai W/L/T untuk perhitungan baru
    pemain_df['W'] = 0
    pemain_df['L'] = 0
    pemain_df['T'] = 0
    
    jadwal_selesai = jadwal_df_input[jadwal_df_input['Status'] == 'Selesai']
    
    for _, match in jadwal_selesai.iterrows():
        p1a, p1b = match['Pemain_1_A'], match['Pemain_1_B']
        p2a, p2b = match['Pemain_2_A'], match['Pemain_2_B']
        poin1, poin2 = match['Poin_Tim_1'], match['Poin_Tim_2']
        
        pemain_tim_1 = [p1a, p1b] if match['Mode'] == 'Double' else [p1a]
        pemain_tim_2 = [p2a, p2b] if match['Mode'] == 'Double' else [p2a]
        
        if poin1 > poin2:
            # Tim 1 Menang, Tim 2 Kalah
            for p_id in pemain_tim_1:
                if p_id in pemain_df.index:
                    pemain_df.loc[p_id, 'W'] += 1
            for p_id in pemain_tim_2:
                if p_id in pemain_df.index:
                    pemain_df.loc[p_id, 'L'] += 1
        elif poin2 > poin1:
            # Tim 2 Menang, Tim 1 Kalah
            for p_id in pemain_tim_2:
                if p_id in pemain_df.index:
                    pemain_df.loc[p_id, 'W'] += 1
            for p_id in pemain_tim_1:
                if p_id in pemain_df.index:
                    pemain_df.loc[p_id, 'L'] += 1
        else:
            # Seri/Tie (poin1 == poin2)
            pemain_all = [p for p in pemain_tim_1 + pemain_tim_2 if p is not None]
            for p_id in pemain_all:
                if p_id in pemain_df.index:
                    pemain_df.loc[p_id, 'T'] += 1
                    
    # Tambahkan hitungan Ranking_W_L (W - L)
    pemain_df['Ranking_W_L'] = pemain_df['W'] - pemain_df['L']
        
    return pemain_df

    
def buat_jadwal(pemain_df, putaran, num_lapangan, mode_permainan, format_turnamen):
    """
    Membuat jadwal baru dengan logika prioritas yang lebih adil dan tie-breaker acak.
    """
    
    # Tambahkan inisialisasi kolom jika belum ada
    for col in ['Total_Bye', 'Games_Played', 'Random_Tie_Breaker']:
        if col not in pemain_df.columns:
            pemain_df[col] = 0
            
    # PERUBAHAN KRUSIAL: Tambahkan kolom tie-breaker acak untuk memastikan pengocokan yang berbeda saat skor sama
    pemain_df['Random_Tie_Breaker'] = [random.random() for _ in range(len(pemain_df))]
        
    # Kriteria Sorting Prioritas: Total_Bye DESC, Games_Played ASC, Total_Poin DESC, Random_Tie_Breaker ASC
    pemain_aktif_sorted = pemain_df.sort_values(
        by=['Total_Bye', 'Games_Played', 'Total_Poin', 'Random_Tie_Breaker'], 
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
        random.shuffle(pemain_bermain) # Acak di antara pemain yang sudah diprioritaskan
        
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
        
        # Urutkan ulang pemain yang bermain berdasarkan Total_Poin (untuk pairing High vs Low)
        pemain_bermain_df_sorted = pemain_df.loc[pemain_bermain].sort_values(
            by='Total_Poin', ascending=False
        ).index.tolist()
        
        mid_point = len(pemain_bermain_df_sorted) // 2
        peringkat_tinggi = pemain_bermain_df_sorted[:mid_point]
        peringkat_rendah = pemain_bermain_df_sorted[mid_point:]
        
        # Kocok di dalam masing-masing kelompok (High vs Low)
        random.shuffle(peringkat_tinggi)
        random.shuffle(peringkat_rendah)
        
        if mode_permainan == 'Double':
            
            num_matches = len(peringkat_tinggi) // 2 
            
            for i in range(num_matches):
                
                # Ambil 2 pemain High dan 2 pemain Low, lalu bagi timnya
                H1 = peringkat_tinggi.pop(0)
                H2 = peringkat_tinggi.pop(0)
                L1 = peringkat_rendah.pop(0)
                L2 = peringkat_rendah.pop(0)

                # Pair: H1 & L1 vs H2 & L2 (Asumsi Pairing Terbaik di Mexicano)
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
#                      ROUTE APLIKASI
# ----------------------------------------------------

@app.route('/')
def index():
    global pemain_df, jadwal_df, putaran_saat_ini, last_config

    # Inisialisasi kolom baru/penting
    for col in ['Total_Bye', 'Games_Played', 'W', 'L', 'T', 'Ranking_W_L']:
        if col not in pemain_df.columns:
            pemain_df[col] = 0

    peringkat = pd.DataFrame()
    if not pemain_df.empty:
        # 1. Hitung W/L/T dan Ranking_W_L (W-L)
        pemain_df_wlt = hitung_wlt(pemain_df.copy(), jadwal_df.copy())
        
        # 2. Hitung Games_Played (Revisi #1: Total Round Partisipasi)
        pemain_df_games_played = hitung_games_played_per_round(pemain_df.copy(), jadwal_df.copy())

        # Gabungkan semua data statistik ke DataFrame peringkat
        peringkat = pemain_df.copy()
        
        # Ambil kolom W/L/T/Ranking_W_L dari hasil hitung_wlt
        for col in ['W', 'L', 'T', 'Ranking_W_L']:
            peringkat[col] = pemain_df_wlt[col]
        
        # Ambil Games_Played dari hasil hitung_games_played_per_round
        peringkat = peringkat.drop(columns=['Games_Played'], errors='ignore').merge(
            pemain_df_games_played, left_index=True, right_index=True, how='left'
        ).fillna({'Games_Played': 0})

        
        # 3. Update Ranking Logic: 1. Ranking_W_L (W-L) DESC, 2. Total_Poin DESC, 3. Games_Played ASC
        peringkat = peringkat.sort_values(
            by=['Ranking_W_L', 'Total_Poin', 'Games_Played'], 
            ascending=[False, False, True]
        )
        peringkat['Peringkat'] = range(1, len(peringkat) + 1)
        
        # PERBAIKAN: Mengubah Index 'ID' menjadi Kolom 'ID'
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
        
        # --- Logika Penentuan Pemain Bye (Menggunakan Ranking W-L dan Games Played) ---
        players_per_court = 4 if current_mode == 'Double' else 2
        num_courts_used = len(jadwal_saat_ini['Lapangan'].unique())
        max_players_scheduled = num_courts_used * players_per_court
        
        # Urutkan pemain dengan logika yang sama seperti di buat_jadwal (termasuk Random_Tie_Breaker sementara)
        if 'Random_Tie_Breaker' not in pemain_df.columns:
            pemain_df['Random_Tie_Breaker'] = 0 
            
        pemain_potensial_idx = pemain_df.sort_values(
            by=['Total_Bye', 'Games_Played', 'Total_Poin', 'Random_Tie_Breaker'], 
            ascending=[False, True, False, True]
        ).index.tolist()
        
        # Pemain yang seharusnya bermain (sesuai prioritas)
        pemain_ranked = pemain_potensial_idx[:max_players_scheduled + players_per_court]
        
        id_cols = ['Pemain_1_A', 'Pemain_1_B', 'Pemain_2_A', 'Pemain_2_B']
        pemain_yang_bermain_id = set()
        for col in id_cols:
            if col in jadwal_saat_ini.columns:
                # Mengambil ID pemain yang ada di jadwal
                pemain_yang_bermain_id.update(jadwal_saat_ini[col].dropna().tolist())

        # Pemain yang Bye adalah pemain yang diprioritaskan tetapi tidak masuk dalam jadwal
        pemain_bye_ids = [id for id in pemain_ranked if id not in pemain_yang_bermain_id]
        pemain_bye = pemain_df.loc[pemain_bye_ids]['Nama'].tolist()
        
        # ------------------------------------------------------------------------------
        
        # 2. Logika Jadwal dan Reshuffle
        if (jadwal_saat_ini['Status'] == 'Belum Selesai').all():
            can_reshuffle = True
            
        if not pemain_df.empty:
            jadwal_dengan_nama = jadwal_saat_ini.copy()
            
            # Map ID pemain ke Nama untuk tampilan di HTML
            for col in id_cols:
                if col in jadwal_dengan_nama.columns and jadwal_dengan_nama[col].notna().any():
                    # Gabungkan dengan pemain_df untuk mendapatkan Nama
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
        # Inisialisasi kolom baru, termasuk Ranking_W_L
        new_row = pd.DataFrame([{'ID': new_id, 'Nama': nama, 'Total_Poin': 0, 'Games_Played': 0, 'Total_Bye': 0, 'W': 0, 'L': 0, 'T': 0, 'Ranking_W_L': 0}])
        new_row = new_row.set_index('ID')
        pemain_df = pd.concat([pemain_df, new_row])
        
    return redirect(url_for('index'))

@app.route('/hapus_pemain/<int:player_id>', methods=['POST'])
def hapus_pemain(player_id):
    global pemain_df, jadwal_df, putaran_saat_ini
    
    if player_id in pemain_df.index:
        # Hapus pemain dari DataFrame pemain
        pemain_df.drop(player_id, inplace=True)
        
        # Hapus pertandingan dari jadwal yang melibatkan pemain tersebut di putaran saat ini (Belum Selesai)
        cols_to_check = ['Pemain_1_A', 'Pemain_1_B', 'Pemain_2_A', 'Pemain_2_B']
        
        jadwal_saat_ini_idx = jadwal_df[
            (jadwal_df['Putaran'] == putaran_saat_ini) & 
            (jadwal_df[cols_to_check].apply(lambda row: player_id in row.values, axis=1))
        ].index
        
        if not jadwal_saat_ini_idx.empty:
            jadwal_df.drop(jadwal_saat_ini_idx, inplace=True)
            
        # Jika semua match di putaran saat ini terhapus, kembalikan putaran_saat_ini ke putaran sebelumnya
        if putaran_saat_ini > 0 and jadwal_df[jadwal_df['Putaran'] == putaran_saat_ini].empty:
            putaran_saat_ini -= 1

        # Re-calculate W/L/T, Games_Played, dan Ranking_W_L
        pemain_df_wlt = hitung_wlt(pemain_df.copy(), jadwal_df.copy())
        pemain_df_games_played = hitung_games_played_per_round(pemain_df.copy(), jadwal_df.copy())

        # Update global pemain_df dengan new stats
        for col in ['W', 'L', 'T', 'Ranking_W_L']:
            if col in pemain_df_wlt.columns:
                pemain_df[col] = pemain_df_wlt[col]
                
        # Update Games_Played (merge logic is safer)
        if 'Games_Played' not in pemain_df.columns: pemain_df['Games_Played'] = 0
        pemain_df = pemain_df.drop(columns=['Games_Played'], errors='ignore').merge(
            pemain_df_games_played, left_index=True, right_index=True, how='left'
        ).fillna({'Games_Played': 0})
        
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
    for col in ['Games_Played', 'Total_Bye', 'W', 'L', 'T', 'Ranking_W_L']:
        if col not in pemain_df.columns:
            pemain_df[col] = 0
            
    # Perhitungan Games_Played dan W/L/T diulang di sini untuk memastikan data terbaru sebelum membuat jadwal
    pemain_df_temp = hitung_wlt(pemain_df.copy(), jadwal_df.copy())
    pemain_df_games_played = hitung_games_played_per_round(pemain_df.copy(), jadwal_df.copy())

    for col in ['W', 'L', 'T', 'Ranking_W_L']:
        pemain_df[col] = pemain_df_temp[col]

    pemain_df = pemain_df.drop(columns=['Games_Played'], errors='ignore').merge(
        pemain_df_games_played, left_index=True, right_index=True, how='left'
    ).fillna({'Games_Played': 0})


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
        
        # Update last_config dengan format baru setelah kocok ulang
        last_config['num_lapangan'] = num_lapangan
        last_config['format_turnamen'] = format_turnamen
        last_config['mode_permainan'] = mode_permainan

        # Pastikan pemain_df memiliki Games_Played dan Total_Bye sebelum masuk ke buat_jadwal
        for col in ['Games_Played', 'Total_Bye', 'W', 'L', 'T', 'Ranking_W_L']:
            if col not in pemain_df.columns:
                pemain_df[col] = 0
        
        # Hitung ulang W/L/T dan Games_Played sebelum kocok ulang
        pemain_df_temp = hitung_wlt(pemain_df.copy(), jadwal_df.copy())
        pemain_df_games_played = hitung_games_played_per_round(pemain_df.copy(), jadwal_df.copy())

        for col in ['W', 'L', 'T', 'Ranking_W_L']:
            pemain_df[col] = pemain_df_temp[col]

        pemain_df = pemain_df.drop(columns=['Games_Played'], errors='ignore').merge(
            pemain_df_games_played, left_index=True, right_index=True, how='left'
        ).fillna({'Games_Played': 0})
        
        
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
            
            match_row = jadwal_df.loc[match_id].copy() # Copy agar perubahan tidak langsung mempengaruhi jadwal_df

            pemain_ids_team_1 = [id for id in [match_row['Pemain_1_A'], match_row['Pemain_1_B']] if id is not None]
            pemain_ids_team_2 = [id for id in [match_row['Pemain_2_A'], match_row['Pemain_2_B']] if id is not None]
            
            # 1. Kurangi Poin Lama (untuk update skor)
            if match_row['Status'] == 'Selesai':
                poin_lama_tim_1 = match_row['Poin_Tim_1']
                poin_lama_tim_2 = match_row['Poin_Tim_2']
                
                # --- HAPUS LOGIKA GAMES_PLAYED DARI SINI (Games Played dihitung ulang) ---
                
                for id in pemain_ids_team_1:
                    if id in pemain_df.index:
                        pemain_df.loc[id, 'Total_Poin'] -= poin_lama_tim_1
                
                for id in pemain_ids_team_2:
                    if id in pemain_df.index:
                        pemain_df.loc[id, 'Total_Poin'] -= poin_lama_tim_2
                        
            # 2. Update Jadwal
            jadwal_df.loc[match_id, ['Poin_Tim_1', 'Poin_Tim_2']] = [skor_tim_1, skor_tim_2]
            jadwal_df.loc[match_id, 'Status'] = 'Selesai'
            
            # 3. Tambah Poin Baru ke Total Poin Pemain
            for id in pemain_ids_team_1:
                if id in pemain_df.index:
                    pemain_df.loc[id, 'Total_Poin'] += skor_tim_1

            for id in pemain_ids_team_2:
                if id in pemain_df.index:
                    pemain_df.loc[id, 'Total_Poin'] += skor_tim_2

            # 4. HITUNG ULANG SEMUA STATISTIK (W/L/T, Ranking_W_L, dan Games_Played)
            pemain_df_wlt = hitung_wlt(pemain_df.copy(), jadwal_df.copy())
            pemain_df_games_played = hitung_games_played_per_round(pemain_df.copy(), jadwal_df.copy())

            # Update kembali W, L, T, Ranking_W_L, dan Games_Played ke pemain_df global
            for col in ['W', 'L', 'T', 'Ranking_W_L']:
                if col not in pemain_df.columns: pemain_df[col] = 0
                if col in pemain_df_wlt.columns:
                    pemain_df[col] = pemain_df_wlt[col]
            
            # Update Games_Played
            if 'Games_Played' not in pemain_df.columns: pemain_df['Games_Played'] = 0
            pemain_df = pemain_df.drop(columns=['Games_Played'], errors='ignore').merge(
                pemain_df_games_played, left_index=True, right_index=True, how='left'
            ).fillna({'Games_Played': 0})

    
    # --- Otomatis Buat Jadwal Putaran Berikutnya ---
    current_round_matches = jadwal_df[jadwal_df['Putaran'] == putaran_saat_ini]
    
    if not current_round_matches.empty and (current_round_matches['Status'] == 'Selesai').all():
        
        # Hapus semua jadwal putaran yang BELUM SELESAI (hanya putaran saat ini)
        jadwal_df = jadwal_df[jadwal_df['Putaran'] < putaran_saat_ini]
        
        putaran_saat_ini += 1
        
        num_lapangan = last_config['num_lapangan']
        format_turnamen = last_config['format_turnamen']
        mode_permainan = last_config['mode_permainan']
        
        # INCREMENT Total_Bye untuk pemain yang "Bye" di putaran sebelumnya
        prev_putaran = putaran_saat_ini - 1
        
        players_per_court = 4 if last_config['mode_permainan'] == 'Double' else 2
        num_courts = last_config['num_lapangan']
        max_players_to_be_scheduled = num_courts * players_per_court
        
        # Pastikan pemain_df memiliki semua kolom untuk sorting
        for col in ['Games_Played', 'Total_Bye', 'Random_Tie_Breaker']:
            if col not in pemain_df.columns: pemain_df[col] = 0
        
        # Logika sorting harus sama persis dengan yang ada di buat_jadwal
        pemain_potensial_prev = pemain_df.sort_values(
            by=['Total_Bye', 'Games_Played', 'Total_Poin', 'Random_Tie_Breaker'], 
            ascending=[False, True, False, True]
        ).index.tolist()
        
        # Jumlah pemain yang diprioritaskan untuk dipertimbangkan bermain 
        pemain_potensial_prev = pemain_potensial_prev[:max_players_to_be_scheduled + players_per_court]
        
        # 2. Ambil pemain yang BENAR-BENAR bermain di putaran sebelumnya
        prev_matches = jadwal_df[jadwal_df['Putaran'] == prev_putaran]
        players_who_played_prev = set(prev_matches[['Pemain_1_A', 'Pemain_1_B', 'Pemain_2_A', 'Pemain_2_B']].stack().dropna().tolist())
        
        # 3. Pemain yang Bye adalah pemain yang diprioritaskan (pemain_potensial_prev) tapi tidak bermain
        players_on_bye_prev = [id for id in pemain_potensial_prev if id not in players_who_played_prev]
        
        # 4. Increment Total_Bye
        pemain_df.loc[players_on_bye_prev, 'Total_Bye'] += 1
        
        
        new_matches = buat_jadwal(pemain_df, putaran_saat_ini, num_lapangan, mode_permainan, format_turnamen)
        
        if new_matches:
            new_jadwal_df = pd.DataFrame(new_matches)
            new_jadwal_df.set_index('Match_ID', inplace=True) 
            jadwal_df = pd.concat([jadwal_df, new_jadwal_df])
            
    return redirect(url_for('index'))

# ROUTE BARU: Menampilkan Rekap Visual (bukan download CSV)
@app.route('/rekap_visual')
def rekap_visual():
    global pemain_df, jadwal_df
    
    # 1. Hitung W/L/T, Ranking_W_L dan Games_Played
    pemain_final = hitung_wlt(pemain_df.copy(), jadwal_df.copy())
    pemain_df_games_played = hitung_games_played_per_round(pemain_df.copy(), jadwal_df.copy())
    
    # Gabungkan Games_Played dan Total_Poin
    pemain_final = pemain_final.merge(
        pemain_df_games_played, left_index=True, right_index=True, how='left'
    )
    if 'Total_Poin' in pemain_df.columns:
        pemain_final['Total_Poin'] = pemain_df['Total_Poin']
        
    # 2. Ranking: 1. Ranking_W_L (W-L) DESC, 2. Total_Poin DESC, 3. Games_Played ASC
    pemain_final = pemain_final.sort_values(
        by=['Ranking_W_L', 'Total_Poin', 'Games_Played'], 
        ascending=[False, False, True]
    )
    pemain_final['Peringkat'] = range(1, len(pemain_final) + 1)
    
    # 3. Siapkan data untuk template
    kolom_rekap = [
        'Peringkat', 
        'Nama', 
        'Total_Poin', 
        'Games_Played', 
        'W', 'L', 'T', 
        'Ranking_W_L' 
    ]
    
    rekap_df = pemain_final.reset_index()
    # Pilih hanya kolom yang ada
    rekap_df = rekap_df[[col for col in kolom_rekap if col in rekap_df.columns]].reset_index(drop=True)
    
    return render_template(
        'rekap.html', 
        rekap=rekap_df.to_dict('records')
    )

if __name__ == '__main__':
    app.run(debug=True)
