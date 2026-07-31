import os

import joblib


PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_DIR = os.path.join(PROJECT_DIR, "model")
MODEL_PATH = os.path.join(MODEL_DIR, "model_sentimen.joblib")


def simpan_model(model_svm, vectorizer, metadata):
    os.makedirs(MODEL_DIR, exist_ok=True)
    temporary_path = MODEL_PATH + ".tmp"
    joblib.dump({
        "model": model_svm,
        "vectorizer": vectorizer,
        "metadata": metadata,
    }, temporary_path)
    os.replace(temporary_path, MODEL_PATH)


def muat_model():
    if not os.path.exists(MODEL_PATH):
        return None
    return joblib.load(MODEL_PATH)


def hapus_model():
    for path in (MODEL_PATH, MODEL_PATH + ".tmp"):
        if os.path.exists(path):
            os.remove(path)


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
