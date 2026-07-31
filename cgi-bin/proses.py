
import sys
import json
import mysql.connector
from model_utils import batalkan_hasil_analisis
from db_utils import DB_CONFIG, dapatkan_dataset_aktif

sys.stdin.reconfigure(encoding='utf-8')
sys.stdout.reconfigure(encoding='utf-8')

print("Content-Type: application/json")
print()

try:
    input_data = sys.stdin.read()
    
    if not input_data:
        print(json.dumps({"status": "error", "message": "Tidak ada data yang dikirim."}))
        sys.exit()

    data_json = json.loads(input_data)
    list_ulasan = data_json.get("data", [])
    id_admin = data_json.get("id_admin")

    if not list_ulasan:
        print(json.dumps({"status": "error", "message": "Tabel CSV kosong."}))
        sys.exit()

    koneksi = mysql.connector.connect(**DB_CONFIG)
    cursor = koneksi.cursor(dictionary=True)

    values_untuk_disimpan = []
    jumlah_kosong = 0
    
    for item in list_ulasan:
        teks_asli = item.get("teks", "")
        sumber = item.get("sumber", "-")
        tgl_komen = item.get("tanggal_komentar", "-")
        
        if not teks_asli.strip():
            jumlah_kosong += 1
            continue
        values_untuk_disimpan.append((teks_asli, sumber, tgl_komen))

    jumlah_akhir_disimpan = len(values_untuk_disimpan)

    if jumlah_akhir_disimpan > 0:
        try:
            id_admin = int(id_admin)
        except (TypeError, ValueError):
            id_admin = None
        id_dataset = dapatkan_dataset_aktif(cursor, buat_baru=True, id_admin=id_admin)
        query = """
            INSERT INTO data_review (id_dataset, teks_review, sumber, tanggal_komentar)
            VALUES (%s, %s, %s, %s)
        """
        cursor.executemany(
            query,
            [(id_dataset, teks, sumber, tanggal) for teks, sumber, tanggal in values_untuk_disimpan]
        )
        batalkan_hasil_analisis(cursor, id_dataset, reset_sentimen=True)
        koneksi.commit()

    cursor.close()
    koneksi.close()

    if jumlah_akhir_disimpan == 0:
        pesan_notif = (
            "Tidak ada data baru yang disimpan. "
            f"Dilewati: {jumlah_kosong} baris kosong."
        )
    elif jumlah_kosong > 0:
        pesan_notif = (
            f"Berhasil menyimpan {jumlah_akhir_disimpan} data ulasan. "
            f"Dilewati: {jumlah_kosong} baris kosong."
        )
    else:
        pesan_notif = f"Berhasil sempurna! Seluruh {jumlah_akhir_disimpan} data ulasan telah disimpan ke database."

    print(json.dumps({
        "status": "success",
        "message": pesan_notif,
        "statistik": {
            "disimpan": jumlah_akhir_disimpan,
            "kosong": jumlah_kosong
        }
    }))

except Exception as e:
    print(json.dumps({"status": "error", "message": f"Error Sistem (proses.py): {str(e)}"}))
