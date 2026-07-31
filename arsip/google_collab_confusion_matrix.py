# =============================================================
# GOOGLE COLAB: Confusion Matrix SVM Review LCGC (selaras website)
# =============================================================
# Cell awal (jalankan sekali pada Colab baru):
# !pip install Sastrawi pandas scikit-learn matplotlib
#
# Upload DUA file sekaligus:
# 1. CSV hasil preprocessing dari website atau Colab.
# 2. cgi-bin/text_pipeline.py dari proyek website terbaru.
# =============================================================
import io
import os
import sys
import pandas as pd
import matplotlib.pyplot as plt
from google.colab import files
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import SVC
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay, classification_report
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
from text_pipeline import label_lexicon

df = pd.read_csv(io.BytesIO(uploaded_csv[nama_csv]), encoding='utf-8-sig')
kolom_preprocessing = next((k for k in df.columns if 'preprocessing' in k.lower()), None)
if kolom_preprocessing is None:
    raise ValueError('Kolom hasil_preprocessing tidak ditemukan.')

df = df[df[kolom_preprocessing].notna() & df[kolom_preprocessing].astype(str).str.strip().ne('')].copy()
if 'status_kelayakan' in df.columns:
    df = df[df['status_kelayakan'].fillna('baru') == 'layak'].copy()
if df.empty:
    raise ValueError('Tidak ada data layak untuk dianalisis.')

# Urutan sama dengan proses_svm.py agar pembagian grouped split konsisten.
kolom_asli = next((k for k in ['teks_review', 'teks', 'review', 'Review', 'Review Asli'] if k in df.columns), kolom_preprocessing)
df['_teks_bersih'] = df[kolom_preprocessing].astype(str)
df['_teks_asli'] = df[kolom_asli].astype(str)
df['_id_urut'] = df['id'] if 'id' in df.columns else range(len(df))
df = df.sort_values(['_teks_bersih', '_teks_asli', '_id_urut']).reset_index(drop=True)

list_teks = df['_teks_bersih'].tolist()
y_label = [label_lexicon(teks) for teks in list_teks]
jumlah_per_kelas = pd.Series(y_label).value_counts()
if len(jumlah_per_kelas) < 2 or jumlah_per_kelas.min() < 2:
    raise ValueError('SVM memerlukan minimal dua kelas dan minimal dua data pada setiap kelas.')
jumlah_kelompok = pd.DataFrame({'teks': list_teks, 'label': y_label}).drop_duplicates().groupby('label').size()
if jumlah_kelompok.min() < 5:
    raise ValueError('Grouped split memerlukan minimal lima kelompok teks unik pada setiap kelas.')

pembagi = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)
indeks_training, indeks_testing = next(pembagi.split(list_teks, y_label, groups=list_teks))
X_train_teks = [list_teks[i] for i in indeks_training]
X_test_teks = [list_teks[i] for i in indeks_testing]
y_train = [y_label[i] for i in indeks_training]
y_test = [y_label[i] for i in indeks_testing]

# TF-IDF hanya di-fit pada data latih, sama seperti website.
vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_df=0.95, sublinear_tf=True)
X_train = vectorizer.fit_transform(X_train_teks)
X_test = vectorizer.transform(X_test_teks)
model = SVC(kernel='linear', class_weight='balanced', C=10, random_state=42)
model.fit(X_train, y_train)
y_pred = model.predict(X_test)

urutan_label = ['POSITIF', 'NEGATIF', 'NETRAL']
cm = confusion_matrix(y_test, y_pred, labels=urutan_label)
akurasi = (cm.trace() / cm.sum()) * 100
print(f'Total data: {len(list_teks)} | Training: {len(X_train_teks)} | Testing: {len(X_test_teks)}')
print(f'Akurasi: {akurasi:.2f}%')

fig, ax = plt.subplots(figsize=(7, 5))
ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=urutan_label).plot(cmap='Blues', ax=ax, values_format='d')
ax.set_title('Confusion Matrix Model SVM (Grouped Split 80:20)')
plt.tight_layout()
plt.show()

laporan = pd.DataFrame(classification_report(y_test, y_pred, labels=urutan_label, output_dict=True)).transpose()
display(laporan.round(3))
