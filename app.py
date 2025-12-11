import random
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, Response

# --- Konfigurasi Turnamen ---
MAX_PEMAIN = 32

# Inisialisasi Aplikasi Flask
app = Flask(__name__)

# --- Manajemen Data dengan Pandas (Simulasi Database) ---
if 'pemain_df' not in globals():
    pemain_df = pd.DataFrame(columns=['ID', 'Nama', 'Total_Poin', 'Games_Played', 'Total_Bye', 'W', 'L', 'T'])
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

def hitung_wlt(pemain_df, jadwal_df):
    """
    Menghitung Win/Lose/Tie KUMULATIF berdasarkan semua pertandingan Selesai.
    """
    
    # Inisialisasi/Reset kolom W/L/T untuk perhitungan baru
    for col in ['W', 'L', 'T']:
        if col not in pemain_df.columns:
            pemain_df[col] = 0
        pemain_df[col] = 0 # Reset
        
    jadwal_selesai = jadwal_df[jadwal_df['Status'] == 'Selesai']
    
    for _, match in jadwal_selesai.iterrows():
        # Memastikan hanya ID yang valid
        pemain_tim_1 = [match['Pemain_1_A'], match['Pemain_1_B']] if match['Mode'] == 'Double' else [match['Pemain_1_A']]
        pemain_tim_1 = [p_id for p_id in pemain_tim_1 if pd.notna(p_id) and p_id in pemain_df.index]
        
        pemain_tim_2 = [match['Pemain_2_A'], match['Pemain_2_B']] if match['Mode'] == 'Double' else [match['Pemain_2_A']]
        pemain_tim_2 = [p_id for p_id in pemain_tim_2 if pd.notna(p_id) and p_id in pemain_df.index]

        poin1, poin2 = match['Poin_Tim_1'], match['Poin_Tim_2']
        
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
                    
    return pemain_df
    
