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
    """Menghitung Win/Lose/Tie berdasarkan semua pertandingan Selesai."""
    
    # Inisialisasi kolom W/L/T jika belum ada
    if 'W' not in pemain_df.columns:
        pemain_df['W'] = 0
        pemain_df['L'] = 0
        pemain_df['T'] = 0

    # Reset nilai W/L/T untuk perhitungan baru
    pemain_df['W'] = 0
    pemain_df['L'] = 0
    pemain_df['T'] = 0
    
    jadwal_selesai = jadwal_df[jadwal_df['Status'] == 'Selesai']
    
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
                    
    return pemain_df
    
def buat_jadwal(pemain_df, putaran, num_lapangan, mode_permainan, format_turnamen):
    """
    Membuat jadwal baru, memprioritaskan pemain dengan Total_Bye terbanyak
    untuk memastikan semua pemain mendapat giliran bermain.
    """
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
                H1, H2 = peringkat_tinggi[i*2], peringkat_tinggi[i*2 + 1]
                L1, L2 = peringkat_rendah[i*2], peringkat_rendah[i*2 + 1]
                
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
            
            num_matches = len(pemain_bermain_df_sorted) // 2
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
#                    ROUTE APLIKASI
# ----------------------------------------------------

@app.route('/')
def index():
    global pemain_df, jadwal_df, putaran_saat_ini, last_config

    if 'Total_Bye' not in pemain_df.columns:
         pemain_df['Total_Bye'] = 0
    
    peringkat = pd.DataFrame()
    if not pemain_df.empty:
        # Panggil fungsi W/L/T
        pemain_df_temp = hitung_wlt(pemain_df.copy(), jadwal_df.copy())
        
        peringkat = pemain_df_temp.copy()
        peringkat['Peringkat'] = peringkat['Total_Poin'].rank(method='min', ascending=False).astype(int)
        peringkat = peringkat.sort_values(by=['Peringkat', 'Total_Poin'], ascending=[True, False])
        
        # PERBAIKAN: Mengubah Index 'ID' menjadi Kolom 'ID'
        peringkat = peringkat.reset_index(names=['ID'])
        

    jadwal_saat_ini = jadwal_df[jadwal_df['Putaran'] == putaran_saat_ini].reset_index()
    jadwal_untuk_template = []
    
    can_reshuffle = False
    current_mode = None
    pemain_bye = []
    current_format = None

    if not jadwal_saat_ini.empty:
        current_mode = jadwal_saat_ini.loc[0, 'Mode']
        current_format = last_config['format_turnamen'] 
        players_per_court = 4 if current_mode == 'Double' else 2
        
        # 1. Tentukan Pemain yang Dapat Bye
        if 'Rank_Poin' not in pemain_df.columns:
             pemain_df['Rank_Poin'] = pemain_df['Total_Poin'].rank(method='min', ascending=False)
             
        pemain_potensial = pemain_df.sort_values(
            by=['Total_Bye', 'Rank_Poin'], 
            ascending=[False, False] 
        ).index.tolist()
        
        id_cols = ['Pemain_1_A', 'Pemain_1_B', 'Pemain_2_A', 'Pemain_2_B']
        pemain_yang_bermain_id = set()
        for col in id_cols:
            if col in jadwal_saat_ini.columns:
                pemain_yang_bermain_id.update(jadwal_saat_ini[col].dropna().tolist())

        num_courts_used = len(jadwal_saat_ini)
        max_players_scheduled = num_courts_used * players_per_court
        
        pemain_ranked = pemain_potensial[:max_players_scheduled + players_per_court]
        
        pemain_bye_ids = [id for id in pemain_ranked if id not in pemain_yang_bermain_id]
        
        # INCREMENT Total_Bye UNTUK PEMAIN YANG BYE
        if putaran_saat_ini > 0:
            pemain_df.loc[pemain_bye_ids, 'Total_Bye'] += 1
        
        pemain_bye = pemain_df.loc[pemain_bye_ids]['Nama'].tolist()
        
        # 2. Logika Jadwal dan Reshuffle
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
        # Inisialisasi W/L/T
        new_row = pd.DataFrame([{'ID': new_id, 'Nama': nama, 'Total_Poin': 0, 'Games_Played': 0, 'Total_Bye': 0, 'W': 0, 'L': 0, 'T': 0}])
        new_row = new_row.set_index('ID')
        pemain_df = pd.concat([pemain_df, new_row])
        
    return redirect(url_for('index'))

