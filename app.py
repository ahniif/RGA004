import random
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, Response

# --- Konfigurasi Turnamen ---
MAX_PEMAIN = 32

# Inisialisasi Aplikasi Flask
app = Flask(__name__)

# --- Manajemen Data dengan Pandas (Simulasi Database) ---
if 'pemain_df' not in globals():
    # 'Total_Poin' = Cumulative Score (Skor mentah). 'Ranking_W_L' = W - L (Skor Peringkat).
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

# --- Fungsi Utility ---

def get_player_id(nama_atau_id):
    """Mendapatkan ID pemain dari nama, atau mengembalikan ID jika sudah int."""
    global pemain_df
    if pd.isna(nama_atau_id) or nama_atau_id == 'Bye':
        return None
    try:
        # Cek apakah input adalah ID (integer)
        player_id = int(nama_atau_id)
        if player_id in pemain_df.index:
            return player_id
    except ValueError:
        # Input adalah Nama (string)
        # Cari pemain berdasarkan Nama dan kembalikan ID-nya
        match = pemain_df[pemain_df['Nama'].str.lower() == str(nama_atau_id).lower()]
        if not match.empty:
            return match.index[0]
    return None

def safe_get_player_id_list(names_or_ids):
    """Mengembalikan list ID pemain yang valid dan tidak None."""
    return [get_player_id(x) for x in names_or_ids if get_player_id(x) is not None]

# --- REVISI FUNGSI PERHITUNGAN STATISTIK ---

def hitung_games_played(pemain_df_input, jadwal_df_input):
    """
    Menghitung Games_Played sebagai jumlah total pertandingan (round) yang diselesaikan 
    oleh setiap pemain (Revisi #1: Total Round Partisipasi).
    """
    pemain_df = pemain_df_input.copy()
    if 'Games_Played' not in pemain_df.columns:
        pemain_df['Games_Played'] = 0
    pemain_df['Games_Played'] = 0 # RESET Games_Played
    
    jadwal_selesai = jadwal_df_input[jadwal_df_input['Status'] == 'Selesai']
    
    for _, match in jadwal_selesai.iterrows():
        id_cols = ['Pemain_1_A', 'Pemain_1_B', 'Pemain_2_A', 'Pemain_2_B']
        pemain_dalam_match = [get_player_id(match[col]) for col in id_cols]
        
        # Hanya hitung 1 Games_Played per pemain per pertandingan
        for p_id in set([p for p in pemain_dalam_match if p is not None]):
            if p_id in pemain_df.index:
                pemain_df.loc[p_id, 'Games_Played'] += 1
                
    return pemain_df[['Games_Played']] # Hanya kembalikan Games_Played


def hitung_wlt(pemain_df_input, jadwal_df_input):
    """
    Menghitung Win/Lose/Tie (W/L/T) dan Ranking_W_L (W - L) 
    berdasarkan hasil akhir setiap pertandingan Selesai (Revisi #2: Status W/L/T berdasarkan Menang/Kalah/Seri).
    """
    
    pemain_df = pemain_df_input.copy()
    jadwal_df = jadwal_df_input.copy()
    
    # Inisialisasi/Reset kolom W/L/T
    for col in ['W', 'L', 'T']:
        if col not in pemain_df.columns:
            pemain_df[col] = 0
        pemain_df[col] = 0 # RESET W/L/T
    
    jadwal_selesai = jadwal_df[jadwal_df['Status'] == 'Selesai']
    
    for _, match in jadwal_selesai.iterrows():
        # Dapatkan ID pemain
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
                if p_id in pemain_df.index:
                    pemain_df.loc[p_id, 'T'] += 1
                
    # Hitung Ranking Poin = W - L
    if 'W' in pemain_df.columns and 'L' in pemain_df.columns:
        pemain_df['Ranking_W_L'] = pemain_df['W'] - pemain_df['L']
    else:
        pemain_df['Ranking_W_L'] = 0
                    
    return pemain_df

# --- FUNGSI ROUTE FLASK ---

