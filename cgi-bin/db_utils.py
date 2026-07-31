import mysql.connector


DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "analisis_svm_relasi",
    "charset": "utf8mb4",
}


def buat_koneksi():
    return mysql.connector.connect(**DB_CONFIG)


def dapatkan_dataset_aktif(cursor, buat_baru=False, id_admin=None):
    cursor.execute("SELECT id_dataset FROM dataset WHERE status = 'aktif' ORDER BY id_dataset DESC LIMIT 1")
    dataset = cursor.fetchone()
    if dataset:
        return dataset["id_dataset"] if isinstance(dataset, dict) else dataset[0]

    if not buat_baru:
        return None

    admin_valid = None
    if id_admin:
        cursor.execute("SELECT id FROM admin_users WHERE id = %s", (id_admin,))
        admin_valid = cursor.fetchone()

    cursor.execute(
        "INSERT INTO dataset (id_admin, nama_dataset, status) VALUES (%s, %s, 'aktif')",
        (id_admin if admin_valid else None, "Dataset Aktif")
    )
    return cursor.lastrowid


def arsipkan_dataset_aktif(cursor):
    id_dataset = dapatkan_dataset_aktif(cursor)
    if id_dataset is not None:
        cursor.execute("UPDATE dataset SET status = 'arsip' WHERE id_dataset = %s", (id_dataset,))
    return id_dataset