def buat_jadwal(pemain_df, putaran, num_lapangan, mode_permainan, format_turnamen):
    """
    Membuat jadwal baru dengan logika prioritas.
    """
    if 'Total_Bye' not in pemain_df.columns:
        pemain_df['Total_Bye'] = 0
    if 'Games_Played' not in pemain_df.columns:
        pemain_df['Games_Played'] = 0
            
    pemain_df['Random_Tie_Breaker'] = [random.random() for _ in range(len(pemain_df))]
            
    pemain_df['Rank_Poin'] = pemain_df['Total_Poin'].rank(method='min', ascending=False)
    
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
        
        pemain_bermain_df_sorted = pemain_df.loc[pemain_bermain].sort_values(
            by='Total_Poin', ascending=False
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
#               ROUTE APLIKASI
# ----------------------------------------------------

@app.route('/')
def index():
    global pemain_df, jadwal_df, putaran_saat_ini, last_config

    if 'Total_Bye' not in pemain_df.columns:
        pemain_df['Total_Bye'] = 0
    if 'Games_Played' not in pemain_df.columns:
        pemain_df['Games_Played'] = 0
    
    for col in ['W', 'L', 'T']:
          if col not in pemain_df.columns:
              pemain_df[col] = 0

    peringkat = pd.DataFrame()
    if not pemain_df.empty:
        pemain_df_temp = hitung_wlt(pemain_df.copy(), jadwal_df.copy())
        
        peringkat = pemain_df_temp.copy()
        peringkat['Peringkat'] = peringkat['Total_Poin'].rank(method='min', ascending=False).astype(int)
        peringkat = peringkat.sort_values(by=['Peringkat', 'Total_Poin'], ascending=[True, False])
        
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
        players_per_court = 4 if current_mode == 'Double' else 2
        
        if 'Rank_Poin' not in pemain_df.columns:
            pemain_df['Rank_Poin'] = pemain_df['Total_Poin'].rank(method='min', ascending=False)
                
        if 'Random_Tie_Breaker' not in pemain_df.columns:
             pemain_df['Random_Tie_Breaker'] = 0 
            
        pemain_potensial_idx = pemain_df.sort_values(
            by=['Total_Bye', 'Games_Played', 'Total_Poin', 'Random_Tie_Breaker'], 
            ascending=[False, True, False, True]
        ).index.tolist()
        
        id_cols = ['Pemain_1_A', 'Pemain_1_B', 'Pemain_2_A', 'Pemain_2_B']
        pemain_yang_bermain_id = set()
        for col in id_cols:
            if col in jadwal_saat_ini.columns:
                pemain_yang_bermain_id.update(jadwal_saat_ini[col].dropna().tolist())

        num_courts_used = len(jadwal_saat_ini)
        max_players_scheduled = num_courts_used * players_per_court
        
        pemain_ranked = pemain_potensial_idx[:max_players_scheduled + players_per_court]
        
        pemain_bye_ids = [id for id in pemain_ranked if id not in pemain_yang_bermain_id]
        
        pemain_bye = pemain_df.loc[pemain_bye_ids]['Nama'].tolist()
        
        if (jadwal_saat_ini['Status'] == 'Belum Selesai').all():
            can_reshuffle = True
            
        if not pemain_df.empty:
            jadwal_dengan_nama = jadwal_saat_ini.copy()
            
            for col in id_cols:
                if col in jadwal_dengan_nama.columns and jadwal_dengan_nama[col].notna().any():
                    jadwal_dengan_nama = jadwal_dengan_nama.merge(
                        pemain_df[['Nama']], 
                        left_on=col, 
                        right_index=True, 
                        how='left', 
                        suffixes=('', f'_{col}_Nama')
                    )
                    jadwal_dengan_nama = jadwal_dengan_nama.rename(columns={'Nama': f'{col}_Nama'})

            # --- LOGIKA STATUS W/L/T PER MATCH (BARU) ---
            def hitung_status_match(poin1, poin2):
                if poin1 > poin2: return 'W'
                if poin2 > poin1: return 'L'
                return 'T'

            for index, row in jadwal_dengan_nama.iterrows():
                
                match_data = row.to_dict()
                
                if row['Status'] == 'Selesai':
                    poin1, poin2 = row['Poin_Tim_1'], row['Poin_Tim_2']
                    
                    status_tim_1 = hitung_status_match(poin1, poin2)
                    status_tim_2 = hitung_status_match(poin2, poin1)
                    
                    # Konversi status ke format W/L/T (Contoh: Menang = 1/0/0)
                    wlt_tim_1 = {'W': '1/0/0', 'L': '0/1/0', 'T': '0/0/1'}.get(status_tim_1, '-')
                    wlt_tim_2 = {'W': '1/0/0', 'L': '0/1/0', 'T': '0/0/1'}.get(status_tim_2, '-')
                    
                    match_data['Status_Tim_1'] = wlt_tim_1
                    match_data['Status_Tim_2'] = wlt_tim_2
                else:
                    match_data['Status_Tim_1'] = '-'
                    match_data['Status_Tim_2'] = '-'
                
                jadwal_untuk_template.append(match_data)
            # ----------------------------------------------
            
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
        new_row = pd.DataFrame([{'ID': new_id, 'Nama': nama, 'Total_Poin': 0, 'Games_Played': 0, 'Total_Bye': 0, 'W': 0, 'L': 0, 'T': 0}])
        new_row = new_row.set_index('ID')
        pemain_df = pd.concat([pemain_df, new_row])
        
    return redirect(url_for('index'))

@app.route('/hapus_pemain/<int:player_id>', methods=['POST'])
def hapus_pemain(player_id):
    global pemain_df, jadwal_df, putaran_saat_ini
    
    if player_id in pemain_df.index:
        pemain_df.drop(player_id, inplace=True)
        
        cols_to_check = ['Pemain_1_A', 'Pemain_1_B', 'Pemain_2_A', 'Pemain_2_B']
        
        jadwal_saat_ini_idx = jadwal_df[jadwal_df['Putaran'] == putaran_saat_ini].index
        
        indices_to_drop = []
        for idx in jadwal_saat_ini_idx:
            is_involved = False
            for col in cols_to_check:
                if jadwal_df.loc[idx, col] == player_id:
                    is_involved = True
                    break
            
            if is_involved:
                indices_to_drop.append(idx)
        
        if indices_to_drop:
            jadwal_df.drop(indices_to_drop, inplace=True)
        
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

    jadwal_df = jadwal_df[jadwal_df['Status'] == 'Selesai'] 
    
    putaran_saat_ini += 1
    
    last_config['num_lapangan'] = num_lapangan
    last_config['format_turnamen'] = format_turnamen
    last_config['mode_permainan'] = mode_permainan
    
    if 'Games_Played' not in pemain_df.columns: pemain_df['Games_Played'] = 0
    if 'Total_Bye' not in pemain_df.columns: pemain_df['Total_Bye'] = 0

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
        
        jadwal_df = jadwal_df[jadwal_df['Putaran'] != putaran_saat_ini]

        num_lapangan = len(jadwal_saat_ini['Lapangan'].unique()) 
        format_turnamen = request.form.get('format_turnamen_ulang')
        mode_permainan = request.form.get('mode_permainan_ulang') 
        
        last_config['num_lapangan'] = num_lapangan
        last_config['format_turnamen'] = format_turnamen
        last_config['mode_permainan'] = mode_permainan

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
            
            p1b = match_row.get('Pemain_1_B')
            p2b = match_row.get('Pemain_2_B')
            
            pemain_ids_team_1 = [id for id in [match_row['Pemain_1_A'], p1b] if pd.notna(id)]
            pemain_ids_team_2 = [id for id in [match_row['Pemain_2_A'], p2b] if pd.notna(id)]
            
            pemain_ids_all = [id for id in pemain_ids_team_1 + pemain_ids_team_2 if id in pemain_df.index]

            # 1. Kurangi Poin dan Games_Played Lama (untuk update skor/reset)
            if match_row['Status'] == 'Selesai':
                poin_lama_tim_1 = match_row['Poin_Tim_1']
                poin_lama_tim_2 = match_row['Poin_Tim_2']
                
                # Kurangi Poin dan Games Played (1)
                for id in pemain_ids_team_1:
                    if id in pemain_df.index:
                        pemain_df.loc[id, 'Total_Poin'] -= poin_lama_tim_1
                        pemain_df.loc[id, 'Games_Played'] -= 1 
                
                for id in pemain_ids_team_2:
                    if id in pemain_df.index:
                        pemain_df.loc[id, 'Total_Poin'] -= poin_lama_tim_2
                        pemain_df.loc[id, 'Games_Played'] -= 1 
                        
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

            # 4. Tambah Games_Played Baru (1 per match/round)
            for id in pemain_ids_all:
                 if id in pemain_df.index:
                     pemain_df.loc[id, 'Games_Played'] += 1 
                    
    
    # --- Otomatis Buat Jadwal Putaran Berikutnya ---
    current_round_matches = jadwal_df[jadwal_df['Putaran'] == putaran_saat_ini]
    
    if not current_round_matches.empty and (current_round_matches['Status'] == 'Selesai').all():
        
        jadwal_df = jadwal_df[jadwal_df['Putaran'] < putaran_saat_ini] 
        
        putaran_saat_ini += 1
        
        num_lapangan = last_config['num_lapangan']
        format_turnamen = last_config['format_turnamen']
        mode_permainan = last_config['mode_permainan']
        
        prev_putaran = putaran_saat_ini - 1
        
        players_per_court = 4 if last_config['mode_permainan'] == 'Double' else 2
        num_courts = last_config['num_lapangan']
        max_players_to_be_scheduled = num_courts * players_per_court
        
        if 'Games_Played' not in pemain_df.columns: pemain_df['Games_Played'] = 0
        if 'Total_Bye' not in pemain_df.columns: pemain_df['Total_Bye'] = 0
        if 'Random_Tie_Breaker' not in pemain_df.columns: pemain_df['Random_Tie_Breaker'] = 0
        
        pemain_potensial_prev = pemain_df.sort_values(
            by=['Total_Bye', 'Games_Played', 'Total_Poin', 'Random_Tie_Breaker'], 
            ascending=[False, True, False, True] 
        ).index.tolist()
        
        pemain_potensial_prev = pemain_potensial_prev[:max_players_to_be_scheduled + players_per_court]
        
        prev_matches = jadwal_df[jadwal_df['Putaran'] == prev_putaran]
        players_who_played_prev = set(prev_matches[['Pemain_1_A', 'Pemain_1_B', 'Pemain_2_A', 'Pemain_2_B']].stack().dropna().tolist())
        
        players_on_bye_prev = [id for id in pemain_potensial_prev if id not in players_who_played_prev]
        
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
    
    # 1. Hitung W/L/T final dan Peringkat
    pemain_final = hitung_wlt(pemain_df.copy(), jadwal_df.copy())
    
    pemain_final['Peringkat'] = pemain_final['Total_Poin'].rank(method='min', ascending=False).astype(int)
    pemain_final = pemain_final.sort_values(by=['Peringkat', 'Total_Poin'], ascending=[True, False])
    
    # 2. Siapkan data untuk template
    kolom_rekap = [
        'Peringkat', 
        'Nama', 
        'Total_Poin', 
        'W', 'L', 'T', 
        'Games_Played'
    ]
    rekap_df = pemain_final.reset_index()
    rekap_df = rekap_df[kolom_rekap].reset_index(drop=True)
    
    return render_template(
        'rekap.html', 
        rekap=rekap_df.to_dict('records')
    )

if __name__ == '__main__':
    app.run(debug=True)
