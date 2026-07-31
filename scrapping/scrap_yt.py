import pandas as pd
from youtube_comment_downloader import *
from datetime import datetime
import sys
import os  


print("="*50)
print("  PROGRAM SCRAPING KOMENTAR YOUTUBE (SKRIPSI)")
print("="*50)

YOUTUBE_URL = input("Masukkan link video YouTube target : ").strip()


if not YOUTUBE_URL:
    print("❌ Error: Link YouTube tidak boleh kosong!")
    sys.exit()


try:
    input_jumlah = input("Masukkan target jumlah komentar (Default: 500) : ")
    target_jumlah = int(input_jumlah) if input_jumlah.strip() else 500
except ValueError:
    print("⚠️ Input bukan angka! Sistem menggunakan default 500.")
    target_jumlah = 500


nama_dasar = 'hasil_scraping_youtube'
ekstensi = '.csv'
nama_csv = f"{nama_dasar}{ekstensi}"
angka = 2


while os.path.exists(nama_csv):
    nama_csv = f"{nama_dasar}{angka}{ekstensi}"
    angka += 1


downloader = YoutubeCommentDownloader()

print(f"\n⏳ Mulai mengambil {target_jumlah} komentar utama dari YouTube...")
print(f"🔗 Link Target: {YOUTUBE_URL}")

try:
    comments = downloader.get_comments_from_url(YOUTUBE_URL, sort_by=SORT_BY_POPULAR)
except Exception as e:
    print(f"\n❌ Error saat mengakses YouTube: {e}")
    print("Pastikan link yang Anda masukkan valid dan komputer terhubung ke internet.")
    sys.exit()

items = []
jumlah_diambil = 0

for comment in comments:
    
    if not comment.get('reply', False):
        
        
        
        teks_bersih = str(comment['text']).replace('\n', ' ').replace('\r', ' ')
        
        
        if 'time_parsed' in comment and comment['time_parsed']:
            
            tanggal = datetime.fromtimestamp(comment['time_parsed']).strftime('%Y-%m-%d %H:%M:%S')
        else:
            
            tanggal = comment.get('time', 'N/A')
            
        
        items.append({
            'review': teks_bersih,
            'tanggal komentar': tanggal
        })
        
        jumlah_diambil += 1
        print(f"Tersimpan: {jumlah_diambil}/{target_jumlah} komentar utama...", end='\r')
        
        
        if jumlah_diambil >= target_jumlah:
            break


if items:
    df = pd.DataFrame(items)
    
    
    df.to_csv(nama_csv, index=False, encoding='utf-8-sig')
    
    print(f"\n Selesai! {jumlah_diambil} berhasil disimpan ke '{nama_csv}'.")
    print("\n\n⚠️ Tidak ada komentar yang berhasil diambil.")