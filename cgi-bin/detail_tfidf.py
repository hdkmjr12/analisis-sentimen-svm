import json
import os
import sys
from collections import Counter
from urllib.parse import parse_qs

from db_utils import buat_koneksi, dapatkan_dataset_aktif
from model_utils import muat_model


sys.stdout.reconfigure(encoding="utf-8")


def kirim_json(data):
    print("Content-Type: application/json")
    print("Cache-Control: no-store")
    print()
    print(json.dumps(data, ensure_ascii=False))
    sys.exit()


def baca_payload_json():
    parameter_query = parse_qs(os.environ.get("QUERY_STRING", ""))
    if parameter_query.get("id"):
        return {"id": parameter_query["id"][0]}

    try:
        panjang = int(os.environ.get("CONTENT_LENGTH", "0") or 0)
    except ValueError:
        panjang = 0

    isi = sys.stdin.buffer.read(panjang).decode("utf-8", "ignore") if panjang > 0 else ""
    return json.loads(isi) if isi else {}


try:
    payload = baca_payload_json()
    try:
        id_review = int(payload.get("id"))
    except (TypeError, ValueError):
        kirim_json({"status": "error", "message": "ID review tidak valid."})

    koneksi = buat_koneksi()
    cursor = koneksi.cursor(dictionary=True)
    id_dataset = dapatkan_dataset_aktif(cursor)
    if id_dataset is None:
        cursor.close()
        koneksi.close()
        kirim_json({"status": "error", "message": "Tidak ada dataset aktif."})

    cursor.execute(
        """
        SELECT id, hasil_preprocessing, id_analisis
        FROM data_review
        WHERE id = %s
          AND id_dataset = %s
          AND status_kelayakan = 'layak'
          AND hasil_preprocessing IS NOT NULL
          AND hasil_preprocessing <> ''
        LIMIT 1
        """,
        (id_review, id_dataset),
    )
    review = cursor.fetchone()
    cursor.close()
    koneksi.close()

    if review is None:
        kirim_json({"status": "error", "message": "Review layak tidak ditemukan pada dataset aktif."})

    artifact_model = muat_model()
    if not artifact_model:
        kirim_json({"status": "error", "message": "Model belum tersedia. Jalankan Analisis Sentimen terlebih dahulu."})

    vectorizer = artifact_model.get("vectorizer")
    metadata = artifact_model.get("metadata", {})
    if vectorizer is None:
        kirim_json({"status": "error", "message": "Vectorizer tidak ditemukan di dalam model."})

    if int(metadata.get("id_dataset", -1)) != int(id_dataset):
        kirim_json({"status": "error", "message": "Model tidak sesuai dengan dataset aktif. Jalankan Analisis Sentimen kembali."})

    id_analisis_model = metadata.get("id_analisis")
    if review.get("id_analisis") and id_analisis_model:
        if int(review["id_analisis"]) != int(id_analisis_model):
            kirim_json({"status": "error", "message": "Review tidak berasal dari proses analisis model yang aktif."})

    teks = review["hasil_preprocessing"]
    if isinstance(teks, (bytes, bytearray)):
        teks = teks.decode("utf-8", "ignore")
    teks = str(teks)

    matriks = vectorizer.transform([teks]).tocsr()
    nama_fitur = vectorizer.get_feature_names_out()
    bobot_per_indeks = dict(zip(matriks.indices.tolist(), matriks.data.tolist()))
    indeks_per_term = {str(nama_fitur[indeks]): int(indeks) for indeks in matriks.indices.tolist()}

    analyzer = vectorizer.build_analyzer()
    seluruh_term = analyzer(teks)
    frekuensi = Counter(seluruh_term)

    # Pertahankan urutan term dari dokumen dan hilangkan duplikat. Hanya term
    # yang benar-benar terdapat pada vocabulary model utama yang ditampilkan.
    urutan_term = []
    sudah_ditambahkan = set()
    for term in seluruh_term:
        if term in indeks_per_term and term not in sudah_ditambahkan:
            urutan_term.append(term)
            sudah_ditambahkan.add(term)

    hasil = []
    for term in urutan_term:
        indeks = indeks_per_term[term]
        hasil.append({
            "term": term,
            "jenis": "BIGRAM" if " " in term else "UNIGRAM",
            "tf": int(frekuensi[term]),
            "tfidf": float(bobot_per_indeks[indeks]),
        })

    kirim_json({
        "status": "success",
        "id": id_review,
        "teks": teks,
        "normalisasi": "L2",
        "total_training": int(metadata.get("total_training", 0)),
        "data": hasil,
    })

except Exception as error:
    kirim_json({"status": "error", "message": f"Gagal menghitung detail TF-IDF: {str(error)}"})