@app.route('/', methods=['GET', 'POST'])
def index():
    global pemain_df, jadwal_df, next_player_id, putaran_saat_ini

    if request.method == 'POST':
        if 'nama' in request.form:
            # Tambah Pemain
            nama = request.form['nama'].strip()
            if nama and len(pemain_df) < MAX_PEMAIN:
                # Tambahkan inisialisasi kolom baru
                new_player = pd.DataFrame([{'ID': next_player_id, 'Nama': nama, 'Total_Poin': 0, 'Games_Played': 0, 'Total_Bye': 0, 'W': 0, 'L': 0, 'T': 0, 'Ranking_W_L': 0}])
                new_player.set_index('ID', inplace=True)
                pemain_df = pd.concat([pemain_df, new_player])
                next_player_id += 1
            
            return redirect(url_for('index'))

    # Hitung statistik untuk tampilan
    peringkat = pd.DataFrame()
    if not pemain_df.empty:
        # Panggil fungsi W/L/T dan Ranking_W_L (W-L)
        pemain_df_temp = hitung_wlt(pemain_df.copy(), jadwal_df.copy())
        
        # Panggil fungsi Games_Played yang baru
        pemain_df_games_played = hitung_games_played(pemain_df.copy(), jadwal_df.copy())
        
        # Gabungkan Games_Played ke pemain_df_temp
        pemain_df_temp = pemain_df_temp.merge(
            pemain_df_games_played,
            left_index=True, right_index=True, how='left'
        )
        
        # Pastikan kolom Total_Poin juga ada dari pemain_df global
        if 'Total_Poin' in pemain_df.columns:
            pemain_df_temp['Total_Poin'] = pemain_df['Total_Poin']

        # --- LOGIKA RANKING ---
        # 1. Ranking_W_L (W - L) DESC
        # 2. Total_Poin DESC
        # 3. Games_Played ASC 
        pemain_df_temp = pemain_df_temp.sort_values(
            by=['Ranking_W_L', 'Total_Poin', 'Games_Played'], 
            ascending=[False, False, True]
        )
        pemain_df_temp['Peringkat'] = range(1, len(pemain_df_temp) + 1)
        # ---------------------
        
        peringkat = pemain_df_temp.reset_index().to_dict('records')
    
    # Ambil jadwal putaran saat ini yang belum selesai
    jadwal_aktif = jadwal_df[
        (jadwal_df['Putaran'] == putaran_saat_ini) & 
        (jadwal_df['Status'] != 'Selesai')
    ].to_dict('index')

    # Pemain yang tidak bermain (Bye)
    pemain_bye = jadwal_df[
        (jadwal_df['Putaran'] == putaran_saat_ini) & 
        (jadwal_df['Pemain_1_A'].str.contains('Bye', na=False) |
         jadwal_df['Pemain_1_B'].str.contains('Bye', na=False) |
         jadwal_df['Pemain_2_A'].str.contains('Bye', na=False) |
         jadwal_df['Pemain_2_B'].str.contains('Bye', na=False)
        )
    ]['Pemain_1_A'].tolist() # Asumsi Bye selalu di P1A untuk putaran saat ini

    return render_template('index.html', 
                           pemain=peringkat, 
                           putaran=putaran_saat_ini, 
                           jadwal_aktif=jadwal_aktif,
                           pemain_bye=pemain_bye)

@app.route('/hapus_pemain/<int:player_id>', methods=['POST'])
def hapus_pemain(player_id):
    global pemain_df, jadwal_df

    if player_id in pemain_df.index:
        # Hapus pemain dari daftar pemain
        pemain_df.drop(player_id, inplace=True)
        
        # Hapus pertandingan dari jadwal yang melibatkan pemain tersebut
        player_name = str(player_id)
        
        columns_to_check = ['Pemain_1_A', 'Pemain_1_B', 'Pemain_2_A', 'Pemain_2_B']
        
        # Cari baris yang mengandung nama pemain (string) atau ID pemain (int, di convert jadi string)
        indices_to_drop = jadwal_df[
            (jadwal_df[columns_to_check].astype(str) == player_name).any(axis=1)
        ].index
        
        if not indices_to_drop.empty:
            jadwal_df.drop(indices_to_drop, inplace=True)
            
        # Hitung ulang W/L/T & Ranking_W_L
        pemain_df_temp = hitung_wlt(pemain_df.copy(), jadwal_df.copy())
        
        # Hitung ulang Games_Played
        pemain_df_games_played = hitung_games_played(pemain_df.copy(), jadwal_df.copy())
        
        # Update kolom statistik ke pemain_df global
        for col in ['W', 'L', 'T', 'Ranking_W_L']:
            if col in pemain_df_temp.columns:
                pemain_df[col] = pemain_df_temp[col]
        
        if 'Games_Played' in pemain_df_games_played.columns:
            pemain_df['Games_Played'] = pemain_df_games_played['Games_Played']
            
    return redirect(url_for('index'))


