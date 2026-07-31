
import sys
import json


sys.stdin.reconfigure(encoding='utf-8')
sys.stdout.reconfigure(encoding='utf-8')

def kirim_json(data):
    print("Content-Type: application/json")
    print()
    print(json.dumps(data))
    sys.exit()

try:
    import mysql.connector
    from model_utils import batalkan_hasil_analisis
    from db_utils import DB_CONFIG, dapatkan_dataset_aktif, arsipkan_dataset_aktif

    input_data = sys.stdin.read()
    if not input_data:
        kirim_json({"status": "error", "message": "Tidak ada perintah yang diterima."})
        
    request = json.loads(input_data)
    action = request.get("action")

    koneksi = mysql.connector.connect(**DB_CONFIG)
    cursor = koneksi.cursor()

    id_dataset = dapatkan_dataset_aktif(cursor)
    if id_dataset is None:
        kirim_json({"status": "error", "message": "Tidak ada dataset aktif untuk dihapus."})

    if action == "all":
        
        # Dataset diarsipkan agar data mentah tetap dapat dipulihkan bila
        # diperlukan; halaman aplikasi hanya membaca dataset berstatus aktif.
        batalkan_hasil_analisis(cursor, id_dataset, reset_sentimen=True)
        arsipkan_dataset_aktif(cursor)
        koneksi.commit()
        kirim_json({"status": "success", "message": "Seluruh review disembunyikan dari dataset aktif dan diarsipkan dengan aman."})

    else:
        kirim_json({"status": "error", "message": "Perintah tidak dikenali."})

    cursor.close()
    koneksi.close()

except Exception as e:
    kirim_json({"status": "error", "message": str(e)})
