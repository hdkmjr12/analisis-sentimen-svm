from apify_client import ApifyClient
import pandas as pd
import sys
import os


print("="*50)
print("  PROGRAM SCRAPING KOMENTAR TIKTOK")
print("="*50)

TIKTOK_URL = input("Masukkan link video TikTok target : ").strip()


if not TIKTOK_URL:
    print("❌ Error: Link TikTok tidak boleh kosong!")
    sys.exit()


try:
    input_jumlah = input("Masukkan target jumlah komentar (Default: 100) : ")
    target_jumlah = int(input_jumlah) if input_jumlah.strip() else 100
except ValueError:
    print("⚠️ Input bukan angka! Sistem menggunakan default 500.")
    target_jumlah = 500


nama_dasar = 'hasil_scraping_tiktok'
ekstensi = '.csv'
nama_file = f"{nama_dasar}{ekstensi}"
angka = 2


while os.path.exists(nama_file):
    nama_file = f"{nama_dasar}{angka}{ekstensi}"
    angka += 1



client = ApifyClient("apify_api_h9QEhcQamxVAA63EO9gHeNqKWTet5k2xmGZz")


run_input = {
    "postURLs": [TIKTOK_URL],
    "commentsPerPost": target_jumlah,
    "maxRepliesPerComment": 0, 
}

print(f"\n⏳ Sedang memproses {target_jumlah} komentar dari TikTok via Apify...")
print(f"🔗 Link Target: {TIKTOK_URL}")

try:
    
    run = client.actor("clockworks/tiktok-comments-scraper").call(run_input=run_input)
except Exception as e:
    print(f"\n❌ Error saat terhubung ke Apify: {e}")
    sys.exit()


items = []
for item in client.dataset(run["defaultDatasetId"]).iterate_items():
    items.append(item)


if items:
    df = pd.DataFrame(items)
    
    
    if 'createTime' in df.columns:
        df['tanggal_format'] = pd.to_datetime(df['createTime'], unit='s').dt.strftime('%Y-%m-%d %H:%M:%S')
    else:
        df['tanggal_format'] = "N/A"

    
    if 'text' in df.columns:
        df_final = df[['text', 'tanggal_format']].copy()
        
        
        df_final['text'] = df_final['text'].replace(r'\n|\r', ' ', regex=True)
        
        
        df_final = df_final.rename(columns={
            'text': 'review',
            'tanggal_format': 'tanggal komentar'
        })
        
        
        df_final.to_csv(nama_file, index=False, encoding='utf-8-sig')
        
        print(f"\n SELESAI! {len(df_final)} komentar berhasil disimpan ke file '{nama_file}'.")
    else:
        print("\n⚠️ Data komentar ('text') tidak ditemukan dalam hasil yang ditarik.")
else:
    print("\n⚠️ Tidak ada data yang berhasil diambil. Pastikan link valid dan video memiliki komentar.")