@app.route('/input_skor/<int:match_id>', methods=['POST'])
def input_skor(match_id):
    global jadwal_df, pemain_df
    
    skor_tim_1_str = request.form.get('skor_tim_1')
    skor_tim_2_str = request.form.get('skor_tim_2')

    try:
        skor_tim_1 = int(skor_tim_1_str)
        skor_tim_2 = int(skor_tim_2_str)
    except ValueError:
        return redirect(url_for('index')) 

    if skor_tim_1 >= 0 and skor_tim_2 >= 0:
        
        if match_id in jadwal_df.index:
            
            match_row = jadwal_df.loc[match_id].copy()
            
            pemain_ids_team_1 = safe_get_player_id_list([match_row['Pemain_1_A'], match_row['Pemain_1_B']])
            pemain_ids_team_2 = safe_get_player_id_list([match_row['Pemain_2_A'], match_row['Pemain_2_B']])
            
            # 1. Update Jadwal
            jadwal_df.loc[match_id, ['Poin_Tim_1', 'Poin_Tim_2']] = [skor_tim_1, skor_tim_2]
            jadwal_df.loc[match_id, 'Status'] = 'Selesai'

            # 2. Update Total Poin Pemain (Cumulative Score)
            # Logika: Kurangi Poin Lama (jika match sudah selesai sebelumnya) lalu Tambah Poin Baru
            
            if match_row['Status'] == 'Selesai':
                poin_lama_tim_1 = match_row['Poin_Tim_1']
                poin_lama_tim_2 = match_row['Poin_Tim_2']
                
                for id in pemain_ids_team_1:
                    if id in pemain_df.index:
                        pemain_df.loc[id, 'Total_Poin'] -= poin_lama_tim_1
                
                for id in pemain_ids_team_2:
                    if id in pemain_df.index:
                        pemain_df.loc[id, 'Total_Poin'] -= poin_lama_tim_2
            
            # Tambah Poin Baru
            for id in pemain_ids_team_1:
                if id in pemain_df.index:
                    pemain_df.loc[id, 'Total_Poin'] += skor_tim_1

            for id in pemain_ids_team_2:
                if id in pemain_df.index:
                    pemain_df.loc[id, 'Total_Poin'] += skor_tim_2

            # 3. HITUNG ULANG W/L/T & Ranking_W_L (W-L) dan Games_Played
            pemain_df_temp = hitung_wlt(pemain_df.copy(), jadwal_df.copy())
            pemain_df_games_played = hitung_games_played(pemain_df.copy(), jadwal_df.copy())
            
            # Update kembali W, L, T, Ranking_W_L, dan Games_Played ke pemain_df global
            for col in ['W', 'L', 'T', 'Ranking_W_L']:
                if col in pemain_df_temp.columns:
                    pemain_df[col] = pemain_df_temp[col]

            if 'Games_Played' in pemain_df_games_played.columns:
                pemain_df['Games_Played'] = pemain_df_games_played['Games_Played']
            
    return redirect(url_for('index'))

