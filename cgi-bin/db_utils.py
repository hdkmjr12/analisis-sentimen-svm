import os

import mysql.connector


PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CA_PATH = os.path.join(PROJECT_DIR, "certs", "aiven-ca.pem")


def _db_config():
    config = {
        "host": os.environ.get("DB_HOST", "localhost"),
        "port": int(os.environ.get("DB_PORT", "3306")),
        "user": os.environ.get("DB_USER", "root"),
        "password": os.environ.get("DB_PASSWORD", ""),
        "database": os.environ.get("DB_NAME", "analisis_svm_relasi"),
        "charset": "utf8mb4",
        "connection_timeout": 15,
    }

    ca_path = os.environ.get("DB_SSL_CA_PATH", DEFAULT_CA_PATH)
    if os.environ.get("DB_HOST"):
        config["ssl_disabled"] = False
        if os.path.exists(ca_path):
            config.update({
                "ssl_ca": ca_path,
                "ssl_verify_cert": True,
            })

    return config


DB_CONFIG = _db_config()


def buat_koneksi():
    return mysql.connector.connect(**_db_config())


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
