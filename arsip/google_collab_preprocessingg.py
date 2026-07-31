# =============================================================
# GOOGLE COLAB: Preprocessing Review LCGC (selaras website)
# =============================================================
# Cell awal (jalankan sekali pada Colab baru):
# !pip install Sastrawi pandas
#
# Upload DUA file sekaligus:
# 1. File CSV data mentah.
# 2. cgi-bin/text_pipeline.py dari proyek website terbaru.
# =============================================================
import io
import os
import sys
import pandas as pd
from google.colab import files
from IPython.display import display


def baca_csv(data_file):
    try:
        return pd.read_csv(io.BytesIO(data_file), encoding='utf-8-sig')
    except UnicodeDecodeError:
        return pd.read_csv(io.BytesIO(data_file), encoding='latin1')


print('LANGKAH 1/2 - Upload text_pipeline.py terbaru:')
uploaded_pipeline = files.upload()
nama_pipeline = next((n for n in uploaded_pipeline if 'text_pipeline' in n.lower() and n.lower().endswith('.py')), None)
if not nama_pipeline:
    raise ValueError('File text_pipeline.py belum dipilih.')
print('LANGKAH 2/2 - Upload satu CSV data mentah:')
uploaded_csv = files.upload()
nama_csv = next((n for n in uploaded_csv if n.lower().endswith('.csv')), None)
if not nama_csv:
    raise ValueError('File CSV belum dipilih.')

with open('text_pipeline.py', 'wb') as file_pipeline:
    file_pipeline.write(uploaded_pipeline[nama_pipeline])
sys.path.insert(0, os.getcwd())

from text_pipeline import buat_preprocessor, preprocess_teks, cek_kelayakan

df = baca_csv(uploaded_csv[nama_csv])
kolom_teks = next((k for k in ['teks_review', 'review', 'Review', 'komentar', 'Komentar', 'comment', 'text'] if k in df.columns), None)
if kolom_teks is None:
    raise ValueError('Kolom teks tidak ditemukan. Gunakan kolom teks_review atau review.')

stemmer, stopword = buat_preprocessor()
cache_stemming = {'berlaku': 'berlaku', 'favorit': 'favorit'}
hasil_preprocessing, status_kelayakan, alasan = [], [], []

for teks in df[kolom_teks].fillna('').astype(str):
    hasil = preprocess_teks(teks, stemmer, stopword, cache_stemming)
    hasil_preprocessing.append(hasil)
    if cek_kelayakan(hasil):
        status_kelayakan.append('layak')
        alasan.append('')
    else:
        status_kelayakan.append('tidak_layak')
        alasan.append('Tidak memenuhi kriteria relevansi, panjang, atau terindikasi spam.')

df['hasil_preprocessing'] = hasil_preprocessing
df['status_kelayakan'] = status_kelayakan
df['alasan_kelayakan'] = alasan
df_layak = df[df['status_kelayakan'] == 'layak'].copy()

print(f'Total data awal: {len(df)}')
print(f'Data layak: {len(df_layak)}')
print(f'Data tidak layak/arsip: {len(df) - len(df_layak)}')
display(df[[kolom_teks, 'hasil_preprocessing', 'status_kelayakan']].head(15))

nama_hasil = 'hasil_preprocessing_lcgc.csv'
df.to_csv(nama_hasil, index=False, encoding='utf-8-sig')
files.download(nama_hasil)
