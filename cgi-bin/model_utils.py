import io
import json
import os

import joblib


PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_DIR = os.path.join(PROJECT_DIR, "model")
MODEL_PATH = os.path.join(MODEL_DIR, "model_sentimen.joblib")


def _buat_artifact(model_svm, vectorizer, metadata):
    buffer = io.BytesIO()
    joblib.dump({
        "model": model_svm,
        "vectorizer": vectorizer,
        "metadata": metadata,
    }, buffer, compress=3)
    return buffer.getvalue()


def _pastikan_tabel(cursor):
    cursor.execute("SHOW TABLES LIKE 'model_artifact'")
    if cursor.fetchone():
        return
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS model_artifact (
            id TINYINT NOT NULL PRIMARY KEY,
            artifact LONGBLOB NOT NULL,
            metadata_json JSON NULL,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
    )


def simpan_model(model_svm, vectorizer, metadata, koneksi=None):
    from db_utils import buat_koneksi

    koneksi_sendiri = koneksi is None
    db = koneksi or buat_koneksi()
    cursor = db.cursor()
    try:
        _pastikan_tabel(cursor)
        cursor.execute(
            """
            INSERT INTO model_artifact (id, artifact, metadata_json)
            VALUES (1, %s, %s)
            ON DUPLICATE KEY UPDATE
                artifact = VALUES(artifact),
                metadata_json = VALUES(metadata_json),
                updated_at = CURRENT_TIMESTAMP
            """,
            (_buat_artifact(model_svm, vectorizer, metadata), json.dumps(metadata)),
        )
        if koneksi_sendiri:
            db.commit()
    finally:
        cursor.close()
        if koneksi_sendiri:
            db.close()


def muat_model():
    try:
        from db_utils import buat_koneksi

        db = buat_koneksi()
        cursor = db.cursor()
        try:
            _pastikan_tabel(cursor)
            cursor.execute("SELECT artifact FROM model_artifact WHERE id = 1")
            row = cursor.fetchone()
            if row and row[0]:
                return joblib.load(io.BytesIO(bytes(row[0])))
        finally:
            cursor.close()
            db.close()
    except Exception:
        # Model bawaan hanya menjadi fallback saat migrasi awal.
        pass

    if os.path.exists(MODEL_PATH):
        return joblib.load(MODEL_PATH)
    return None


def hapus_model():
    try:
        from db_utils import buat_koneksi

        db = buat_koneksi()
        cursor = db.cursor()
        try:
            _pastikan_tabel(cursor)
            cursor.execute("DELETE FROM model_artifact WHERE id = 1")
            db.commit()
        finally:
            cursor.close()
            db.close()
    except Exception:
        # Penghapusan data utama tetap boleh dilanjutkan jika artifact belum ada.
        pass


def batalkan_hasil_analisis(cursor, id_dataset, reset_sentimen=True):
    if reset_sentimen:
        cursor.execute(
            "UPDATE data_review SET sentimen = NULL, id_analisis = NULL WHERE id_dataset = %s",
            (id_dataset,)
        )

    # Penghapusan proses analisis akan menghapus evaluasi terkait secara
    # otomatis melalui foreign key ON DELETE CASCADE.
    cursor.execute("DELETE FROM proses_analisis_svm WHERE id_dataset = %s", (id_dataset,))

    hapus_model()
