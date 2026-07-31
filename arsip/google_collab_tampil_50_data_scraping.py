# ================================================================
# GOOGLE COLAB: MENAMPILKAN 50 DATA SCRAPING REPRESENTATIF
# Platform: YouTube, TikTok, dan Instagram
# ================================================================

# Pilih semua file hasil_scraping_*.csv ketika jendela unggah muncul.
from google.colab import files
uploaded = files.upload()

import io
import re

import pandas as pd
from IPython.display import display

JUMLAH_TARGET = 50
SEED = 42  # Sampel selalu sama saat kode dijalankan ulang.


def tentukan_platform(nama_file):
    """Menentukan platform berdasarkan nama file hasil scraping."""
    nama = nama_file.lower()
    if "youtube" in nama:
        return "YouTube"
    if "tiktok" in nama:
        return "TikTok"
    if "instagram" in nama or re.search(r"(^|[_-])ig([_-]|$)", nama):
        return "Instagram"
    return None


def baca_csv(nama_file, isi_file):
    """Membaca CSV dan menyamakan nama kolom penting."""
    try:
        data = pd.read_csv(io.BytesIO(isi_file), encoding="utf-8-sig")
    except UnicodeDecodeError:
        data = pd.read_csv(io.BytesIO(isi_file), encoding="latin-1")

    data.columns = data.columns.str.strip().str.lower()
    kolom_review = next((k for k in data.columns if k in {"review", "text", "komentar", "comment"}), None)
    kolom_tanggal = next((k for k in data.columns if "tanggal" in k or "date" in k or "time" in k), None)
    if kolom_review is None:
        raise ValueError("Kolom komentar tidak ditemukan.")

    hasil = pd.DataFrame({
        "Komentar": data[kolom_review].astype(str).str.replace(r"\s+", " ", regex=True).str.strip(),
        "Tanggal Komentar": data[kolom_tanggal] if kolom_tanggal else "-",
        "File Sumber": nama_file,
    })
    return hasil[hasil["Komentar"].notna() & hasil["Komentar"].ne("")].copy()


def alokasi_seimbang(ketersediaan, target):
    """Membagi target merata, kemudian mengisi kuota yang masih kurang."""
    platform = list(ketersediaan.index)
    target = min(target, int(ketersediaan.sum()))
    kuota = {nama: 0 for nama in platform}
    while sum(kuota.values()) < target:
        berubah = False
        for nama in sorted(platform):
            if sum(kuota.values()) >= target:
                break
            if kuota[nama] < ketersediaan[nama]:
                kuota[nama] += 1
                berubah = True
        if not berubah:
            break
    return kuota


# Hanya menggunakan CSV yang namanya menunjukkan platform scraping.
data_per_platform = []
file_diabaikan = []
for nama_file, isi_file in uploaded.items():
    platform = tentukan_platform(nama_file)
    if platform is None or not nama_file.lower().endswith(".csv"):
        file_diabaikan.append(nama_file)
        continue
    try:
        data = baca_csv(nama_file, isi_file)
        data.insert(0, "Platform", platform)
        data_per_platform.append(data)
    except Exception as error:
        print(f"File '{nama_file}' dilewati: {error}")

if not data_per_platform:
    raise ValueError("Tidak ada CSV YouTube, TikTok, atau Instagram yang berhasil dibaca.")

gabungan = pd.concat(data_per_platform, ignore_index=True)
# Hapus komentar duplikat dalam platform yang sama agar sampel lebih representatif.
gabungan = gabungan.drop_duplicates(subset=["Platform", "Komentar"], keep="first")

ketersediaan = gabungan.groupby("Platform", sort=True).size()
kuota = alokasi_seimbang(ketersediaan, JUMLAH_TARGET)

sampel = []
for platform, jumlah in kuota.items():
    data_platform = gabungan[gabungan["Platform"] == platform]
    sampel.append(data_platform.sample(n=jumlah, random_state=SEED) if jumlah else data_platform.head(0))

hasil_50 = pd.concat(sampel, ignore_index=True)
hasil_50 = hasil_50.sort_values(["Platform", "Tanggal Komentar"], kind="stable").reset_index(drop=True)
hasil_50.index = hasil_50.index + 1
hasil_50.index.name = "No"

print("Jumlah data unik yang tersedia:")
display(ketersediaan.rename("Jumlah Data").to_frame())
print(f"\nKuota sampel (target {JUMLAH_TARGET} data): {kuota}")
print(f"Total data yang ditampilkan: {len(hasil_50)}")
display(hasil_50)

# Unduh hasil agar dapat dipakai pada tahap berikutnya.
nama_output = "sampel_50_data_scraping_representatif.csv"
hasil_50.to_csv(nama_output, encoding="utf-8-sig", index=True)
files.download(nama_output)

if file_diabaikan:
    print("\nFile yang diabaikan:", ", ".join(file_diabaikan))
