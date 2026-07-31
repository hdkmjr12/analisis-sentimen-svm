# =============================================================
# GOOGLE COLAB: Pelabelan Lexicon Review LCGC (selaras website)
# =============================================================
# Upload DUA file sekaligus:
# 1. hasil_preprocessing_lcgc.csv.
# 2. cgi-bin/text_pipeline.py dari proyek website terbaru.
# =============================================================
import io
import os
import sys
import pandas as pd
from google.colab import files
from IPython.display import display


print('LANGKAH 1/2 - Upload text_pipeline.py terbaru:')
uploaded_pipeline = files.upload()
nama_pipeline = next((n for n in uploaded_pipeline if 'text_pipeline' in n.lower() and n.lower().endswith('.py')), None)
if not nama_pipeline:
    raise ValueError('File text_pipeline.py belum dipilih.')
print('LANGKAH 2/2 - Upload satu CSV hasil preprocessing:')
uploaded_csv = files.upload()
nama_csv = next((n for n in uploaded_csv if n.lower().endswith('.csv')), None)
if not nama_csv:
    raise ValueError('File CSV belum dipilih.')

with open('text_pipeline.py', 'wb') as file_pipeline:
    file_pipeline.write(uploaded_pipeline[nama_pipeline])
sys.path.insert(0, os.getcwd())
from text_pipeline import label_lexicon, hitung_skor_lexicon

df = pd.read_csv(io.BytesIO(uploaded_csv[nama_csv]), encoding='utf-8-sig')
kolom_preprocessing = next((k for k in df.columns if 'preprocessing' in k.lower()), None)
if kolom_preprocessing is None:
    raise ValueError('Kolom hasil_preprocessing tidak ditemukan.')

if 'status_kelayakan' in df.columns:
    df_layak = df[df['status_kelayakan'].fillna('baru') == 'layak'].copy()
else:
    df_layak = df[df[kolom_preprocessing].notna() & df[kolom_preprocessing].astype(str).str.strip().ne('')].copy()

df_layak['label_lexicon'] = df_layak[kolom_preprocessing].astype(str).apply(label_lexicon)
df_layak['skor_positif'] = df_layak[kolom_preprocessing].astype(str).apply(lambda teks: hitung_skor_lexicon(teks)['positif'])
df_layak['skor_negatif'] = df_layak[kolom_preprocessing].astype(str).apply(lambda teks: hitung_skor_lexicon(teks)['negatif'])

print('Distribusi label lexicon:')
display(df_layak['label_lexicon'].value_counts().rename_axis('sentimen').reset_index(name='jumlah'))
display(df_layak[[kolom_preprocessing, 'skor_positif', 'skor_negatif', 'label_lexicon']].head(15))

nama_hasil = 'hasil_label_lexicon_lcgc.csv'
df_layak.to_csv(nama_hasil, index=False, encoding='utf-8-sig')
files.download(nama_hasil)
