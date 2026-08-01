import sys
import json
import os
import tempfile

from model_utils import batalkan_hasil_analisis
from text_pipeline import buat_preprocessor, preprocess_teks, cek_kelayakan
from db_utils import buat_koneksi, dapatkan_dataset_aktif


sys.stdout.reconfigure(encoding='utf-8')


def kirim_json(data):
    print("Content-Type: application/json\n")
    print(json.dumps(data))
    sys.exit()


try:
    stemmer, daftar_stopword = buat_preprocessor()
    koneksi = buat_koneksi()
    cursor = koneksi.cursor(dictionary=True)

    id_dataset = dapatkan_dataset_aktif(cursor)
    if id_dataset is None:
        kirim_json({"status": "error", "message": "Tidak ada dataset aktif. Impor data terlebih dahulu."})

    cursor.execute(
        "SELECT id, teks_review, sumber FROM data_review WHERE id_dataset = %s ORDER BY id ASC",
        (id_dataset,)
    )
    baris_data = cursor.fetchall()
    if not baris_data:
        kirim_json({"status": "error", "message": "Dataset aktif kosong. Impor data terlebih dahulu."})

    total_sebelum = len(baris_data)
    platform_sebelum = {}
    sumber_per_id = {}
    for baris in baris_data:
        sumber = (baris.get('sumber') or '-').strip()
        sumber_per_id[baris['id']] = sumber
        platform_sebelum[sumber] = platform_sebelum.get(sumber, 0) + 1

    lokasi_project = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    lokasi_cache_bawaan = os.path.join(lokasi_project, 'stemming_cache.json')
    lokasi_cache_stemming = os.path.join(tempfile.gettempdir(), 'stemming_cache.json')
    cache_stemming = {}
    lokasi_cache_sumber = lokasi_cache_stemming if os.path.exists(lokasi_cache_stemming) else lokasi_cache_bawaan
    if os.path.exists(lokasi_cache_sumber):
        try:
            with open(lokasi_cache_sumber, 'r', encoding='utf-8') as file_cache:
                cache_stemming = json.load(file_cache)
        except (OSError, ValueError, TypeError):
            cache_stemming = {}

    cache_stemming.update({"berlaku": "berlaku", "favorit": "favorit"})
    jumlah_cache_awal = len(cache_stemming)

    data_terproses = []
    list_data_update = []
    jumlah_tidak_layak = 0
    platform_sesudah = {}

    for baris in baris_data:
        id_review = baris['id']
        teks_asli = baris['teks_review']
        if isinstance(teks_asli, (bytes, bytearray)):
            teks_asli = teks_asli.decode('utf-8', 'ignore')

        teks_akhir = preprocess_teks(teks_asli, stemmer, daftar_stopword, cache_stemming)
        if cek_kelayakan(teks_akhir):
            status_kelayakan = 'layak'
            alasan_kelayakan = None
            data_terproses.append({"id": id_review, "teks": teks_asli, "hasil": teks_akhir})
            sumber = sumber_per_id[id_review]
            platform_sesudah[sumber] = platform_sesudah.get(sumber, 0) + 1
        else:
            # Data tidak dihapus; tetap disimpan untuk audit dan pemulihan.
            status_kelayakan = 'tidak_layak'
            alasan_kelayakan = 'Tidak memenuhi kriteria relevansi, panjang, atau terindikasi spam.'
            jumlah_tidak_layak += 1

        list_data_update.append((teks_akhir, status_kelayakan, alasan_kelayakan, id_review))

    total_sesudah = len(data_terproses)

    cursor.execute(
        """
        INSERT INTO proses_preprocessing (
            id_dataset, total_sebelum, total_sesudah,
            per_platform_sebelum, per_platform_sesudah
        ) VALUES (%s, %s, %s, %s, %s)
        """,
        (
            id_dataset, total_sebelum, total_sesudah,
            json.dumps(platform_sebelum), json.dumps(platform_sesudah)
        )
    )
    id_preprocessing = cursor.lastrowid

    # Preprocessing baru membatalkan model dan evaluasi lama pada dataset ini.
    batalkan_hasil_analisis(cursor, id_dataset, reset_sentimen=False)
    cursor.executemany(
        """
        UPDATE data_review
        SET hasil_preprocessing = %s,
            sentimen = NULL,
            id_preprocessing = %s,
            id_analisis = NULL,
            status_kelayakan = %s,
            alasan_kelayakan = %s
        WHERE id = %s AND id_dataset = %s
        """,
        [
            (teks, id_preprocessing, status, alasan, id_review, id_dataset)
            for teks, status, alasan, id_review in list_data_update
        ]
    )

    if len(cache_stemming) > jumlah_cache_awal:
        lokasi_cache_sementara = lokasi_cache_stemming + '.tmp'
        with open(lokasi_cache_sementara, 'w', encoding='utf-8') as file_cache:
            json.dump(cache_stemming, file_cache, ensure_ascii=False, sort_keys=True)
        os.replace(lokasi_cache_sementara, lokasi_cache_stemming)

    koneksi.commit()
    cursor.close()
    koneksi.close()

    if jumlah_tidak_layak:
        pesan_akhir = (
            f"Preprocessing selesai. {jumlah_tidak_layak} ulasan tidak layak atau spam "
            "disaring dan disimpan aman sebagai arsip."
        )
    else:
        pesan_akhir = "Preprocessing selesai. Seluruh ulasan lolos seleksi kualitas."

    kirim_json({
        "status": "success",
        "message": pesan_akhir,
        "data": data_terproses,
        "statistik_preprocessing": {
            "total_sebelum": total_sebelum,
            "total_sesudah": total_sesudah,
            "per_platform_sebelum": platform_sebelum,
            "per_platform_sesudah": platform_sesudah,
            "diarsipkan_tidak_layak_spam": jumlah_tidak_layak,
            "jumlah_kata_cache_stemming": len(cache_stemming)
        }
    })

except Exception as e:
    kirim_json({"status": "error", "message": f"Error Preprocessing: {str(e)}"})
