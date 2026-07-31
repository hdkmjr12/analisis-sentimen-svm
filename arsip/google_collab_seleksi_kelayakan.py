# =============================================================
# GOOGLE COLAB: Seleksi Kelayakan Data Review LCGC
# =============================================================
# Cell awal (jalankan sekali pada Colab baru):
# !pip install Sastrawi pandas
#
# Upload seluruh CSV mentah hasil scraping (16 file pada folder data scrapp)
# dan cgi-bin/text_pipeline.py terbaru dari proyek website.
# =============================================================
import io
import os
import sys
import pandas as pd
from google.colab import files
from IPython.display import display


def baca_csv(data_file):
    """Membaca CSV scraping dengan encoding yang umum dipakai."""
    for encoding in ('utf-8-sig', 'utf-8', 'latin1'):
        try:
            return pd.read_csv(io.BytesIO(data_file), encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError('CSV tidak dapat dibaca dengan encoding yang didukung.')


def tentukan_platform(nama_file, dataframe):
    """Mengikuti logika impor website: sumber dapat berasal dari CSV atau nama file."""
    kolom_sumber = next((k for k in dataframe.columns if k.lower() in ('sumber', 'platform')), None)
    nama_lower = nama_file.lower()
    if kolom_sumber:
        return dataframe[kolom_sumber].fillna('').astype(str).str.strip().replace('', pd.NA)
    if 'youtube' in nama_lower:
        return pd.Series('Youtube', index=dataframe.index)
    if 'tiktok' in nama_lower:
        return pd.Series('Tiktok', index=dataframe.index)
    if 'instagram' in nama_lower:
        return pd.Series('Instagram', index=dataframe.index)
    return pd.Series('-', index=dataframe.index)


def alasan_tidak_layak(teks_bersih, pipeline):
    """Menjelaskan hasil cek_kelayakan tanpa mengubah aturan aslinya."""
    kata_kata = teks_bersih.split()
    token = set(kata_kata)
    if not kata_kata:
        return 'Hasil preprocessing kosong.'
    if len(kata_kata) == 1 and kata_kata[0] not in pipeline.KATA_SENTIMEN_PENDEK:
        return 'Hanya satu kata dan bukan kata sentimen pendek yang jelas.'
    if len(kata_kata) > 1 and bool(token & pipeline.KATA_SPAM_REQUEST):
        return 'Terindikasi permintaan konten, promosi, atau spam.'
    if len(kata_kata) > 1:
        ada_konteks = bool(token & pipeline.KATA_KUNCI_MOBIL) or bool(token & pipeline.KATA_SENTIMEN_PENDEK)
        if not ada_konteks:
            return 'Tidak memuat konteks kendaraan atau kata sentimen.'
    return 'Tidak memenuhi kriteria kelayakan.'


print('LANGKAH 1/2 - Upload file text_pipeline.py terbaru saja:')
uploaded_pipeline = files.upload()
nama_pipeline = next((n for n in uploaded_pipeline if 'text_pipeline' in n.lower() and n.lower().endswith('.py')), None)
if not nama_pipeline:
    raise ValueError('File text_pipeline.py belum dipilih. Unggah file dari folder cgi-bin.')

print('LANGKAH 2/2 - Upload seluruh file CSV mentah dari folder data scrapp:')
uploaded_csv = files.upload()
nama_csv = [n for n in uploaded_csv if n.lower().endswith('.csv')]
if not nama_csv:
    raise ValueError('Tidak ada CSV yang dipilih.')

with open('text_pipeline.py', 'wb') as file_pipeline:
    file_pipeline.write(uploaded_pipeline[nama_pipeline])
sys.path.insert(0, os.getcwd())
import text_pipeline as pipeline

data_per_file = []
for nama_file in nama_csv:
    df_file = baca_csv(uploaded_csv[nama_file])
    kolom_teks = next((k for k in df_file.columns if k.lower() in ('teks_review', 'review', 'komentar', 'comment', 'text')), None)
    if kolom_teks is None:
        print(f'File dilewati karena kolom teks tidak ditemukan: {nama_file}')
        continue

    hasil_file = pd.DataFrame({
        'teks_review': df_file[kolom_teks].fillna('').astype(str),
        'sumber': tentukan_platform(nama_file, df_file),
        'file_sumber': nama_file
    })
    data_per_file.append(hasil_file)

if not data_per_file:
    raise ValueError('Tidak ada CSV yang memiliki kolom review/teks_review.')

df = pd.concat(data_per_file, ignore_index=True)
stemmer, stopword = pipeline.buat_preprocessor()
cache_stemming = {'berlaku': 'berlaku', 'favorit': 'favorit'}

hasil_preprocessing = []
status_kelayakan = []
alasan_kelayakan = []
for teks in df['teks_review']:
    hasil = pipeline.preprocess_teks(teks, stemmer, stopword, cache_stemming)
    hasil_preprocessing.append(hasil)
    if pipeline.cek_kelayakan(hasil):
        status_kelayakan.append('layak')
        alasan_kelayakan.append('')
    else:
        status_kelayakan.append('tidak_layak')
        alasan_kelayakan.append(alasan_tidak_layak(hasil, pipeline))

df['hasil_preprocessing'] = hasil_preprocessing
df['status_kelayakan'] = status_kelayakan
df['alasan_kelayakan'] = alasan_kelayakan

df_layak = df[df['status_kelayakan'] == 'layak'].copy()
df_tidak_layak = df[df['status_kelayakan'] == 'tidak_layak'].copy()

rekap_total = pd.DataFrame([
    {'Keterangan': 'Ulasan mentah', 'Jumlah': len(df)},
    {'Keterangan': 'Data layak', 'Jumlah': len(df_layak)},
    {'Keterangan': 'Data tidak layak/arsip', 'Jumlah': len(df_tidak_layak)}
])
rekap_platform = (
    df.groupby(['sumber', 'status_kelayakan']).size()
      .unstack(fill_value=0)
      .reindex(columns=['layak', 'tidak_layak'], fill_value=0)
      .reset_index()
)
rekap_platform['total'] = rekap_platform['layak'] + rekap_platform['tidak_layak']

print('REKAP SELEKSI KELAYAKAN DATA')
display(rekap_total)
print('REKAP PER PLATFORM')
display(rekap_platform)

# Verifikasi terhadap angka penelitian. Pesan akan berbeda bila file input
# bukan 16 CSV mentah penelitian atau text_pipeline.py yang diupload berbeda.
target = {'total': 5122, 'layak': 3096, 'tidak_layak': 2026,
          'Youtube': 1730, 'Tiktok': 1164, 'Instagram': 202}
layak_platform = dict(zip(rekap_platform['sumber'], rekap_platform['layak']))
sesuai_target = (
    len(df) == target['total'] and len(df_layak) == target['layak'] and
    len(df_tidak_layak) == target['tidak_layak'] and
    all(layak_platform.get(platform, 0) == jumlah for platform, jumlah in target.items()
        if platform in ('Youtube', 'Tiktok', 'Instagram'))
)
if sesuai_target:
    print('VERIFIKASI BERHASIL: hasil sama dengan rekap penelitian (5.122 -> 3.096).')
else:
    print('Catatan: hasil dihitung dari file dan text_pipeline.py yang diupload; berbeda dari rekap penelitian bila input atau aturan berbeda.')

print('CONTOH DATA TIDAK LAYAK (TETAP DIARSIPKAN)')
display(df_tidak_layak[['teks_review', 'hasil_preprocessing', 'alasan_kelayakan', 'sumber']].head(15))

df.to_csv('hasil_seleksi_kelayakan_lcgc.csv', index=False, encoding='utf-8-sig')
df_layak.to_csv('data_layak_lcgc.csv', index=False, encoding='utf-8-sig')
df_tidak_layak.to_csv('arsip_data_tidak_layak_lcgc.csv', index=False, encoding='utf-8-sig')
files.download('hasil_seleksi_kelayakan_lcgc.csv')
