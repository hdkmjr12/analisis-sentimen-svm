
import sys
import json
import mysql.connector
from db_utils import DB_CONFIG


sys.stdin.reconfigure(encoding='utf-8')
sys.stdout.reconfigure(encoding='utf-8')

def kirim_json(data):
    print("Content-Type: application/json\n")
    print(json.dumps(data))
    sys.exit()

try:
    
    input_data = sys.stdin.read()
    if not input_data:
        kirim_json({"status": "error", "message": "Tidak ada data yang dikirim."})

    data_json = json.loads(input_data)
    user_input = data_json.get("username", "").strip()
    pass_input = data_json.get("password", "").strip()

    if not user_input or not pass_input:
        kirim_json({"status": "error", "message": "Username dan Password tidak boleh kosong."})

    
    koneksi = mysql.connector.connect(**DB_CONFIG)
    cursor = koneksi.cursor(dictionary=True)

    
    cursor.execute("SHOW TABLES LIKE 'admin_users'")
    tabel_ada = cursor.fetchone()

    
    query = "SELECT * FROM admin_users WHERE username = %s AND password = %s"
    cursor.execute(query, (user_input, pass_input))
    admin_valid = cursor.fetchone()

    cursor.close()
    koneksi.close()

    
    if admin_valid:
        kirim_json({"status": "success", "message": "Login berhasil!", "id_admin": admin_valid["id"]})
    else:
        kirim_json({"status": "error", "message": "Username atau Password salah!"})

except Exception as e:
    kirim_json({"status": "error", "message": f"Error Sistem: {str(e)}"})
