# =============================================================
# GOOGLE COLAB: Demonstrasi TF-IDF Review LCGC
# =============================================================
# File ini untuk contoh pembobotan TF-IDF pada Bab IV.
# Ini BUKAN skrip evaluasi SVM; evaluasi memakai google_collab_confusion_matrix.py.
# Upload CSV hasil preprocessing dari website atau Colab preprocessing.
# =============================================================
import io
import pandas as pd
from google.colab import files
from sklearn.feature_extraction.text import TfidfVectorizer
from IPython.display import display


print('Upload CSV yang memiliki kolom hasil_preprocessing:')
uploaded = files.upload()
if not uploaded:
    raise ValueError('Tidak ada file yang diupload.')
nama_csv = next(iter(uploaded))
df = pd.read_csv(io.BytesIO(uploaded[nama_csv]), encoding='utf-8-sig')
kolom_preprocessing = next((k for k in df.columns if 'preprocessing' in k.lower()), None)
if kolom_preprocessing is None:
    raise ValueError('Kolom hasil_preprocessing tidak ditemukan.')

df_valid = df[df[kolom_preprocessing].notna() & df[kolom_preprocessing].astype(str).str.strip().ne('')].copy()
if 'status_kelayakan' in df_valid.columns:
    df_valid = df_valid[df_valid['status_kelayakan'].fillna('baru') == 'layak'].copy()
teks_valid = df_valid[kolom_preprocessing].astype(str).tolist()
if len(teks_valid) < 2:
    raise ValueError('Minimal diperlukan dua data layak untuk demonstrasi TF-IDF.')

# Parameter identik dengan website. Pada file ini fit dilakukan pada seluruh
# data layak hanya untuk menampilkan contoh tabel; bukan untuk evaluasi SVM.
vectorizer = TfidfVectorizer(
    ngram_range=(1, 2),
    min_df=2,
    max_df=0.95,
    sublinear_tf=True
)
X_tfidf = vectorizer.fit_transform(teks_valid)
fitur = vectorizer.get_feature_names_out()

print(f'Jumlah dokumen contoh: {len(teks_valid)}')
print(f'Jumlah fitur unigram dan bigram: {len(fitur)}')
print(f'Ukuran matriks TF-IDF: {X_tfidf.shape}')
print('Parameter: ngram_range=(1,2), min_df=2, max_df=0.95, sublinear_tf=True')

jumlah_sampel = min(15, len(df_valid))
contoh = df_valid.head(jumlah_sampel).copy()
matriks_contoh = pd.DataFrame(
    X_tfidf[:jumlah_sampel].toarray(),
    columns=fitur,
    index=[f'D{i + 1}' for i in range(jumlah_sampel)]
)

display(contoh[[kolom_preprocessing]].reset_index(drop=True))
display(matriks_contoh.iloc[:, :min(20, len(fitur))].round(4))

rata_rata_bobot = pd.Series(X_tfidf.mean(axis=0).A1, index=fitur).sort_values(ascending=False).head(20)
display(rata_rata_bobot.rename_axis('fitur').reset_index(name='rata_rata_bobot').round(4))
