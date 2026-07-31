
import sys
import json
from model_utils import muat_model
from text_pipeline import buat_preprocessor, preprocess_teks, hitung_skor_lexicon


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
    kalimat_input = data_json.get('kalimat', '').strip()

    if not kalimat_input:
        kirim_json({"status": "error", "message": "Kalimat tidak boleh kosong."})

    
    stemmer, daftar_stopword = buat_preprocessor()
    teks_input_bersih = preprocess_teks(
        kalimat_input, stemmer, daftar_stopword, {"berlaku": "berlaku", "favorit": "favorit"}
    )

    if not teks_input_bersih.strip():
        kirim_json({"status": "error", "message": "Setelah preprocessing, kalimat menjadi kosong. Coba masukkan kalimat yang lebih panjang."})

    
    skor_lexicon = hitung_skor_lexicon(teks_input_bersih, dengan_detail=True)

    artifact_model = muat_model()
    if artifact_model is None:
        kirim_json({
            "status": "error",
            "message": "Model SVM belum tersedia atau sudah tidak berlaku. Jalankan Analisis Sentimen terlebih dahulu."
        })

    model_svm = artifact_model.get("model")
    vectorizer = artifact_model.get("vectorizer")
    metadata_model = artifact_model.get("metadata", {})
    if model_svm is None or vectorizer is None:
        kirim_json({
            "status": "error",
            "message": "File model SVM tidak lengkap. Jalankan ulang Analisis Sentimen."
        })

    X_input = vectorizer.transform([teks_input_bersih])
    prediksi = model_svm.predict(X_input)

    hasil_sentimen = prediksi[0]

    kirim_json({
        "status": "success",
        "kalimat_asli": kalimat_input,
        "hasil_preprocessing": teks_input_bersih,
        "sentimen": hasil_sentimen,
        "skor_lexicon": {
            "positif": skor_lexicon["positif"],
            "negatif": skor_lexicon["negatif"],
            "detail_positif": skor_lexicon["detail_positif"],
            "detail_negatif": skor_lexicon["detail_negatif"]
        },
        "total_data_training": int(metadata_model.get("total_training", 0))
    })

except Exception as e:
    kirim_json({"status": "error", "message": f"Error Uji Sentimen: {str(e)}"})
