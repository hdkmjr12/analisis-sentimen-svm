import pandas as pd
from youtube_comment_downloader import *
from datetime import datetime

downloader = YoutubeCommentDownloader()


YOUTUBE_URL = 'https://www.youtube.com/watch?v=dsFCts7o5rs'
nama_csv = 'hasil_scraping_youtube.csv'


target_jumlah = 100 

print(f"Mulai mengambil {target_jumlah} komentar utama dari YouTube...")

comments = downloader.get_comments_from_url(YOUTUBE_URL, sort_by=SORT_BY_POPULAR)

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
    
    print(f"\n\n🎉 Selesai! {jumlah_diambil} komentar utama berhasil disimpan ke '{nama_csv}'.")
    print("- Karakter 'Enter' sudah dihapus (baris tidak akan melar).")
    print("- Emoji tetap aman terbaca.")
    print("- Format tabel siap digunakan untuk analisis/preprocessing.")
else: