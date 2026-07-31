from apify_client import ApifyClient
import pandas as pd
import sys
import os

print("="*50)
print("  PROGRAM SCRAPING KOMENTAR INSTAGRAM")
print("="*50)

IG_URL = input("Masukkan link postingan Instagram target : ").strip()

if not IG_URL:
    print("❌ Error: Link Instagram tidak boleh kosong!")
    sys.exit()

try:
    input_jumlah = input("Masukkan target jumlah komentar (Default: 100) : ")
    target_jumlah = int(input_jumlah) if input_jumlah.strip() else 100
except ValueError:
    print("⚠️ Input bukan angka! Sistem menggunakan default 100.")
    target_jumlah = 100

nama_dasar = 'hasil_scraping_instagram'
ekstensi = '.csv'
nama_file = f"{nama_dasar}{ekstensi}"
angka = 2

while os.path.exists(nama_file):
    nama_file = f"{nama_dasar}{angka}{ekstensi}"
    angka += 1

client = ApifyClient("apify_api_h9QEhcQamxVAA63EO9gHeNqKWTet5k2xmGZz")

run_input = {
    "postUrls": [IG_URL],
    "maxCommentsPerPost": target_jumlah,
    "sortOrder": "popular",
}

print(f"\n⏳ Menghubungkan ke Apify dan menarik {target_jumlah} komentar Instagram...")
print(f"🔗 Link Target: {IG_URL}")

try:
    run = client.actor("499mNnuVGkU2S5rh1").call(run_input=run_input)
except Exception as e:
    print(f"\n❌ Error saat terhubung ke Apify: {e}")
    sys.exit()

items = []
for item in client.dataset(run["defaultDatasetId"]).iterate_items():
    items.append(item)

if items:
    df = pd.DataFrame(items)
    
    if 'timestamp' in df.columns:
        try:
            df['tanggal_format'] = pd.to_datetime(df['timestamp'], unit='s').dt.strftime('%Y-%m-%d %H:%M:%S')
        except ValueError:
            df['tanggal_format'] = pd.to_datetime(df['timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
    else:
        df['tanggal_format'] = "N/A"

    if 'text' in df.columns:
        df['text'] = df['text'].replace(r'\n|\r', ' ', regex=True)
        
        df_final = df[['text', 'tanggal_format']].copy()
        
        df_final = df_final.rename(columns={
            'text': 'review',
            'tanggal_format': 'tanggal komentar'
        })
        
        df_final.drop_duplicates(subset=['review'], keep='first', inplace=True)
        
        df_final.to_csv(nama_file, index=False, encoding='utf-8-sig')
        
        print(f"\n SELESAI! {len(df_final)} komentar unik berhasil disimpan ke '{nama_file}'.")
    else:
        print("\n⚠️ Kolom komentar ('text') tidak ditemukan.")
else:
    print("\n⚠️ Tidak ada data yang ditemukan. Pastikan link valid dan memiliki komentar.")