@app.route('/hapus_pemain/<int:player_id>', methods=['POST'])
def hapus_pemain(player_id):
    global pemain_df, jadwal_df, putaran_saat_ini
    
    if player_id in pemain_df.index:
        # Hapus pemain dari DataFrame pemain
        pemain_df.drop(player_id, inplace=True)
        
        # Hapus pemain dari jadwal yang BELUM SELESAI
        cols_to_check = ['Pemain_1_A', 'Pemain_1_B', 'Pemain_2_A', 'Pemain_2_B']
        
        # Hanya putaran saat ini yang mungkin perlu dikoreksi
        jadwal_saat_ini_idx = jadwal_df[jadwal_df['Putaran'] == putaran_saat_ini].index
        
        # Hapus match jika pemain terlibat
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

    jadwal_df = jadwal_df[jadwal_df['Status'] == 'Selesai'] 
    
    putaran_saat_ini += 1
    
    last_config['num_lapangan'] = num_lapangan
    last_config['format_turnamen'] = format_turnamen
    last_config['mode_permainan'] = mode_permainan
    
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
            
            pemain_ids_team_1 = [id for id in [match_row['Pemain_1_A'], match_row['Pemain_1_B']] if id is not None]
            pemain_ids_team_2 = [id for id in [match_row['Pemain_2_A'], match_row['Pemain_2_B']] if id is not None]
            
            pemain_ids_all = pemain_ids_team_1 + pemain_ids_team_2

            # 1. Kurangi Poin Lama (untuk update skor)
            if match_row['Status'] == 'Selesai':
                poin_lama_tim_1 = match_row['Poin_Tim_1']
                poin_lama_tim_2 = match_row['Poin_Tim_2']
                
                for id in pemain_ids_team_1:
                    if id in pemain_df.index:
                        pemain_df.loc[id, 'Total_Poin'] -= poin_lama_tim_1
                
                for id in pemain_ids_team_2:
                    if id in pemain_df.index:
                        pemain_df.loc[id, 'Total_Poin'] -= poin_lama_tim_2
                        
            # 2. Tambah Games_Played (hanya jika match baru selesai)
            if match_row['Status'] != 'Selesai':
                 total_points_in_match = skor_tim_1 + skor_tim_2
                 for id in pemain_ids_all:
                      if id in pemain_df.index:
                          pemain_df.loc[id, 'Games_Played'] += total_points_in_match 
                      
            # 3. Update Jadwal
            jadwal_df.loc[match_id, ['Poin_Tim_1', 'Poin_Tim_2']] = [skor_tim_1, skor_tim_2]
            jadwal_df.loc[match_id, 'Status'] = 'Selesai'
            
            # 4. Tambah Poin Baru ke Total Poin Pemain
            for id in pemain_ids_team_1:
                if id in pemain_df.index:
                    pemain_df.loc[id, 'Total_Poin'] += skor_tim_1

            for id in pemain_ids_team_2:
                if id in pemain_df.index:
                    pemain_df.loc[id, 'Total_Poin'] += skor_tim_2

    
    # --- Otomatis Buat Jadwal Putaran Berikutnya ---
    current_round_matches = jadwal_df[jadwal_df['Putaran'] == putaran_saat_ini]
    
    if not current_round_matches.empty and (current_round_matches['Status'] == 'Selesai').all():
        
        jadwal_df = jadwal_df[jadwal_df['Status'] == 'Selesai'] 
        
        putaran_saat_ini += 1
        
        num_lapangan = last_config['num_lapangan']
        format_turnamen = last_config['format_turnamen']
        mode_permainan = last_config['mode_permainan']
        
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
    rekap_df = pemain_final[kolom_rekap].reset_index(drop=True)
    
    return render_template(
        'rekap.html', 
        rekap=rekap_df.to_dict('records')
    )

if __name__ == '__main__':
    app.run(debug=True)