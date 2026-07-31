import sys
import json
import datetime

from db_utils import buat_koneksi, dapatkan_dataset_aktif


sys.stdout.reconfigure(encoding='utf-8')


def kirim_json(data):
    print("Content-Type: application/json")
    print()
    print(json.dumps(data))
    sys.exit()


try:
    koneksi = buat_koneksi()
    cursor = koneksi.cursor(dictionary=True)
    id_dataset = dapatkan_dataset_aktif(cursor)

    data_review = []
    statistik_data = {
        "total_data_db": 0,
        "total_sudah_preprocessing": 0,
        "platform_db": {},
        "platform_preprocessed": {},
        "log_preprocessing": None
    }

    if id_dataset is not None:
        # Data tidak layak tetap ada di database, tetapi tidak ditampilkan
        # pada alur utama aplikasi dan tidak dikirim ke SVM.
        cursor.execute(
            """
            SELECT id, teks_review, sumber, tanggal_komentar, tanggal,
                   hasil_preprocessing, sentimen
            FROM data_review
            WHERE id_dataset = %s AND status_kelayakan <> 'tidak_layak'
            ORDER BY id ASC
            """,
            (id_dataset,)
        )
        baris_tampil = cursor.fetchall()
        for baris in baris_tampil:
            teks = baris["teks_review"]
            hasil_pre = baris["hasil_preprocessing"]
            if isinstance(teks, (bytes, bytearray)):
                teks = teks.decode('utf-8', 'ignore')
            if isinstance(hasil_pre, (bytes, bytearray)):
                hasil_pre = hasil_pre.decode('utf-8', 'ignore')

            waktu = baris["tanggal"]
            tgl_str = waktu.strftime("%d/%m/%Y") if isinstance(waktu, datetime.datetime) else (str(waktu) if waktu else "Baru")
            data_review.append({
                "id": baris["id"],
                "teks": teks,
                "sumber": baris["sumber"] or "-",
                "tanggal_komentar": baris["tanggal_komentar"] or "-",
                "tanggal": tgl_str,
                "hasil": hasil_pre or "",
                "sentimen": baris["sentimen"] or ""
            })

        cursor.execute(
            """
            SELECT
                COUNT(*) AS total_data_db,
                SUM(CASE WHEN status_kelayakan = 'layak'
                          AND hasil_preprocessing IS NOT NULL
                          AND hasil_preprocessing <> '' THEN 1 ELSE 0 END) AS total_sudah_preprocessing
            FROM data_review
            WHERE id_dataset = %s
            """,
            (id_dataset,)
        )
        ringkasan = cursor.fetchone()
        total_raw = int(ringkasan["total_data_db"] or 0)
        total_layak = int(ringkasan["total_sudah_preprocessing"] or 0)

        cursor.execute(
            """
            SELECT sumber,
                   COUNT(*) AS jumlah_db,
                   SUM(CASE WHEN status_kelayakan = 'layak'
                            AND hasil_preprocessing IS NOT NULL
                            AND hasil_preprocessing <> '' THEN 1 ELSE 0 END) AS jumlah_preprocessed
            FROM data_review
            WHERE id_dataset = %s
            GROUP BY sumber
            """,
            (id_dataset,)
        )
        platform_db = {}
        platform_preprocessed = {}
        for baris in cursor.fetchall():
            sumber = (baris["sumber"] or "-").strip()
            platform_db[sumber] = int(baris["jumlah_db"] or 0)
            platform_preprocessed[sumber] = int(baris["jumlah_preprocessed"] or 0)

        statistik_data.update({
            "total_data_db": total_raw,
            "total_sudah_preprocessing": total_layak,
            "platform_db": platform_db,
            "platform_preprocessed": platform_preprocessed
        })

        # Log hanya dipakai bila seluruh data pada dataset aktif berasal dari
        # proses preprocessing terakhir. Impor/hapus data akan memakai statistik real-time.
        cursor.execute(
            "SELECT * FROM proses_preprocessing WHERE id_dataset = %s ORDER BY id_preprocessing DESC LIMIT 1",
            (id_dataset,)
        )
        log_row = cursor.fetchone()
        if log_row and total_raw == int(log_row["total_sebelum"] or 0):
            cursor.execute(
                "SELECT COUNT(*) AS jumlah FROM data_review WHERE id_dataset = %s AND id_preprocessing = %s",
                (id_dataset, log_row["id_preprocessing"])
            )
            jumlah_berasal_dari_log = int(cursor.fetchone()["jumlah"] or 0)
            if jumlah_berasal_dari_log == total_raw:
                statistik_data["log_preprocessing"] = {
                    "total_sebelum": int(log_row["total_sebelum"] or 0),
                    "total_sesudah": int(log_row["total_sesudah"] or 0),
                    "per_platform_sebelum": json.loads(log_row["per_platform_sebelum"]) if log_row["per_platform_sebelum"] else {},
                    "per_platform_sesudah": json.loads(log_row["per_platform_sesudah"]) if log_row["per_platform_sesudah"] else {}
                }

    cursor.close()
    koneksi.close()
    kirim_json({"status": "success", "data": data_review, "statistik_data": statistik_data})

except Exception as e:
    kirim_json({"status": "error", "message": f"Error Sistem Python: {str(e)}"})
