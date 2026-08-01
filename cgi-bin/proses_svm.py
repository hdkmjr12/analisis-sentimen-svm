import sys
import json
from collections import Counter
from math import ceil

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import SVC
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.metrics import accuracy_score, confusion_matrix

from db_utils import buat_koneksi, dapatkan_dataset_aktif
from model_utils import simpan_model
from text_pipeline import label_lexicon


sys.stdout.reconfigure(encoding='utf-8')


def kirim_json(data):
    print("Content-Type: application/json\n")
    print(json.dumps(data))
    sys.exit()


try:
    koneksi = buat_koneksi()
    cursor = koneksi.cursor(dictionary=True)

    id_dataset = dapatkan_dataset_aktif(cursor)
    if id_dataset is None:
        kirim_json({"status": "error", "message": "Tidak ada dataset aktif untuk dianalisis."})

    cursor.execute(
        """
        SELECT id, teks_review, hasil_preprocessing, id_preprocessing
        FROM data_review
        WHERE id_dataset = %s
          AND status_kelayakan = 'layak'
          AND hasil_preprocessing IS NOT NULL
          AND hasil_preprocessing <> ''
        """,
        (id_dataset,)
    )
    baris_data = cursor.fetchall()
    if not baris_data:
        kirim_json({"status": "error", "message": "Tidak ada data layak yang siap dianalisis. Lakukan Preprocessing terlebih dahulu."})

    def teks_unicode(nilai):
        if isinstance(nilai, (bytes, bytearray)):
            return nilai.decode('utf-8', 'ignore')
        return str(nilai)

    # Urutan kanonis menjaga hasil pembagian tetap konsisten untuk dataset sama.
    baris_data.sort(key=lambda baris: (
        teks_unicode(baris['hasil_preprocessing']),
        teks_unicode(baris['teks_review']),
        int(baris['id'])
    ))

    id_preprocessing_set = {baris['id_preprocessing'] for baris in baris_data}
    if None in id_preprocessing_set or len(id_preprocessing_set) != 1:
        kirim_json({
            "status": "error",
            "message": "Dataset tidak berasal dari satu proses preprocessing yang sama. Jalankan Preprocessing kembali."
        })
    id_preprocessing = id_preprocessing_set.pop()

    list_id = [baris['id'] for baris in baris_data]
    list_teks_bersih = [teks_unicode(baris['hasil_preprocessing']) for baris in baris_data]
    y_label = [label_lexicon(teks) for teks in list_teks_bersih]

    jumlah_per_kelas = Counter(y_label)
    jumlah_kelas = len(jumlah_per_kelas)
    if jumlah_kelas < 2:
        kelas_satu = next(iter(jumlah_per_kelas), "-")
        kirim_json({"status": "error", "message": f"Analisis tidak dapat dilakukan karena seluruh data berlabel {kelas_satu}. SVM membutuhkan minimal dua kelas sentimen."})

    kelas_terlalu_sedikit = {kelas: jumlah for kelas, jumlah in jumlah_per_kelas.items() if jumlah < 2}
    if kelas_terlalu_sedikit:
        rincian = ", ".join(f"{kelas}: {jumlah} data" for kelas, jumlah in kelas_terlalu_sedikit.items())
        kirim_json({"status": "error", "message": f"Analisis tidak dapat dilakukan. Kelas tidak cukup untuk pembagian stratified: {rincian}."})

    jumlah_testing = ceil(len(y_label) * 0.2)
    jumlah_training = len(y_label) - jumlah_testing
    if jumlah_testing < jumlah_kelas or jumlah_training < jumlah_kelas:
        kirim_json({"status": "error", "message": "Jumlah data belum mencukupi untuk pembagian stratified 80:20."})

    kelompok_per_kelas = {
        kelas: len({teks for teks, label in zip(list_teks_bersih, y_label) if label == kelas})
        for kelas in jumlah_per_kelas
    }
    kelas_group_kurang = {kelas: jumlah for kelas, jumlah in kelompok_per_kelas.items() if jumlah < 5}
    if kelas_group_kurang:
        rincian = ", ".join(f"{kelas}: {jumlah} kelompok unik" for kelas, jumlah in kelas_group_kurang.items())
        kirim_json({"status": "error", "message": f"Grouped split 80:20 membutuhkan minimal 5 kelompok teks unik pada setiap kelas: {rincian}."})

    pembagi_group = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)
    indeks_training, indeks_testing = next(pembagi_group.split(list_teks_bersih, y_label, groups=list_teks_bersih))
    X_train_teks = [list_teks_bersih[i] for i in indeks_training]
    X_test_teks = [list_teks_bersih[i] for i in indeks_testing]
    y_train = [y_label[i] for i in indeks_training]
    y_test = [y_label[i] for i in indeks_testing]

    if set(X_train_teks) & set(X_test_teks):
        kirim_json({"status": "error", "message": "Grouped split gagal karena teks identik ditemukan pada training dan testing."})

    vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_df=0.95, sublinear_tf=True)
    try:
        X_train = vectorizer.fit_transform(X_train_teks)
    except ValueError as error_tfidf:
        kirim_json({"status": "error", "message": f"TF-IDF tidak dapat dibentuk dari data training: {str(error_tfidf)}"})

    X_test = vectorizer.transform(X_test_teks)
    X_semua = vectorizer.transform(list_teks_bersih)
    model_svm = SVC(kernel='linear', class_weight='balanced', C=10, random_state=42)
    model_svm.fit(X_train, y_train)

    prediksi_testing = model_svm.predict(X_test)
    prediksi_svm = model_svm.predict(X_semua)
    akurasi = accuracy_score(y_test, prediksi_testing)
    label_cm = ["POSITIF", "NEGATIF", "NETRAL"]
    cm = confusion_matrix(y_test, prediksi_testing, labels=label_cm)

    konfigurasi = {
        "metode_split": "StratifiedGroupKFold-5 (satu fold sebagai testing)",
        "random_state": 42,
        "tfidf": {"ngram_range": [1, 2], "min_df": 2, "max_df": 0.95, "sublinear_tf": True},
        "svm": {"kernel": "linear", "C": 10, "class_weight": "balanced"}
    }
    cursor.execute(
        "INSERT INTO proses_analisis_svm (id_dataset, id_preprocessing, konfigurasi) VALUES (%s, %s, %s)",
        (id_dataset, id_preprocessing, json.dumps(konfigurasi))
    )
    id_analisis = cursor.lastrowid

    cursor.executemany(
        """
        UPDATE data_review
        SET sentimen = %s, id_analisis = %s
        WHERE id = %s AND id_dataset = %s
        """,
        [(prediksi_svm[i], id_analisis, list_id[i], id_dataset) for i in range(len(list_id))]
    )

    cursor.execute(
        """
        INSERT INTO hasil_evaluasi_svm (
            id_analisis, total_data, total_training, total_testing, akurasi,
            pos_pos, pos_neg, pos_net,
            neg_pos, neg_neg, neg_net,
            net_pos, net_neg, net_net
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            id_analisis, len(list_teks_bersih), len(X_train_teks), len(X_test_teks), round(akurasi * 100, 2),
            int(cm[0][0]), int(cm[0][1]), int(cm[0][2]),
            int(cm[1][0]), int(cm[1][1]), int(cm[1][2]),
            int(cm[2][0]), int(cm[2][1]), int(cm[2][2])
        )
    )

    simpan_model(model_svm, vectorizer, {
        "versi": 2,
        "id_dataset": id_dataset,
        "id_analisis": id_analisis,
        "total_data": len(list_teks_bersih),
        "total_training": len(X_train_teks),
        "total_testing": len(X_test_teks),
        "jumlah_per_kelas": dict(jumlah_per_kelas),
        "kelompok_unik_per_kelas": kelompok_per_kelas,
        "metode_split": "StratifiedGroupKFold-5",
        "random_state": 42,
    }, koneksi=koneksi)

    koneksi.commit()
    cursor.close()
    koneksi.close()

    data_terproses = [
        {"id": list_id[i], "teks": baris_data[i]['teks_review'], "hasil": list_teks_bersih[i], "sentimen": prediksi_svm[i]}
        for i in range(len(list_id))
    ]
    kirim_json({
        "status": "success",
        "message": f"Analisis SVM selesai. {len(list_id)} data ulasan diproses. Akurasi data testing: {round(akurasi * 100, 2)}%.",
        "akurasi": round(akurasi * 100, 2),
        "data": data_terproses
    })

except Exception as e:
    kirim_json({"status": "error", "message": f"Error SVM: {str(e)}"})
