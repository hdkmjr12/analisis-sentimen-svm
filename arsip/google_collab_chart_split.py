# =============================================================
# GOOGLE COLAB: Visualisasi Pembagian Data SVM LCGC
# =============================================================
# Upload DUA file sekaligus:
# 1. CSV hasil preprocessing dari website/Colab.
# 2. cgi-bin/text_pipeline.py terbaru.
# =============================================================
import io
import os
import sys
import pandas as pd
import matplotlib.pyplot as plt
from google.colab import files
from sklearn.model_selection import StratifiedGroupKFold


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
from text_pipeline import label_lexicon

df = pd.read_csv(io.BytesIO(uploaded_csv[nama_csv]), encoding='utf-8-sig')
kolom_preprocessing = next((k for k in df.columns if 'preprocessing' in k.lower()), None)
if kolom_preprocessing is None:
    raise ValueError('Kolom hasil_preprocessing tidak ditemukan.')

df = df[df[kolom_preprocessing].notna() & df[kolom_preprocessing].astype(str).str.strip().ne('')].copy()
if 'status_kelayakan' in df.columns:
    df = df[df['status_kelayakan'].fillna('baru') == 'layak'].copy()

kolom_asli = next((k for k in ['teks_review', 'teks', 'review', 'Review', 'Review Asli'] if k in df.columns), kolom_preprocessing)
df['_teks_bersih'] = df[kolom_preprocessing].astype(str)
df['_teks_asli'] = df[kolom_asli].astype(str)
df['_id_urut'] = df['id'] if 'id' in df.columns else range(len(df))
df = df.sort_values(['_teks_bersih', '_teks_asli', '_id_urut']).reset_index(drop=True)

list_teks = df['_teks_bersih'].tolist()
y_label = [label_lexicon(teks) for teks in list_teks]
if min(pd.Series(y_label).value_counts()) < 2:
    raise ValueError('Setiap kelas memerlukan minimal dua data.')
if min(pd.DataFrame({'teks': list_teks, 'label': y_label}).drop_duplicates().groupby('label').size()) < 5:
    raise ValueError('Setiap kelas memerlukan minimal lima kelompok teks unik.')

pembagi = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)
indeks_training, indeks_testing = next(pembagi.split(list_teks, y_label, groups=list_teks))
jumlah = [len(indeks_training), len(indeks_testing)]
persentase = [nilai / len(list_teks) * 100 for nilai in jumlah]

fig, ax = plt.subplots(figsize=(8, 4))
bars = ax.barh(['Data Latih', 'Data Uji'], jumlah, color=['#3498db', '#f39c12'])
for bar, nilai, persen in zip(bars, jumlah, persentase):
    ax.text(bar.get_width() + len(list_teks) * 0.015, bar.get_y() + bar.get_height() / 2,
            f'{nilai} ulasan ({persen:.1f}%)', va='center', fontweight='bold')
ax.set_xlabel('Jumlah Ulasan')
ax.set_title('Pembagian Data Latih dan Data Uji 80:20 (Stratified Group)')
ax.set_xlim(0, max(jumlah) * 1.25)
plt.tight_layout()
plt.show()

print(f'Total data: {len(list_teks)} | Data latih: {jumlah[0]} | Data uji: {jumlah[1]}')