# Fungsi untuk menghasilkan jadwal putaran
@app.route('/generasi_jadwal', methods=['POST'])
def generasi_jadwal():
    global pemain_df, jadwal_df, putaran_saat_ini, next_match_id

    # Hanya pemain yang tidak 'Bye' di putaran terakhir yang dimasukkan (jika putaran > 0)
    pemain_aktif_df = pemain_df.copy()

    # 1. Pastikan semua statistik dihitung ulang sebelum putaran baru
    if not pemain_aktif_df.empty:
        # Hitung Games_Played dan W/L/T
        pemain_df_stats = hitung_wlt(pemain_aktif_df.copy(), jadwal_df.copy())
        pemain_df_games_played = hitung_games_played(pemain_aktif_df.copy(), jadwal_df.copy())
        
        pemain_aktif_df = pemain_df_stats.merge(
            pemain_df_games_played,
            left_index=True, right_index=True, how='left'
        )
        
        if 'Total_Poin' not in pemain_aktif_df.columns and 'Total_Poin' in pemain_df.columns:
             pemain_aktif_df['Total_Poin'] = pemain_df['Total_Poin']

    # --- LOGIKA RANKING UNTUK SWISS LADDER ---
    # Jika sudah ada putaran, ranking diurutkan untuk pasangan yang lebih adil
    if putaran_saat_ini > 0:
        # 1. Ranking_W_L (W - L) DESC
        # 2. Total_Poin DESC
        # 3. Games_Played ASC 
        pemain_aktif_df = pemain_aktif_df.sort_values(
            by=['Ranking_W_L', 'Total_Poin', 'Games_Played'], 
            ascending=[False, False, True]
        )
    # Putaran 1 (Random Pairing)
    else:
        # Acak pemain (untuk Putaran 1)
        pemain_aktif_df = pemain_aktif_df.sample(frac=1).copy()
        
    # --- PROSES GENERASI PASANGAN ---
    list_pemain = pemain_aktif_df.index.tolist()
    new_matches = []
    lapangan_counter = 1
    
    # Penanganan Bye (jika jumlah pemain ganjil)
    bye_player_id = None
    if len(list_pemain) % 2 != 0:
        
        # Logika Swiss: Pemain dengan ranking terendah yang belum Bye mendapat Bye.
        # Atau, jika putaran 1, pemain terakhir di list acak mendapat Bye.
        
        # Cari pemain yang Total_Bye-nya paling sedikit dan Ranking_W_L-nya paling kecil
        pemain_bye_candidates = pemain_aktif_df.sort_values(
            by=['Total_Bye', 'Ranking_W_L'], 
            ascending=[True, True]
        ).index.tolist()
        
        # Pilih kandidat pertama dari list yang diurutkan
        for p_id in pemain_bye_candidates:
            if p_id in list_pemain:
                bye_player_id = p_id
                list_pemain.remove(bye_player_id)
                break
        
        # Catat Bye
        if bye_player_id is not None:
            # Tambahkan 1 ke Total_Bye pemain_df global
            if bye_player_id in pemain_df.index:
                pemain_df.loc[bye_player_id, 'Total_Bye'] = pemain_df.loc[bye_player_id, 'Total_Bye'] + 1
            
            # Buat match 'Bye' agar tercatat di jadwal
            new_matches.append({
                'Match_ID': next_match_id,
                'Putaran': putaran_saat_ini + 1,
                'Lapangan': 0, # Lapangan 0 untuk Bye
                'Mode': 'Bye',
                'Pemain_1_A': pemain_aktif_df.loc[bye_player_id, 'Nama'], 
                'Pemain_1_B': 'Bye',
                'Pemain_2_A': 'Bye', 
                'Pemain_2_B': 'Bye',
                'Poin_Tim_1': 0, 'Poin_Tim_2': 0,
                'Status': 'Selesai'
            })
            next_match_id += 1


    # Proses Pasangan (Swiss Ladder Pairing)
    
    # 1. Cek apakah ada jadwal aktif yang belum selesai
    if not jadwal_df[jadwal_df['Status'] != 'Selesai'].empty:
        # Jika ada match yang belum selesai, jangan buat putaran baru
        return "Terdapat pertandingan yang belum selesai di putaran saat ini. Mohon selesaikan semua skor terlebih dahulu.", 400

    
    while len(list_pemain) >= 2:
        p1_id = list_pemain.pop(0) # Ambil pemain rank teratas
        
        # Cari pasangan yang belum pernah dilawan (atau pasangannya di putaran yang sama)
        found_pair = False
        p2_id = None
        
        for i, potential_p2_id in enumerate(list_pemain):
            
            # Cek apakah p1_id pernah melawan/setim dengan potential_p2_id
            
            def is_pair_found(row, p1, p2):
                p1_cols = [row['Pemain_1_A'], row['Pemain_1_B'], row['Pemain_2_A'], row['Pemain_2_B']]
                p1_ids = [get_player_id(x) for x in p1_cols]
                
                # Cek apakah p1 dan p2 ada di daftar pemain di match ini
                return (p1 in p1_ids) and (p2 in p1_ids)
                
            
            has_played = jadwal_df.apply(lambda row: is_pair_found(row, p1_id, potential_p2_id), axis=1).any()

            if not has_played:
                p2_id = potential_p2_id
                list_pemain.pop(i) # Hapus pasangan yang ditemukan
                found_pair = True
                break
        
        # Jika pasangan tidak ditemukan, pasangkan dengan yang berikutnya (terendah ranking)
        if not found_pair:
            p2_id = list_pemain.pop(0)

        # Jika masih ada pemain aktif, buat match (Asumsi Singles 1 vs 1)
        if p1_id is not None and p2_id is not None:
            
            p1_name = pemain_aktif_df.loc[p1_id, 'Nama']
            p2_name = pemain_aktif_df.loc[p2_id, 'Nama']
            
            # Acak posisi tim (p1 vs p2 atau p2 vs p1)
            if random.choice([True, False]):
                new_matches.append({
                    'Match_ID': next_match_id,
                    'Putaran': putaran_saat_ini + 1,
                    'Lapangan': lapangan_counter,
                    'Mode': 'Singles',
                    'Pemain_1_A': p1_name, 'Pemain_1_B': None,
                    'Pemain_2_A': p2_name, 'Pemain_2_B': None,
                    'Poin_Tim_1': 0, 'Poin_Tim_2': 0,
                    'Status': 'Akan Datang'
                })
            else:
                 new_matches.append({
                    'Match_ID': next_match_id,
                    'Putaran': putaran_saat_ini + 1,
                    'Lapangan': lapangan_counter,
                    'Mode': 'Singles',
                    'Pemain_1_A': p2_name, 'Pemain_1_B': None,
                    'Pemain_2_A': p1_name, 'Pemain_2_B': None,
                    'Poin_Tim_1': 0, 'Poin_Tim_2': 0,
                    'Status': 'Akan Datang'
                })
            
            next_match_id += 1
            lapangan_counter += 1
            
    # Update putaran dan jadwal_df
    if new_matches:
        new_jadwal_df = pd.DataFrame(new_matches)
        new_jadwal_df.set_index('Match_ID', inplace=True) 
        # Cek tipe data sebelum concat (Poin_Tim_X harus int/float)
        new_jadwal_df['Poin_Tim_1'] = new_jadwal_df['Poin_Tim_1'].astype(int)
        new_jadwal_df['Poin_Tim_2'] = new_jadwal_df['Poin_Tim_2'].astype(int)
        
        jadwal_df = pd.concat([jadwal_df, new_jadwal_df])
        
        putaran_saat_ini += 1 # Tambahkan putaran hanya jika match berhasil digenerate
            
    return redirect(url_for('index'))

