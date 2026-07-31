import json
import sys

from db_utils import buat_koneksi, dapatkan_dataset_aktif


sys.stdout.reconfigure(encoding='utf-8')
print("Content-Type: application/json\n")


def kirim_json(data):
    print(json.dumps(data))
    sys.exit()


try:
    koneksi = buat_koneksi()
    cursor = koneksi.cursor(dictionary=True)
    id_dataset = dapatkan_dataset_aktif(cursor)
    if id_dataset is None:
        kirim_json({"status": "error", "message": "Tidak ada dataset aktif. Impor data terlebih dahulu."})

    cursor.execute(
        """
        SELECT COUNT(*) AS total_preprocessing,
               SUM(CASE WHEN sentimen IN ('POSITIF', 'NEGATIF', 'NETRAL') THEN 1 ELSE 0 END) AS total_analisis
        FROM data_review
        WHERE id_dataset = %s
          AND status_kelayakan = 'layak'
          AND hasil_preprocessing IS NOT NULL
          AND hasil_preprocessing <> ''
        """,
        (id_dataset,)
    )
    status_data = cursor.fetchone()
    total_preprocessing = int(status_data['total_preprocessing'] or 0)
    total_analisis = int(status_data['total_analisis'] or 0)

    if total_preprocessing == 0:
        kirim_json({"status": "error", "message": "Tidak ada data layak. Lakukan preprocessing terlebih dahulu."})
    if total_analisis != total_preprocessing:
        kirim_json({"status": "pending", "message": "Analisis sentimen belum dijalankan atau belum selesai. Jalankan Analisis Sentimen terlebih dahulu."})

    cursor.execute(
        """
        SELECT e.*
        FROM hasil_evaluasi_svm e
        JOIN proses_analisis_svm a ON a.id_analisis = e.id_analisis
        WHERE a.id_dataset = %s
        ORDER BY e.id_evaluasi DESC
        LIMIT 1
        """,
        (id_dataset,)
    )
    evaluasi = cursor.fetchone()
    cursor.close()
    koneksi.close()

    if evaluasi is None:
        kirim_json({"status": "pending", "message": "Hasil evaluasi belum tersedia. Jalankan Analisis Sentimen terlebih dahulu."})

    kirim_json({
        "status": "success",
        "akurasi": float(evaluasi['akurasi']),
        "total_data": int(evaluasi['total_data']),
        "total_training": int(evaluasi['total_training']),
        "total_testing": int(evaluasi['total_testing']),
        "cm": {
            "pos_pos": int(evaluasi['pos_pos']), "pos_neg": int(evaluasi['pos_neg']), "pos_net": int(evaluasi['pos_net']),
            "neg_pos": int(evaluasi['neg_pos']), "neg_neg": int(evaluasi['neg_neg']), "neg_net": int(evaluasi['neg_net']),
            "net_pos": int(evaluasi['net_pos']), "net_neg": int(evaluasi['net_neg']), "net_net": int(evaluasi['net_net'])
        }
    })

except Exception as error:
    kirim_json({"status": "error", "message": str(error)})