# ROUTE BARU: Menampilkan Rekap Visual
@app.route('/rekap_visual')
def rekap_visual():
    global pemain_df, jadwal_df
    
    pemain_copy = pemain_df.copy()

    # 1. Hitung W/L/T dan Ranking_W_L (W-L) final
    pemain_final = hitung_wlt(pemain_copy.copy(), jadwal_df.copy())
    
    # Hitung Games_Played
    pemain_final = pemain_final.merge(
        hitung_games_played(pemain_copy.copy(), jadwal_df.copy()),
        left_index=True, right_index=True, how='left'
    )
    
    # Tambahkan Total_Poin dan Random_Tie_Breaker (jika ada)
    if 'Total_Poin' in pemain_copy.columns:
        pemain_final['Total_Poin'] = pemain_copy['Total_Poin']
    else:
        pemain_final['Total_Poin'] = 0
        
    if 'Random_Tie_Breaker' not in pemain_final.columns:
        # Tambahkan Tie Breaker random jika belum ada
        pemain_final['Random_Tie_Breaker'] = [random.random() for _ in range(len(pemain_final))]
    
    # --- LOGIKA RANKING FINAL ---
    # 1. Ranking_W_L (W - L) DESC (Perubahan Peringkat Utama)
    # 2. Total_Poin DESC (Tie Breaker 1)
    # 3. Games_Played ASC (Tie Breaker 2: Semakin sedikit Games Played semakin baik)
    # 4. Random_Tie_Breaker ASC (Tie Breaker 3: Acak)
    pemain_final = pemain_final.sort_values(
        by=['Ranking_W_L', 'Total_Poin', 'Games_Played', 'Random_Tie_Breaker'], 
        ascending=[False, False, True, True]
    )
    pemain_final['Peringkat'] = range(1, len(pemain_final) + 1)
    # ------------------------------------
    
    # 2. Siapkan data untuk template
    kolom_rekap = [
        'Peringkat', 
        'Nama', 
        'Total_Poin', # Poin kumulatif
        'Games_Played', 
        'W', 'L', 'T', 
        'Ranking_W_L' # W - L (Skor Peringkat)
    ]
    
    # Pilih kolom yang relevan dan konversi ke list dict
    rekap_list = pemain_final.reset_index()[kolom_rekap].to_dict('records')
    
    return render_template('rekap.html', 
                           rekap=rekap_list, 
                           putaran=jadwal_df['Putaran'].max() if not jadwal_df.empty else 0)

# Export data ke CSV
@app.route('/export_data')
def export_data():
    global pemain_df, jadwal_df
    
    # Pastikan data dihitung ulang sebelum export
    pemain_copy = pemain_df.copy()
    
    pemain_final = hitung_wlt(pemain_copy.copy(), jadwal_df.copy())
    pemain_final = pemain_final.merge(
        hitung_games_played(pemain_copy.copy(), jadwal_df.copy()),
        left_index=True, right_index=True, how='left'
    )
    pemain_final['Total_Poin'] = pemain_copy['Total_Poin']

    # Konversi dataframes ke CSV string
    pemain_csv = pemain_final.to_csv(index=True)

    response = Response(
        pemain_csv,
        mimetype="text/csv",
        headers={"Content-disposition":
                 "attachment; filename=rekap_pemain_final.csv"}
    )
    return response

if __name__ == '__main__':
    app.run(debug=True)
