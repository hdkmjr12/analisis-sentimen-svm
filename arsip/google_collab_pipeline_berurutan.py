# =============================================================
# GOOGLE COLAB: PIPELINE BERURUT ANALISIS SENTIMEN LCGC
# =============================================================
# Jalankan file ini sebagai satu notebook/skrip utama di Google Colab.
# Kebutuhan pustaka akan dipasang otomatis pada Colab baru.
#
# Upload seluruh 16 CSV mentah dari folder data scrapp. Aturan preprocessing
# dan lexicon website sudah disertakan dalam skrip ini. Seluruh tahap berjalan berurutan:
# 1. Preprocessing dan seleksi kelayakan
# 2. Pelabelan lexicon
# 3. Pembagian data grouped 80:20
# 4. TF-IDF data latih
# 5. Pelatihan SVM dan confusion matrix
# =============================================================
import io
import base64
import os
import sys
import re
import subprocess
import importlib.util
import importlib.metadata
from collections import Counter
from html import escape


def pastikan_pustaka(nama_modul, nama_paket=None, versi=None):
    """Memasang paket hanya jika belum tersedia di runtime Colab."""
    paket = nama_paket or nama_modul
    belum_ada = importlib.util.find_spec(nama_modul) is None
    versi_berbeda = False
    if not belum_ada and versi:
        try:
            versi_berbeda = importlib.metadata.version(paket) != versi
        except importlib.metadata.PackageNotFoundError:
            versi_berbeda = True
    if belum_ada or versi_berbeda:
        paket_instal = f'{paket}=={versi}' if versi else paket
        print(f'Menyiapkan pustaka {paket}...')
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', '--upgrade', paket_instal])


pastikan_pustaka('Sastrawi')
pastikan_pustaka('sklearn', 'scikit-learn', '1.8.0')
import pandas as pd
import matplotlib.pyplot as plt
from google.colab import files
from IPython.display import display, HTML
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import SVC
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay, classification_report

import sklearn
print(f'Versi scikit-learn untuk pembagian data: {sklearn.__version__}')


def baca_csv(data_file):
    for encoding in ('utf-8-sig', 'utf-8', 'latin1'):
        try:
            return pd.read_csv(io.BytesIO(data_file), encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError('CSV tidak dapat dibaca.')


def tentukan_platform(nama_file, dataframe):
    kolom_sumber = next((k for k in dataframe.columns if k.lower() in ('sumber', 'platform')), None)
    if kolom_sumber:
        return dataframe[kolom_sumber].fillna('').astype(str).str.strip().replace('', pd.NA)
    nama = nama_file.lower()
    if 'youtube' in nama:
        return pd.Series('Youtube', index=dataframe.index)
    if 'tiktok' in nama:
        return pd.Series('Tiktok', index=dataframe.index)
    if 'instagram' in nama:
        return pd.Series('Instagram', index=dataframe.index)
    return pd.Series('-', index=dataframe.index)


def tampilkan_tahap_preprocessing(teks, pipeline, stemmer, stopword, cache):
    """Menampilkan enam tahap dengan aturan yang sama seperti preprocess_teks()."""
    case_folding = str(teks).lower()
    cleaning = re.sub(r"[^a-zA-Z\s]", " ", str(teks)).lower()
    cleaning = re.sub(r"\s+", " ", cleaning).strip()
    tokenizing = cleaning.split()
    normalisasi = pipeline.normalisasi_teks(cleaning)
    tanpa_stopword = [kata for kata in normalisasi.split() if kata not in stopword]
    hasil_stem = []
    for kata in tanpa_stopword:
        if kata not in cache:
            cache[kata] = stemmer.stem(kata)
        hasil_stem.append(cache[kata])
    stemming = " ".join(pipeline.KOREKSI_SASTRAWI.get(kata, kata) for kata in hasil_stem)
    return {
        'teks_asli': str(teks),
        'case_folding': case_folding,
        'cleaning': cleaning,
        'tokenizing': tokenizing,
        'normalisasi': normalisasi.split(),
        'stopword_removal': tanpa_stopword,
        'stemming': stemming.split()
    }


def format_teks(nilai):
    if isinstance(nilai, list):
        return '[' + ', '.join(escape(str(kata)) for kata in nilai) + ']'
    return escape(str(nilai))


def sorot_dihapus(sebelum, sesudah):
    sisa = Counter(sesudah)
    hasil = []
    for kata in sebelum:
        if sisa[kata] > 0:
            hasil.append(escape(str(kata)))
            sisa[kata] -= 1
        else:
            hasil.append(f'<mark>{escape(str(kata))}</mark>')
    return '[' + ', '.join(hasil) + ']'


def sorot_berubah(sebelum, sesudah):
    hasil = []
    for indeks, kata in enumerate(sebelum):
        if indeks >= len(sesudah) or kata != sesudah[indeks]:
            hasil.append(f'<mark>{escape(str(kata))}</mark>')
        else:
            hasil.append(escape(str(kata)))
    return '[' + ', '.join(hasil) + ']'


def sorot_case_folding(teks):
    """Menandai kata yang memiliki huruf kapital sebelum diubah lowercase."""
    teks = str(teks)
    hasil = []
    posisi = 0
    for cocok in re.finditer(r'\b[A-Za-z]*[A-Z][A-Za-z]*\b', teks):
        hasil.append(escape(teks[posisi:cocok.start()]))
        hasil.append(f'<mark>{escape(cocok.group())}</mark>')
        posisi = cocok.end()
    hasil.append(escape(teks[posisi:]))
    return ''.join(hasil)


def sorot_cleaning(teks):
    """Menandai angka, tanda baca, simbol, dan emoji yang akan dihapus."""
    hasil = []
    for karakter in str(teks):
        if re.match(r'[^a-zA-Z\s]', karakter):
            hasil.append(f'<mark>{escape(karakter)}</mark>')
        else:
            hasil.append(escape(karakter))
    return ''.join(hasil)


def tampilkan_tabel_tahap(judul, label_sebelum, label_sesudah, data, kolom_sebelum, kolom_sesudah, sorotan=None):
    """Tabel padat dan terbaca untuk screenshot Word."""
    baris_html = []
    for nomor, baris in enumerate(data, start=1):
        sebelum = baris[kolom_sebelum]
        sesudah = baris[kolom_sesudah]
        if sorotan == 'hapus':
            html_sebelum = sorot_dihapus(sebelum, sesudah)
        elif sorotan == 'ubah':
            html_sebelum = sorot_berubah(sebelum, sesudah)
        elif sorotan == 'case':
            html_sebelum = sorot_case_folding(sebelum)
        elif sorotan == 'clean':
            html_sebelum = sorot_cleaning(sebelum)
        else:
            html_sebelum = format_teks(sebelum)
        baris_html.append(
            f'<tr><td class="no">{nomor}</td>'
            f'<td class="platform">{escape(str(baris["sumber"]))}</td>'
            f'<td>{html_sebelum}</td><td>{format_teks(sesudah)}</td></tr>'
        )

    html_tabel = f'''
    <style>
      .tahap-wrap {{font-family:Arial,sans-serif; width:100%; color:#111827;}}
      .tahap-wrap h3 {{margin:18px 0 7px; font-size:16px; font-weight:700;}}
      .tahap-wrap table {{border-collapse:collapse; width:fit-content; max-width:100%; table-layout:auto; font-size:12px;}}
      .tahap-wrap th {{background:#f3f4f6; border-bottom:2px solid #9ca3af; padding:4px 3px; text-align:left;}}
      .tahap-wrap td {{border-bottom:1px solid #e5e7eb; padding:4px 3px; vertical-align:top; line-height:1.35; overflow-wrap:anywhere;}}
      .tahap-wrap tr:nth-child(even) {{background:#fafafa;}}
      .tahap-wrap .no {{width:1%; text-align:center; white-space:nowrap;}}
      .tahap-wrap .platform {{width:1%; white-space:nowrap;}}
      .tahap-wrap mark {{background:#fff36b; padding:0 2px;}}
    </style>
    <div class="tahap-wrap">
      <h3>{escape(judul)}</h3>
      <table>
        <thead><tr><th class="no">No</th><th class="platform">Platform</th>
        <th>{escape(label_sebelum)}</th><th>{escape(label_sesudah)}</th></tr></thead>
        <tbody>{''.join(baris_html)}</tbody>
      </table>
    </div>
    '''
    display(HTML(html_tabel))


# text_pipeline.py terbaru disematkan agar pengguna hanya mengunggah CSV.
PIPELINE_BASE64 = """
    "aW1wb3J0IHJlDQoNCmZyb20gU2FzdHJhd2kuU3RlbW1lci5TdGVtbWVyRmFjdG9yeSBpbXBvcnQgU3RlbW1lckZhY3RvcnkNCmZyb20gU2FzdHJhd2kuU3Rv"
    "cFdvcmRSZW1vdmVyLlN0b3BXb3JkUmVtb3ZlckZhY3RvcnkgaW1wb3J0IFN0b3BXb3JkUmVtb3ZlckZhY3RvcnkNCg0KDQpLQVRBX1BFTlRJTkcgPSBbJ3Rp"
    "ZGFrJywgJ2J1a2FuJywgJ2JlbHVtJywgJ2t1cmFuZycsICdqYW5nYW4nLCAnc2FuZ2F0JywgJ2xlYmloJ10NCkNVU1RPTV9TVE9QV09SRCA9IFsnYmFuZycs"
    "DQogJ29tJywNCiAnbWluJywNCiAnYnJvJywNCiAnZ2FuJywNCiAnbmdhYicsDQogJ2thaycsDQogJ255YScsDQogJ3NpaCcsDQogJ2tvaycsDQogJ2Rvbmcn"
    "LA0KICdkZWgnLA0KICdsYWgnLA0KICdtYWgnLA0KICdwdW4nLA0KICdrYW4nLA0KICdiamlyJywNCiAnYW5qaXInLA0KICduamlyJywNCiAnYnVzZXQnLA0K"
    "ICdoYWxvJywNCiAnaGFpJywNCiAnbHVyJ10NCktBTVVTX1NMQU5HID0geydhYmcnOiAnYWJhbmcnLA0KICdhaic6ICdzYWphJywNCiAnYWphJzogJ3NhamEn"
    "LA0KICdhamFoJzogJ3NhamEnLA0KICdha3UnOiAnc2F5YScsDQogJ2FsaGFtZHVsaWxhJzogJ3N5dWt1cicsDQogJ2FsaGFtZHVsaWxhaCc6ICdzeXVrdXIn"
    "LA0KICdhbGhhbWR1bGlsbGFoJzogJ3N5dWt1cicsDQogJ2FsbGhhbWR1bGlsYWgnOiAnc3l1a3VyJywNCiAnYW5ha2EnOiAnYW5haycsDQogJ2FuY3VyJzog"
    "J2hhbmN1cicsDQogJ2FuZSc6ICdzYXlhJywNCiAnYXEnOiAnc2F5YScsDQogJ2F0JzogJ290b21hdGlzJywNCiAnYmFuZ2F0JzogJ3NhbmdhdCcsDQogJ2Jh"
    "bmdldCc6ICdzYW5nYXQnLA0KICdiYW5nZyc6ICdhYmFuZycsDQogJ2JhcGEnOiAnYmFwYWsnLA0KICdiYXB1ayc6ICdidXJ1aycsDQogJ2JibSc6ICdiZW5z"
    "aW4nLA0KICdiZWplayc6ICdnYXMnLA0KICdiZW5lcic6ICdiZW5hcicsDQogJ2JlbmVyMic6ICdzYW5nYXQnLA0KICdiZXJpc2lrJzogJ2Jpc2luZycsDQog"
    "J2Jlc3QnOiAnYmFndXMnLA0KICdiZyc6ICdhYmFuZycsDQogJ2Jncyc6ICdiYWd1cycsDQogJ2JndCc6ICdzYW5nYXQnLA0KICdia24nOiAnYnVrYW4nLA0K"
    "ICdibGtuZyc6ICdiZWxha2FuZycsDQogJ2JsbSc6ICdiZWx1bScsDQogJ2JuZ3QnOiAnc2FuZ2F0JywNCiAnYm55YWsnOiAnYmFueWFrJywNCiAnYm55ayc6"
    "ICdiYW55YWsnLA0KICdib3Jvcyc6ICdib3JvcycsDQogJ2Jvcyc6ICdib3MnLA0KICdicic6ICdiYXJ1JywNCiAnYnJzayc6ICdiaXNpbmcnLA0KICdicyc6"
    "ICdiaXNhJywNCiAnYnNhJzogJ2Jpc2EnLA0KICdidWF0JzogJ3VudHVrJywNCiAnY2Fsc2lnJzogJ2NhbHlhIHNpZ3JhJywNCiAnY2VwZXInOiAncmVuZGFo"
    "JywNCiAnY20nOiAnY3VtYScsDQogJ2Ntbic6ICdjdW1hJywNCiAnY3Vhbic6ICd1bnR1bmcnLA0KICdjdW1hbic6ICdjdW1hJywNCiAnZCc6ICdkaScsDQog"
    "J2RhaCc6ICdzdWRhaCcsDQogJ2RnJzogJ2RlbmdhbicsDQogJ2Rnbic6ICdkZW5nYW4nLA0KICdkaCc6ICdzdWRhaCcsDQogJ2RoZSc6ICdkZWgnLA0KICdk"
    "bCc6ICdkdWx1JywNCiAnZGx1JzogJ2R1bHUnLA0KICdkcHQnOiAnZGFwYXQnLA0KICdkcic6ICdkYXJpJywNCiAnZHJpJzogJ2RhcmknLA0KICdlZWUnOiAn"
    "ZWgnLA0KICdlbG8nOiAna2FtdScsDQogJ2VtZyc6ICdtZW1hbmcnLA0KICdlbmFrJzogJ255YW1hbicsDQogJ2VuYWthbic6ICdueWFtYW4nLA0KICdlbmsn"
    "OiAnbnlhbWFuJywNCiAnZW50ZSc6ICdrYW11JywNCiAnZyc6ICd0aWRhaycsDQogJ2dhJzogJ3RpZGFrJywNCiAnZ2FiaXNhJzogJ3RpZGFrIGJpc2EnLA0K"
    "ICdnYWVuYWsnOiAndGlkYWsgbnlhbWFuJywNCiAnZ2FqZSc6ICd0aWRhayBqZWxhcycsDQogJ2dhamVsYXMnOiAndGlkYWsgamVsYXMnLA0KICdnYWsnOiAn"
    "dGlkYWsnLA0KICdnYW5kb3MnOiAnYmFndXMnLA0KICdnYXBhcGEnOiAndGlkYWsgYXBhJywNCiAnZ2FzcnVrJzogJ2dlc2VrJywNCiAnZ2F0YXUnOiAndGlk"
    "YWsgdGFodScsDQogJ2dhdXNhaCc6ICd0aWRhayB1c2FoJywNCiAnZ2V0ZXInOiAnZ2V0YXInLA0KICdnaW1hbmEnOiAnYmFnYWltYW5hJywNCiAnZ2luaSc6"
    "ICdiZWdpbmknLA0KICdnaXR1JzogJ2JlZ2l0dScsDQogJ2drJzogJ3RpZGFrJywNCiAnZ2xvZGFrYW4nOiAnYmlzaW5nJywNCiAnZ21uJzogJ2JhZ2FpbWFu"
    "YScsDQogJ2duJzogJ2JlZ2luaScsDQogJ2dvY2FyJzogJ3Rha3NpJywNCiAnZ29vZCc6ICdiYWd1cycsDQogJ2dwcCc6ICd0aWRhayBhcGEnLA0KICdncmFi"
    "JzogJ3Rha3NpJywNCiAnZ3QnOiAnYmVnaXR1JywNCiAnZ3R1JzogJ2JlZ2l0dScsDQogJ2d0dyc6ICd0aWRhayB0YWh1JywNCiAnZ3VhJzogJ3NheWEnLA0K"
    "ICdndWUnOiAnc2F5YScsDQogJ2d3JzogJ3NheWEnLA0KICdob2F4JzogJ2JvaG9uZycsDQogJ2lyaXQnOiAnaGVtYXQnLA0KICdqZCc6ICdqYWRpJywNCiAn"
    "amRpJzogJ2phZGknLA0KICdqZWxlayc6ICdidXJ1aycsDQogJ2psayc6ICdidXJ1aycsDQogJ2pvcyc6ICdiYWd1cycsDQogJ2pvc2dhbmRvcyc6ICdzYW5n"
    "YXQgYmFndXMnLA0KICdqb3NzJzogJ2JhZ3VzJywNCiAnam9zc3MnOiAnYmFndXMnLA0KICdrYWdhayc6ICd0aWRhaycsDQogJ2thbG8nOiAna2FsYXUnLA0K"
    "ICdrYXJuYSc6ICdrYXJlbmEnLA0KICdrYXJuYWthbic6ICdrYXJlbmEnLA0KICdrYXlhJzogJ3NlcGVydGknLA0KICdrYXlhayc6ICdzZXBlcnRpJywNCiAn"
    "a2VkYXAnOiAnc2VueWFwJywNCiAna2VrJzogJ3NlcGVydGknLA0KICdrZW5jZW5nJzogJ2tlbmNhbmcnLA0KICdrZXJlbic6ICdiYWd1cycsDQogJ2tldWph"
    "bmFuJzogJ2tlaHVqYW5hbicsDQogJ2tsJzogJ2thbGF1JywNCiAna2xhdSc6ICdrYWxhdScsDQogJ2tsbyc6ICdrYWxhdScsDQogJ2tuYWxwb3QnOiAnc2Fs"
    "dXJhbiBidWFuZycsDQogJ2tucCc6ICdrZW5hcGEnLA0KICdrcGQnOiAna2VwYWRhJywNCiAna3JuJzogJ2thcmVuYScsDQogJ2tybmEnOiAna2FyZW5hJywN"
    "CiAna3Vsbyc6ICdzYXlhJywNCiAna3VyZW5nJzogJ2t1cmFuZycsDQogJ2t5ayc6ICdzZXBlcnRpJywNCiAnbGFhYSc6ICdsYWgnLA0KICdsYmgnOiAnbGVi"
    "aWgnLA0KICdsZWxldCc6ICdsYW1iYXQnLA0KICdsZW1vdCc6ICdsYW1iYXQnLA0KICdsZyc6ICdsYWdpJywNCiAnbG15YW4nOiAnY3VrdXAnLA0KICdsbyc6"
    "ICdrYW11JywNCiAnbHUnOiAna2FtdScsDQogJ2x1bSc6ICdiZWx1bScsDQogJ2x1bWF5YW4nOiAnY3VrdXAnLA0KICdtYWhhbCc6ICdtYWhhbCcsDQogJ21h"
    "bnRhYic6ICdiYWd1cycsDQogJ21hbnRhcCc6ICdiYWd1cycsDQogJ21hcyc6ICdhYmFuZycsDQogJ21hdGljJzogJ290b21hdGlzJywNCiAnbWF0aWsnOiAn"
    "b3RvbWF0aXMnLA0KICdtYmFrJzogJ2tha2FrJywNCiAnbWVuZGluZyc6ICdsZWJpaCBiYWlrJywNCiAnbWdrbic6ICdtdW5na2luJywNCiAnbWhsJzogJ21h"
    "aGFsJywNCiAnbW1nJzogJ21lbWFuZycsDQogJ21uZ2tuJzogJ211bmdraW4nLA0KICdtbnVydXQnOiAnbWVudXJ1dCcsDQogJ21vYmknOiAnbW9iaWwnLA0K"
    "ICdtcmVrYSc6ICdtZXJla2EnLA0KICdtcmgnOiAnbXVyYWgnLA0KICdtdCc6ICdtYW51YWwnLA0KICdtdGInOiAnYmFndXMnLA0KICdtdXJhJzogJ211cmFo"
    "JywNCiAnbXVyYWgnOiAnbXVyYWgnLA0KICdtdyc6ICdtYXUnLA0KICduYW5qYWsnOiAndGFuamFrJywNCiAnbmFwYSc6ICdrZW5hcGEnLA0KICduZW11Jzog"
    "J3RlbXUnLA0KICduZ2EnOiAndGlkYWsnLA0KICduZ2VkZW4nOiAnYmVyYXQnLA0KICduZ2dhJzogJ3RpZGFrJywNCiAnbmdnYWsnOiAndGlkYWsnLA0KICdu"
    "Z2snOiAndGlkYWsnLA0KICduaXB1JzogJ3RpcHUnLA0KICdueWFtYW4nOiAnbnlhbWFuJywNCiAnbnlhbmdrdXQnOiAnc2FuZ2t1dCcsDQogJ255bW4nOiAn"
    "bnlhbWFuJywNCiAnb2snOiAnYmFndXMnLA0KICdva2UnOiAnYmFndXMnLA0KICdvcmFnJzogJ29yYW5nJywNCiAnb3JnJzogJ29yYW5nJywNCiAncGFrZSc6"
    "ICdwYWthaScsDQogJ3Bha2VrJzogJ3Bha2FpJywNCiAncGFyYWgnOiAnc2FuZ2F0JywNCiAncGRobCc6ICdwYWRhaGFsJywNCiAncGVnZWwnOiAncGVnYWwn"
    "LA0KICdwZWxnJzogJ3BlbGVrJywNCiAncGVzZW4nOiAncGVzYW4nLA0KICdwbnAnOiAncGVudW1wYW5nJywNCiAncSc6ICdzYXlhJywNCiAncmV2aWV3Jzog"
    "J3VsYXNhbicsDQogJ3JpdmV3JzogJ3VsYXNhbicsDQogJ3JtaCc6ICdydW1haCcsDQogJ3J1Z2knOiAncnVnaScsDQogJ3NhbXBlJzogJ3NhbXBhaScsDQog"
    "J3NhdCBzZXQnOiAnY2VwYXQnLA0KICdzYXRzZXQnOiAnY2VwYXQnLA0KICdzZWtlbic6ICdiZWthcycsDQogJ3Nob2NrJzogJ3N1c3BlbnNpJywNCiAnc2lh"
    "bmcyJzogJ3NpYW5nJywNCiAnc2loaGgnOiAnc2loJywNCiAnc2onOiAnc2FqYScsDQogJ3NrcmcnOiAnc2VrYXJhbmcnLA0KICdza3JuZyc6ICdzZWthcmFu"
    "ZycsDQogJ3NtJzogJ3NhbWEnLA0KICdzbWEnOiAnc2FtYScsDQogJ3Nvayc6ICdzdXNwZW5zaScsDQogJ3Nva2JyZWtlcic6ICdzdXNwZW5zaScsDQogJ3N5"
    "JzogJ3NheWEnLA0KICdzeWEnOiAnc2F5YScsDQogJ3Rhayc6ICd0aWRhaycsDQogJ3RhbXBhJzogJ3RhbnBhJywNCiAndGF1JzogJ3RhaHUnLA0KICd0YXhp"
    "JzogJ3Rha3NpJywNCiAndGhlJzogJ3NhbmdhdCcsDQogJ3RpcGVyJzogJ3RpcGUgcicsDQogJ3RwJzogJ3RhcGknLA0KICd0cGknOiAndGFwaScsDQogJ3Ry"
    "cyc6ICd0ZXJ1cycsDQogJ3RydXMnOiAndGVydXMnLA0KICd0dGVwJzogJ3RldGFwJywNCiAndHRnJzogJ3RlbnRhbmcnLA0KICd0dHAnOiAndGV0YXAnLA0K"
    "ICd0dyc6ICd0YWh1JywNCiAndWRhaCc6ICdzdWRhaCcsDQogJ3VkaCc6ICdzdWRhaCcsDQogJ3Vkaic6ICdzdWRhaCcsDQogJ3VnJzogJ3lhbmcnLA0KICd1"
    "dGsnOiAndW50dWsnLA0KICd2ZWxnJzogJ3BlbGVrJywNCiAndyc6ICdzYXlhJywNCiAnd2t0JzogJ3dha3R1JywNCiAnd29yaXQnOiAnc2VwYWRhbicsDQog"
    "J3dvcnQgaXQnOiAnc2VwYWRhbicsDQogJ3dvcnRoIGl0JzogJ3NlcGFkYW4nLA0KICd5Zyc6ICd5YW5nJywNCiAneW5nJzogJ3lhbmcnLA0KICd6b25rJzog"
    "J2J1cnVrJ30NCktPUkVLU0lfU0FTVFJBV0kgPSB7J2FzYSc6ICdyYXNhJywNCiAnYXdhdCc6ICdyYXdhdCcsDQogJ2Rhcic6ICdzZWthZGFyJywNCiAna2Vi"
    "ZWwnOiAnYmVsaScsDQogJ2tlbic6ICdpbmdpbicsDQogJ2tlbnlhbSc6ICdueWFtYW4nLA0KICdrZXMnOiAna2VzYW4nLA0KICdtdWQnOiAna2VtdWRpJywN"
    "CiAnbnlhbSc6ICdueWFtYW4nfQ0KS0FUQV9LVU5DSV9NT0JJTCA9IHNldChbJ21vYmlsJywNCiAnbGNnYycsDQogJ2F5bGEnLA0KICdhZ3lhJywNCiAnc2ln"
    "cmEnLA0KICdjYWx5YScsDQogJ2JyaW8nLA0KICdrYXJpbXVuJywNCiAnd2Fnb24nLA0KICdkYXRzdW4nLA0KICdtZXNpbicsDQogJ3NldGlyJywNCiAnYmVu"
    "c2luJywNCiAna25hbHBvdCcsDQogJ3ZlbGcnLA0KICdwZWxlaycsDQogJ2JhbicsDQogJ3N1c3BlbnNpJywNCiAna2FiaW4nLA0KICdqb2snLA0KICdiYWdh"
    "c2knLA0KICdhYycsDQogJ3JlbScsDQogJ2tvcGxpbmcnLA0KICdnaWdpJywNCiAnZ2FzJywNCiAnaXJpdCcsDQogJ2Jvcm9zJywNCiAndGFuamFrJywNCiAn"
    "dG9sJywNCiAnamFsYW4nLA0KICdkZWFsZXInLA0KICdoYXJnYScsDQogJ2JlbGknLA0KICdrcmVkaXQnLA0KICdjaWNpbCcsDQogJ3Rha3NpJywNCiAnc2Vy"
    "dmljZScsDQogJ3NlcnZpcycsDQogJ29saScsDQogJ2t1YWxpdGFzJywNCiAncGVyZm9ybWEnLA0KICdueWFtYW4nLA0KICdzZW1waXQnLA0KICdiYWd1cycs"
    "DQogJ2plbGVrJ10pDQpLQVRBX1NQQU1fUkVRVUVTVCA9IHNldChbJ2JhaGFzJywNCiAnbmV4dCcsDQogJ3ZpZGVvJywNCiAnZ2l2ZWF3YXknLA0KICdjb2Jh"
    "aW4nLA0KICdyZXZpZXdpbicsDQogJ3RhbnlhJywNCiAnaW5mbycsDQogJ2hhZGlyJywNCiAnbWFtcGlyJywNCiAnc3VicycsDQogJ2NoYW5uZWwnLA0KICdr"
    "b250ZW4nLA0KICdrYXBhbicsDQogJ3R1dG9yaWFsJ10pDQpLQVRBX1NFTlRJTUVOX1BFTkRFSyA9IHNldCh7J2FtYW4nLA0KICdiYWd1cycsDQogJ2Jpc2lu"
    "ZycsDQogJ2Jvcm9zJywNCiAnYnVydWsnLA0KICdjZXBhdCcsDQogJ2hhbHVzJywNCiAnaGVtYXQnLA0KICdrZWNld2EnLA0KICdrZXJlbicsDQogJ2t1YXQn"
    "LA0KICdsYW1iYXQnLA0KICdsZW1haCcsDQogJ21haGFsJywNCiAnbWFudGFwJywNCiAnbWV3YWgnLA0KICdtdWRhaCcsDQogJ211cmFoJywNCiAnbnlhbWFu"
    "JywNCiAncGFyYWgnLA0KICdwdWFzJywNCiAncnVnaScsDQogJ3J1c2FrJywNCiAnc2VtcGl0JywNCiAnc3RhYmlsJywNCiAnc3VrYScsDQogJ3N1c2FoJywN"
    "CiAndW50dW5nJ30pDQoNCktBVEFfUE9TSVRJRiA9IHNldChbJ2t1YXQnLA0KICd0ZXRlcCcsDQogJ2Z1bmdzaW9uYWwnLA0KICdsdW5hcycsDQogJ2Vrb25v"
    "bWlzJywNCiAnc3VrYScsDQogJ2JncycsDQogJ2Z1bmdzaScsDQogJ3NlbmFuZycsDQogJ2xhcmlzJywNCiAnbXVkYWgnLA0KICdoZWJhdCcsDQogJ3NpcCcs"
    "DQogJ3RlbmFuZycsDQogJ3RlcmphbmdrYXUnLA0KICdzZW1wdXJuYScsDQogJ2tlcmVuJywNCiAnbWFudGVwJywNCiAnbGFuY2FyJywNCiAnZWxlZ2FuJywN"
    "CiAnZGFoc3lhdCcsDQogJ21lbmRpbmdhbicsDQogJ2FhbWlpbicsDQogJ2NhbmdnaWgnLA0KICdiZW5hcicsDQogJ2xlZ2EnLA0KICdrZWJlbGknLA0KICdi"
    "ZXR1bCcsDQogJ3N0YWJpbCcsDQogJ3Jlc3BvbnNpZicsDQogJ3Jla29tZW5kYXNpJywNCiAna29rb2gnLA0KICdpbXBpYW4nLA0KICdtYW50ZWInLA0KICdt"
    "YXNpaCcsDQogJ3NlcnUnLA0KICdyZWtvbWVuJywNCiAnYmVyc3VrdXInLA0KICdsYXBhbmcnLA0KICdiYW5nZ2EnLA0KICdrZW5jYW5nJywNCiAnYmVya2Vs"
    "YXMnLA0KICdnYW5kb3MnLA0KICdiZW5lcicsDQogJ2JhbmRlbCcsDQogJ21hbnRhZicsDQogJ2dhbXBhbmcnLA0KICdtZW5kaW5nJywNCiAnbHVtYXlhbics"
    "DQogJ2FsaGFtZHVsaWxsYWgnLA0KICdhbWFuJywNCiAncGFkYW4nLA0KICdsYWt1JywNCiAndGVyYmFpaycsDQogJ211bHRpZnVuZ3NpJywNCiAnYWRlbScs"
    "DQogJ3RvcCcsDQogJ2tlY2UnLA0KICdhbWluJywNCiAnZmF2b3JpdCcsDQogJ21hbnR1bCcsDQogJ2JlcnN5dWt1cicsDQogJ3B1YXMnLA0KICdsaW5jYWgn"
    "LA0KICdjdWt1cCcsDQogJ2VuYWsnLA0KICd0ZXRhcCcsDQogJ3N5dWt1cicsDQogJ3NldHVqdScsDQogJ3NlcGFkYW4nLA0KICdwcmFrdGlzJywNCiAndGFu"
    "Z2d1aCcsDQogJ29wdGltYWwnLA0KICdzZXN1YWknLA0KICdhd2F0JywNCiAnY2FrZXAnLA0KICdyaW5nYW4nLA0KICdzZW1vZ2EnLA0KICdwYXMnLA0KICd0"
    "ZXJwZXJjYXlhJywNCiAnamFuZ2thdScsDQogJ3N5dWt1cmknLA0KICdzZXBha2F0JywNCiAnbnlhbWFuJywNCiAnYWxoYW1kdWxpbGFoJywNCiAnaXN0aW1l"
    "d2EnLA0KICdiaXNtaWxsYWgnLA0KICdnZXNpdCcsDQogJ2NvY29rJywNCiAndGVyYmFudHUnLA0KICdwcmltYScsDQogJ21hbmZhYXQnLA0KICdtZW5hbmcn"
    "LA0KICdpbXBpJywNCiAnb2tlJywNCiAnam9zJywNCiAnbXVsdXMnLA0KICdkaW5naW4nLA0KICdpbWJhbmcnLA0KICdtZXdhaCcsDQogJ2VtcHVrJywNCiAn"
    "bW9nYScsDQogJ3BlbnRpbmcnLA0KICdrZW5jZW5nJywNCiAnbWFudGFwJywNCiAnbXVyYWgnLA0KICdtYW1wdScsDQogJ25vcm1hbCcsDQogJ2hhbmRhbCcs"
    "DQogJ25naW1iYW5naW4nLA0KICd1bmdndWxhbicsDQogJ3dvcnRoJywNCiAncGxvbmcnLA0KICdtZW5naW1iYW5naScsDQogJ2NlcGF0JywNCiAnbHVhcycs"
    "DQogJ3dhamFyJywNCiAnbmlrbWF0JywNCiAnc2FuZ2d1cCcsDQogJ2JhbnR1JywNCiAnYmFpaycsDQogJ2JhZ3VzJywNCiAnaXJpdCcsDQogJ2FuZGFsJywN"
    "CiAnYXdldCcsDQogJ3NlbGFtYXQnLA0KICdtYW51c2lhd2knLA0KICd1bnR1bmcnLA0KICdzb2x1c2knLA0KICdoYWx1cycsDQogJ2hlbWF0JywNCiAnYmVy"
    "a2FoJ10pDQpLQVRBX05FR0FUSUYgPSBzZXQoWydyZW1laCcsDQogJ2dsb2Rha2FuJywNCiAndGlwaXMnLA0KICdnZXJvYmFrJywNCiAncnVnaScsDQogJ3N1"
    "c2FoJywNCiAna2FsZW5nJywNCiAnYmVsYWd1JywNCiAnYXJvZ2FuJywNCiAnbGFtYmF0JywNCiAnZXJyb3InLA0KICdsZWJheScsDQogJ2NhcGVrJywNCiAn"
    "a3VyYW5nJywNCiAna21haGFsYW4nLA0KICdyZW11aycsDQogJ2xlbW90JywNCiAnc29tYm9uZycsDQogJ2J1YW5nJywNCiAndG9sb2wnLA0KICdnb3lhbmcn"
    "LA0KICdwbGFzdGlrJywNCiAnYm95bycsDQogJ3JleW90JywNCiAnaGluYScsDQogJ21lbnllc2FsJywNCiAnZ2VtYmVuZycsDQogJ25nZWRlbicsDQogJ2Jp"
    "c2luZycsDQogJ3JpYmV0JywNCiAna2VydXB1aycsDQogJ2tlY2V3YScsDQogJ2Jlcm1hc2FsYWgnLA0KICdqZWxla255YScsDQogJ255aWtzYScsDQogJ2Jl"
    "cmlzaWsnLA0KICdiYXB1aycsDQogJ2dldGFyJywNCiAnaGFuY3VyJywNCiAnbmdlbGl0aWsnLA0KICdueWVzZWwnLA0KICdqZWxlaycsDQogJ2J1cnVrJywN"
    "CiAnYmF0YWwnLA0KICdyb21iZW5nJywNCiAnYmFjb3QnLA0KICdrZW1haGFsYW4nLA0KICdnYWdhbCcsDQogJ3NlbXBpdCcsDQogJ25pcHUnLA0KICdvdmVy"
    "cHJpY2UnLA0KICdib2NvcicsDQogJ2FuY3VyJywNCiAnbGVtYWgnLA0KICdrdXJlbmcnLA0KICdwZWdlbCcsDQogJ2JvZG9oJywNCiAnaHVqYXQnLA0KICdu"
    "eWVuZGF0JywNCiAncmluZ2tpaCcsDQogJ2thdHJvaycsDQogJ21pbnVzJywNCiAnbG95bycsDQogJ21hbHUnLA0KICdtdXJhaGFuJywNCiAnYW1wYXMnLA0K"
    "ICdiZW5jaScsDQogJ25nZW5lcycsDQogJ2FuZ2tvdCcsDQogJ2hvYXgnLA0KICdnYWFkYScsDQogJ25nZWh1amF0JywNCiAnamVib2wnLA0KICduZ290YWsn"
    "LA0KICdtYWhhbCcsDQogJ2Jvcm9zJywNCiAncmVudGFuJywNCiAnYm95b3QnLA0KICdtdWFsJywNCiAncGFyYWgnLA0KICdnYXNydWsnLA0KICdiY290JywN"
    "CiAncnVzYWsnLA0KICdqbGsnLA0KICdtZW50b2snLA0KICdrb3BvbmcnLA0KICdrZXJhcycsDQogJ2tlaHVqYW5hbicsDQogJ2dldGVyJywNCiAnc2FtcGFo"
    "JywNCiAnbGltYnVuZycsDQogJ2xlbGV0JywNCiAnb2RvbmcnLA0KICdnbG9kYWsnLA0KICdraG9uZ2d1YW4nLA0KICdrZXBhbmFzYW4nLA0KICdwYW5hcydd"
    "KQ0KRlJBU0FfUE9TSVRJRiA9IFsnbHVhciBiaWFzYScsDQogJ3dvcnRoIGl0JywNCiAnbGViaWggYmFpaycsDQogJ2JlbGkgYmFydScsDQogJ21lbmRpbmcg"
    "YW1iaWwnLA0KICdtZW5kaW5nIGJlbGknLA0KICd0aWRhayBtYWx1JywNCiAnZ2EgbWFsdScsDQogJ2dhayBtYWx1JywNCiAnYnVrYW4gZ2VuZ3NpJywNCiAn"
    "dGlkYWsgYWRhIG1hc2FsYWgnLA0KICd0aWRhayBhZGEga2VuZGFsYScsDQogJ3RhbnBhIG1hc2FsYWgnLA0KICd0YW5wYSBrZW5kYWxhJywNCiAndGlkYWsg"
    "amVsZWsnLA0KICdnYSBqZWxlaycsDQogJ2dhayBqZWxlaycsDQogJ3RpZGFrIG1haGFsJywNCiAnZ2EgbWFoYWwnLA0KICdnYWsgbWFoYWwnLA0KICd0aWRh"
    "ayBib3JvcycsDQogJ2dhIGJvcm9zJywNCiAnZ2FrIGJvcm9zJywNCiAnYW50aSBwYW5hcycsDQogJ2FudGkgaHVqYW4nLA0KICd0aWRhayBiaXNpbmcnLA0K"
    "ICd0aWRhayBiZXJpc2lrJywNCiAndGlkYWsgcnVzYWsnLA0KICd0aWRhayBueWVzZWwnLA0KICd0aWRhayBydWdpJywNCiAndGlkYWsgbGltYnVuZycsDQog"
    "J3RpZGFrIGdhc3J1aycsDQogJ3RpZGFrIG1lbnRvaycsDQogJ3RpZGFrIHJld2VsJywNCiAndGlkYWsgZ2V0YXInLA0KICd0aWRhayBnZXRlcicsDQogJ2dh"
    "IGdldGFyJywNCiAnZ2EgZ2V0ZXInLA0KICdnYWsgZ2V0YXInLA0KICdnYWsgZ2V0ZXInLA0KICd0aWRhayBodWphbicsDQogJ2dhIGh1amFuJywNCiAnZ2Fr"
    "IGh1amFuJywNCiAndGlkYWsga2VwYW5hc2FuJywNCiAnZ2Ega2VwYW5hc2FuJywNCiAndGlkYWsgcGFuYXMnLA0KICdnYSBwYW5hcycsDQogJ2dhayBwYW5h"
    "cycsDQogJ3RpZGFrIGtlaHVqYW5hbicsDQogJ2dhIGtlaHVqYW5hbicsDQogJ2FtYW4gYWphJywNCiAnYW1hbiBhbWFuJywNCiAnZ2EgYWRhIGdldGVyJywN"
    "CiAnZ2FrIGFkYSBnZXRhcicsDQogJ3RpZGFrIGFkYSBnZXRhcicsDQogJ3RpZGFrIGtlbmRhbGEnLA0KICduZ2dhayBrZW5kYWxhJywNCiAnYmlzYSBiZWxp"
    "JywNCiAna3JlZGl0IGx1bmFzJywNCiAnZ2V0YXIgbWFuYScsDQogJ2dldGVyIG1hbmEnLA0KICdtYW5hIGdldGFyJywNCiAnbWFuYSBnZXRlcicsDQogJ3Np"
    "YXBhIGJpbGFuZycsDQogJ2thdGEgc2lhcGEnLA0KICdtYW5hIGFkYScsDQogJ2phbmdhbiBzYWxhaCcsDQogJ3NhbGFoIGJlc2FyJywNCiAndGV0ZXAgam9z"
    "cycsDQogJ3RldGVwIGpvcycsDQogJ3RldGVwIGJhZ3VzJywNCiAndGV0ZXAgbnlhbWFuJywNCiAndGV0ZXAgYW1hbicsDQogJ3RldGVwIGlyaXQnLA0KICd0"
    "ZXRhcCBqb3NzJywNCiAndGV0YXAgam9zJywNCiAndGV0YXAgYmFndXMnLA0KICd0ZXRhcCBueWFtYW4nLA0KICd0ZXRhcCBhbWFuJywNCiAndGV0YXAgaXJp"
    "dCcsDQogJ21hc2loIGJhZ3VzJywNCiAnbWFzaWggbnlhbWFuJywNCiAnbWFzaWggYW1hbicsDQogJ21hc2loIGlyaXQnLA0KICdtYXNpaCBva2UnLA0KICdt"
    "YXNpaCBrZW5jYW5nJywNCiAncGFsaW5nIGlyaXQnLA0KICdwYWxpbmcgbnlhbWFuJywNCiAncGFsaW5nIG11cmFoJywNCiAncGFsaW5nIGJhZ3VzJywNCiAn"
    "cGFsaW5nIGtlcmVuJywNCiAnc2FuZ2F0IG55YW1hbicsDQogJ3NhbmdhdCBiYWd1cycsDQogJ3NhbmdhdCBpcml0JywNCiAnc2FuZ2F0IG11cmFoJywNCiAn"
    "c2FuZ2F0IGtlcmVuJywNCiAnbGViaWggbnlhbWFuJywNCiAnbGViaWggYmFndXMnLA0KICdsZWJpaCBpcml0JywNCiAnbGViaWggbXVyYWgnLA0KICdsZWJp"
    "aCBrZXJlbicsDQogJ2xlYmloIGx1YXMnLA0KICdjdWt1cCBueWFtYW4nLA0KICdjdWt1cCBiYWd1cycsDQogJ2N1a3VwIGlyaXQnLA0KICdjdWt1cCBsdWFz"
    "JywNCiAnY3VrdXAgYW1hbicsDQogJ2FtYW4gbnlhbWFuJywNCiAnbnlhbWFuIGFtYW4nLA0KICdlbmFrIG55YW1hbicsDQogJ2FtYW4ga29rJywNCiAnYmFn"
    "dXMga29rJywNCiAnbnlhbWFuIGtvaycsDQogJ2lyaXQga29rJywNCiAna3VhdCBrb2snLA0KICdnYSBhZGEgbWFzYWxhaCcsDQogJ2dhayBhZGEgbWFzYWxh"
    "aCcsDQogJ2dhIG1hc2FsYWgnLA0KICdnYWsgbWFzYWxhaCcsDQogJ2dhIG55ZXNlbCcsDQogJ2dhayBueWVzZWwnLA0KICdnYSBydWdpJywNCiAnZ2FrIHJ1"
    "Z2knLA0KICd5YW5nIHBlbnRpbmcnLA0KICd5ZyBwZW50aW5nJywNCiAnamVyaWggcGF5YWgnLA0KICdwYWxhIGJhcGFrJ10NCkZSQVNBX05FR0FUSUYgPSBb"
    "J3RpZGFrIGJhZ3VzJywKICdrdXJhbmcgYmFndXMnLA0KICd0aWRhayBpcml0JywNCiAna3VyYW5nIGlyaXQnLA0KICd0aWRhayBhd2V0JywNCiAna3VyYW5n"
    "IGF3ZXQnLA0KICd0aWRhayBueWFtYW4nLA0KICdrdXJhbmcgbnlhbWFuJywNCiAnZ2EgbnlhbWFuJywNCiAnZ2FrIG55YW1hbicsDQogJ3RpZGFrIGVuYWsn"
    "LA0KICdnYSBlbmFrJywNCiAnZ2FrIGVuYWsnLA0KICd0aWRhayBsYWt1JywNCiAnZ2EgbGFrdScsDQogJ2dhayBsYWt1JywNCiAndGlkYWsgYW1hbicsDQog"
    "J2t1cmFuZyBhbWFuJywNCiAndGlkYWsgc2FuZ2d1cCcsDQogJ3RpZGFrIG1hbXB1JywNCiAnYnVrYW4gbW9iaWwnLA0KICdqYW5nYW4gYmVsaScsDQogJ2th"
    "bGVuZyBrZXJ1cHVrJywNCiAnYm9keSBrYWxlbmcnLA0KICdrYXN0YSBiYXdhaCcsDQogJ2thc3RhIHBhbGluZyBiYXdhaCcsDQogJ3VqaSBtZW50YWwnLA0K"
    "ICdtZW5ndWppIG1lbnRhbCcsDQogJ2t1cmFuZyBkaW5naW4nLA0KICd0aWRhayBkaW5naW4nLA0KICdnYSBkaW5naW4nLA0KICdnYWsgZGluZ2luJywNCiAn"
    "a3VyYW5nIG1hbnRhcCcsDQogJ2t1cmFuZyBtYW50ZXAnLA0KICdrdXJhbmcgZml0dXInLA0KICd0aWRhayBhZGEgd2lwZXInLA0KICdnYWFkYSB3aXBlcics"
    "DQogJ3RhbnBhIHdpcGVyJywNCiAnb3ZlciBwcmljZScsDQogJ2thY2FuZyByZWJ1cycsDQogJ2JhdGFsIGJlbGknLA0KICd1cnVuZyBiZWxpJywNCiAndGlk"
    "YWsga3VhdCcsDQogJ2dhIGt1YXQnLA0KICdnYWsga3VhdCcsDQogJ2t1cmFuZyBrdWF0JywNCiAna3VyYW5nIGx1YXMnLA0KICdrdXJhbmcgbGVnYScsDQog"
    "J2t1cmFuZyBlbXB1aycsDQogJ2FjIGt1cmFuZycsDQogJ2FjIGdhJywNCiAnYWMgZ2FrJywNCiAnYWMgdGlkYWsnLA0KICdzYW5nYXQgbWFoYWwnLA0KICd0"
    "ZXJsYWx1IG1haGFsJywNCiAnc2FuZ2F0IGJvcm9zJywNCiAndGVybGFsdSBib3JvcycsDQogJ3NhbmdhdCBzZW1waXQnLA0KICd0ZXJsYWx1IHNlbXBpdCcs"
    "DQogJ3NhbmdhdCBiaXNpbmcnLA0KICd0ZXJsYWx1IGJpc2luZyddCgojIFRhbWJhaGFuIGJlcmRhc2Fya2FuIGtvc2FrYXRhIGtlbHVoYW4geWFuZyBtdW5j"
    "dWwgcGFkYSBkYXRhc2V0IG90b21vdGlmLgojIEthdGEgdW11bSB0aWRhayBkaXRhbWJhaGthbiBzZWNhcmEgc2VtYmFyYW5nYW47IGZva3VzbnlhIHBhZGEg"
    "aXN0aWxhaCB5YW5nCiMgbWVtaWxpa2kgbWFrbmEgbmVnYXRpZiBkYWxhbSBrb250ZWtzIGtlbmRhcmFhbiBhdGF1IGhhcmdhIGtlbmRhcmFhbi4KS0FUQV9O"
    "RUdBVElGLnVwZGF0ZSh7CiAgICAncHJpbWl0aWYnLCAna3VubycsICduZ2VzZWxpbicsICduYWppcycsICdtaW5pbScsICdwYWtzYScsICduZ29yZW5nJwp9"
    "KQpGUkFTQV9QT1NJVElGLmV4dGVuZChbCiAgICAndGlkYWsgYnVydWsnLCAndGlkYWsgdGVybGFsdSBtYWhhbCcsICd0aWRhayBtYWhhbCBzZWthbGknLAog"
    "ICAgJ3RpZGFrIGplbGVrIGtvaycsICd0aWRhayBqZWxlayBzYW1hIHNla2FsaScKXSkKRlJBU0FfTkVHQVRJRi5leHRlbmQoWwogICAgJ2hhcmdhIGdvcmVu"
    "ZycsICdoYXJnYSBkaWdvcmVuZycsICdmaXR1ciBtaW5pbScsICdtaW5pbSBhbWFuJywKICAgICdwaW50dSByaW5nYW4nLCAna3VhbGl0YXMgYnVydWsnLCAn"
    "bWVzaW4gZ2V0YXInLCAndGVybGFsdSBnZXRhcicsCiAgICAnbW9kZWwga3VubycsICdoZWFkIHVuaXQgcHJpbWl0aWYnLCAndGlkYWsgbnlhbWFuJywgJ3Rp"
    "ZGFrIGFtYW4nCl0pCg0KS0FNVVNfU0xBTkdfRlJBU0EgPSB7azogdiBmb3IgaywgdiBpbiBLQU1VU19TTEFORy5pdGVtcygpIGlmICIgIiBpbiBrfQ0KS0FN"
    "VVNfU0xBTkdfS0FUQSA9IHtrOiB2IGZvciBrLCB2IGluIEtBTVVTX1NMQU5HLml0ZW1zKCkgaWYgIiAiIG5vdCBpbiBrfQ0KDQoNCmRlZiBidWF0X3ByZXBy"
    "b2Nlc3NvcigpOg0KICAgIHN0ZW1tZXIgPSBTdGVtbWVyRmFjdG9yeSgpLmNyZWF0ZV9zdGVtbWVyKCkNCiAgICBzdG9wd29yZF9hc2xpID0gU3RvcFdvcmRS"
    "ZW1vdmVyRmFjdG9yeSgpLmdldF9zdG9wX3dvcmRzKCkNCiAgICBzdG9wd29yZCA9IHtrYXRhIGZvciBrYXRhIGluIHN0b3B3b3JkX2FzbGkgaWYga2F0YSBu"
    "b3QgaW4gS0FUQV9QRU5USU5HfQ0KICAgIHN0b3B3b3JkLnVwZGF0ZShDVVNUT01fU1RPUFdPUkQpDQogICAgcmV0dXJuIHN0ZW1tZXIsIHN0b3B3b3JkDQoN"
    "Cg0KZGVmIG5vcm1hbGlzYXNpX3Rla3ModGVrcyk6DQogICAgZm9yIGZyYXNhIGluIHNvcnRlZChLQU1VU19TTEFOR19GUkFTQSwga2V5PWxlbiwgcmV2ZXJz"
    "ZT1UcnVlKToNCiAgICAgICAgdGVrcyA9IHJlLnN1YihyZiIoPzwhXHcpe3JlLmVzY2FwZShmcmFzYSl9KD8hXHcpIiwgS0FNVVNfU0xBTkdfRlJBU0FbZnJh"
    "c2FdLCB0ZWtzKQ0KICAgIHJldHVybiAiICIuam9pbihLQU1VU19TTEFOR19LQVRBLmdldChrYXRhLCBrYXRhKSBmb3Iga2F0YSBpbiB0ZWtzLnNwbGl0KCkp"
    "DQoNCg0KZGVmIHByZXByb2Nlc3NfdGVrcyh0ZWtzLCBzdGVtbWVyLCBzdG9wd29yZCwgY2FjaGVfc3RlbW1pbmc9Tm9uZSk6DQogICAgY2FjaGUgPSBjYWNo"
    "ZV9zdGVtbWluZyBpZiBjYWNoZV9zdGVtbWluZyBpcyBub3QgTm9uZSBlbHNlIHt9DQogICAgdGVrc19iZXJzaWggPSByZS5zdWIociJbXmEtekEtWlxzXSIs"
    "ICIgIiwgc3RyKHRla3MpKS5sb3dlcigpDQogICAgdGVrc19iZXJzaWggPSByZS5zdWIociJccysiLCAiICIsIHRla3NfYmVyc2loKS5zdHJpcCgpDQogICAg"
    "dGVrc19ub3JtYWwgPSBub3JtYWxpc2FzaV90ZWtzKHRla3NfYmVyc2loKQ0KICAgIHRhbnBhX3N0b3B3b3JkID0gW2thdGEgZm9yIGthdGEgaW4gdGVrc19u"
    "b3JtYWwuc3BsaXQoKSBpZiBrYXRhIG5vdCBpbiBzdG9wd29yZF0NCg0KICAgIGhhc2lsX3N0ZW0gPSBbXQ0KICAgIGZvciBrYXRhIGluIHRhbnBhX3N0b3B3"
    "b3JkOg0KICAgICAgICBpZiBrYXRhIG5vdCBpbiBjYWNoZToNCiAgICAgICAgICAgIGNhY2hlW2thdGFdID0gc3RlbW1lci5zdGVtKGthdGEpDQogICAgICAg"
    "IGhhc2lsX3N0ZW0uYXBwZW5kKGNhY2hlW2thdGFdKQ0KDQogICAgcmV0dXJuICIgIi5qb2luKEtPUkVLU0lfU0FTVFJBV0kuZ2V0KGthdGEsIGthdGEpIGZv"
    "ciBrYXRhIGluIGhhc2lsX3N0ZW0pDQoNCg0KZGVmIGNla19rZWxheWFrYW4odGVrcyk6DQogICAga2F0YV9rYXRhID0gdGVrcy5zcGxpdCgpDQogICAgdG9r"
    "ZW4gPSBzZXQoa2F0YV9rYXRhKQ0KICAgIGlmIG5vdCBrYXRhX2thdGE6DQogICAgICAgIHJldHVybiBGYWxzZQ0KICAgIGlmIGxlbihrYXRhX2thdGEpID09"
    "IDE6DQogICAgICAgIHJldHVybiBrYXRhX2thdGFbMF0gaW4gS0FUQV9TRU5USU1FTl9QRU5ERUsNCiAgICBhZGFfa29udGVrcyA9IGJvb2wodG9rZW4gJiBL"
    "QVRBX0tVTkNJX01PQklMKSBvciBib29sKHRva2VuICYgS0FUQV9TRU5USU1FTl9QRU5ERUspDQogICAgYWRhX3NwYW0gPSBib29sKHRva2VuICYgS0FUQV9T"
    "UEFNX1JFUVVFU1QpDQogICAgcmV0dXJuIGFkYV9rb250ZWtzIGFuZCBub3QgYWRhX3NwYW0NCg0KDQpkZWYgaGl0dW5nX3Nrb3JfbGV4aWNvbih0ZWtzLCBk"
    "ZW5nYW5fZGV0YWlsPUZhbHNlKToKICAgIHRla3NfbG93ZXIgPSBzdHIodGVrcykubG93ZXIoKQogICAgdG9rZW4gPSBzZXQodGVrc19sb3dlci5zcGxpdCgp"
    "KQogICAgc2tvcl9wb3MgPSAwCiAgICBza29yX25lZyA9IDAKICAgIGRldGFpbF9wb3MgPSBbXQogICAgZGV0YWlsX25lZyA9IFtdCgogICAgIyBQcmlvcml0"
    "YXNrYW4gZnJhc2EgeWFuZyBwYWxpbmcgcGFuamFuZy4gU2V0ZWxhaCBzZWJ1YWggZnJhc2EgY29jb2ssCiAgICAjIGJhZ2lhbiB0ZXJzZWJ1dCBkaXR1dHVw"
    "IGFnYXIga2F0YSBkaSBkYWxhbW55YSB0aWRhayBkaWhpdHVuZyBrZW1iYWxpCiAgICAjIGRlbmdhbiBwb2xhcml0YXMgYmVybGF3YW5hbiAobWlzLiAidGlk"
    "YWsgYnVydWsiIGRhbiBrYXRhICJidXJ1ayIpLgogICAgZnJhc2FfYmVybGFiZWwgPSBbKGZyYXNhLCAnUE9TSVRJRicpIGZvciBmcmFzYSBpbiBGUkFTQV9Q"
    "T1NJVElGXQogICAgZnJhc2FfYmVybGFiZWwgKz0gWyhmcmFzYSwgJ05FR0FUSUYnKSBmb3IgZnJhc2EgaW4gRlJBU0FfTkVHQVRJRl0KICAgIHRla3Nfc2lz"
    "YSA9IHRla3NfbG93ZXIKICAgIGZvciBmcmFzYSwgbGFiZWwgaW4gc29ydGVkKGZyYXNhX2JlcmxhYmVsLCBrZXk9bGFtYmRhIGl0ZW06IGxlbihpdGVtWzBd"
    "KSwgcmV2ZXJzZT1UcnVlKToKICAgICAgICBwb2xhID0gcmYnKD88IVx3KXtyZS5lc2NhcGUoZnJhc2EpfSg/IVx3KScKICAgICAgICBpZiByZS5zZWFyY2go"
    "cG9sYSwgdGVrc19zaXNhKToKICAgICAgICAgICAgaWYgbGFiZWwgPT0gJ1BPU0lUSUYnOgogICAgICAgICAgICAgICAgc2tvcl9wb3MgKz0gMwogICAgICAg"
    "ICAgICAgICAgaWYgZGVuZ2FuX2RldGFpbDoKICAgICAgICAgICAgICAgICAgICBkZXRhaWxfcG9zLmFwcGVuZChmJyJ7ZnJhc2F9IiAoKzMpJykKICAgICAg"
    "ICAgICAgZWxzZToKICAgICAgICAgICAgICAgIHNrb3JfbmVnICs9IDMKICAgICAgICAgICAgICAgIGlmIGRlbmdhbl9kZXRhaWw6CiAgICAgICAgICAgICAg"
    "ICAgICAgZGV0YWlsX25lZy5hcHBlbmQoZicie2ZyYXNhfSIgKCszKScpCiAgICAgICAgICAgIHRla3Nfc2lzYSA9IHJlLnN1Yihwb2xhLCAnICcsIHRla3Nf"
    "c2lzYSkKCiAgICB0b2tlbl9zaXNhID0gc2V0KHRla3Nfc2lzYS5zcGxpdCgpKQogICAgZm9yIGthdGEgaW4gS0FUQV9QT1NJVElGOgogICAgICAgIGlmIGth"
    "dGEgaW4gdG9rZW5fc2lzYToKICAgICAgICAgICAgc2tvcl9wb3MgKz0gMQogICAgICAgICAgICBpZiBkZW5nYW5fZGV0YWlsOgogICAgICAgICAgICAgICAg"
    "ZGV0YWlsX3Bvcy5hcHBlbmQoZicie2thdGF9IiAoKzEpJykKICAgIGZvciBrYXRhIGluIEtBVEFfTkVHQVRJRjoKICAgICAgICBpZiBrYXRhIGluIHRva2Vu"
    "X3Npc2E6CiAgICAgICAgICAgIHNrb3JfbmVnICs9IDEKICAgICAgICAgICAgaWYgZGVuZ2FuX2RldGFpbDoNCiAgICAgICAgICAgICAgICBkZXRhaWxfbmVn"
    "LmFwcGVuZChmJyJ7a2F0YX0iICgrMSknKQ0KDQogICAgcmV0dXJuIHsNCiAgICAgICAgInBvc2l0aWYiOiBza29yX3BvcywNCiAgICAgICAgIm5lZ2F0aWYi"
    "OiBza29yX25lZywNCiAgICAgICAgImRldGFpbF9wb3NpdGlmIjogZGV0YWlsX3BvcywNCiAgICAgICAgImRldGFpbF9uZWdhdGlmIjogZGV0YWlsX25lZywN"
    "CiAgICB9DQoNCg0KZGVmIGxhYmVsX2xleGljb24odGVrcyk6DQogICAgc2tvciA9IGhpdHVuZ19za29yX2xleGljb24odGVrcykNCiAgICBpZiBza29yWyJw"
    "b3NpdGlmIl0gPiBza29yWyJuZWdhdGlmIl06DQogICAgICAgIHJldHVybiAiUE9TSVRJRiINCiAgICBpZiBza29yWyJuZWdhdGlmIl0gPiBza29yWyJwb3Np"
    "dGlmIl06DQogICAgICAgIHJldHVybiAiTkVHQVRJRiINCiAgICByZXR1cm4gIk5FVFJBTCINCg=="
"""
with open('text_pipeline.py', 'wb') as file_pipeline:
    # Tanda kutip dari pecahan teks diabaikan agar aman saat kode ditempel di Colab.
    file_pipeline.write(base64.b64decode(PIPELINE_BASE64.replace('"', '')))
sys.path.insert(0, os.getcwd())
import text_pipeline as pipeline

print('Upload seluruh file CSV mentah dari folder data scrapp:')
uploaded_csv = files.upload()
nama_csv = [n for n in uploaded_csv if n.lower().endswith('.csv')]
if not nama_csv:
    raise ValueError('Tidak ada CSV yang dipilih. Unggah seluruh CSV mentah dari folder data scrapp.')

# =============================================================
# TAHAP 1 - PREPROCESSING DAN SELEKSI KELAYAKAN
# =============================================================
data_per_file = []
for nama_file in nama_csv:
    df_file = baca_csv(uploaded_csv[nama_file])
    kolom_teks = next((k for k in df_file.columns if k.lower() in ('teks_review', 'review', 'komentar', 'comment', 'text')), None)
    if kolom_teks is None:
        print(f'File dilewati, kolom teks tidak ditemukan: {nama_file}')
        continue
    data_per_file.append(pd.DataFrame({
        'teks_review': df_file[kolom_teks].fillna('').astype(str),
        'sumber': tentukan_platform(nama_file, df_file),
        'file_sumber': nama_file
    }))

if not data_per_file:
    raise ValueError('Tidak ada file CSV yang dapat diproses.')

df = pd.concat(data_per_file, ignore_index=True)
df['_id_urut'] = range(len(df))
stemmer, stopword = pipeline.buat_preprocessor()
cache_stemming = {'berlaku': 'berlaku', 'favorit': 'favorit'}

hasil, status = [], []
for teks in df['teks_review']:
    teks_bersih = pipeline.preprocess_teks(teks, stemmer, stopword, cache_stemming)
    hasil.append(teks_bersih)
    status.append('layak' if pipeline.cek_kelayakan(teks_bersih) else 'tidak_layak')

df['hasil_preprocessing'] = hasil
df['status_kelayakan'] = status
df_layak = df[df['status_kelayakan'] == 'layak'].copy()
df_arsip = df[df['status_kelayakan'] == 'tidak_layak'].copy()

print('\nTAHAP 1 - SELEKSI KELAYAKAN')
print(f'Ulasan mentah: {len(df)}')
print(f'Data layak: {len(df_layak)}')
print(f'Data tidak layak/arsip: {len(df_arsip)}')
display(df.groupby(['sumber', 'status_kelayakan']).size().unstack(fill_value=0))

# Satu set contoh yang sama dipakai pada seluruh tabel tahap berikutnya.
# Hanya data layak yang dipilih agar dapat ditampilkan pula pada pelabelan,
# pembagian data, dan TF-IDF.
jumlah_contoh = min(15, len(df_layak))
df_sampel_konsisten = df_layak.head(jumlah_contoh).copy()
print(f'Contoh hasil enam tahap preprocessing ({jumlah_contoh} data layak yang sama):')
contoh_tahap = []
cache_tampil = {'berlaku': 'berlaku', 'favorit': 'favorit'}
for _, baris in df_sampel_konsisten.iterrows():
    contoh = tampilkan_tahap_preprocessing(baris['teks_review'], pipeline, stemmer, stopword, cache_tampil)
    contoh['sumber'] = baris['sumber']
    contoh['status_kelayakan'] = baris['status_kelayakan']
    contoh_tahap.append(contoh)

tampilkan_tabel_tahap(
    'TAHAP 1: CASE FOLDING', 'Sebelum (Teks Asli)', 'Sesudah (Case Folding)',
    contoh_tahap, 'teks_asli', 'case_folding', 'case'
)
tampilkan_tabel_tahap(
    'TAHAP 2: CLEANING', 'Sebelum (Case Folding)', 'Sesudah (Cleaning)',
    contoh_tahap, 'case_folding', 'cleaning', 'clean'
)
tampilkan_tabel_tahap(
    'TAHAP 3: TOKENIZING', 'Sebelum (Cleaning)', 'Sesudah (Token)',
    contoh_tahap, 'cleaning', 'tokenizing'
)
tampilkan_tabel_tahap(
    'TAHAP 4: NORMALISASI KATA', 'Sebelum (Token)', 'Sesudah (Normalisasi)',
    contoh_tahap, 'tokenizing', 'normalisasi', 'ubah'
)
tampilkan_tabel_tahap(
    'TAHAP 5: STOPWORD REMOVAL', 'Sebelum (Normalisasi)', 'Sesudah (Stopword)',
    contoh_tahap, 'normalisasi', 'stopword_removal', 'hapus'
)
tampilkan_tabel_tahap(
    'TAHAP 6: STEMMING', 'Sebelum (Stopword)', 'Sesudah (Stemming)',
    contoh_tahap, 'stopword_removal', 'stemming', 'ubah'
)

print('Contoh data tidak layak yang tetap diarsipkan:')
display(df_arsip[['teks_review', 'hasil_preprocessing', 'sumber']].head(15))

# =============================================================
# TAHAP 2 - PELABELAN LEXICON
# =============================================================
df_layak['label_lexicon'] = df_layak['hasil_preprocessing'].apply(pipeline.label_lexicon)
df_sampel_konsisten = df_layak[df_layak['_id_urut'].isin(df_sampel_konsisten['_id_urut'])].copy()
df_sampel_konsisten = df_sampel_konsisten.set_index('_id_urut').loc[
    df_layak.head(jumlah_contoh)['_id_urut']
].reset_index()
print('\nTAHAP 2 - PELABELAN LEXICON')
urutan_sentimen = ['POSITIF', 'NEGATIF', 'NETRAL']
nama_sentimen = {'POSITIF': 'Positif', 'NEGATIF': 'Negatif', 'NETRAL': 'Netral'}
warna_sentimen = {'POSITIF': '#2ecc71', 'NEGATIF': '#e74c3c', 'NETRAL': '#95a5a6'}

jumlah_sentimen = (
    df_layak['label_lexicon']
    .value_counts()
    .reindex(urutan_sentimen, fill_value=0)
)
display(jumlah_sentimen.rename(index=nama_sentimen).rename_axis('sentimen').reset_index(name='jumlah'))

# Diagram memakai seluruh data layak, bukan hanya 15 contoh data tampilan.
plt.figure(figsize=(7, 4.8))
plt.pie(
    jumlah_sentimen.values,
    labels=[nama_sentimen[label] for label in jumlah_sentimen.index],
    colors=[warna_sentimen[label] for label in jumlah_sentimen.index],
    explode=[0.06, 0, 0],
    autopct='%1.1f%%',
    startangle=145,
    shadow=True,
    textprops={'fontsize': 11, 'fontweight': 'bold'}
)
plt.title('Distribusi Kelas Sentimen', fontsize=14, fontweight='bold', pad=12)
plt.axis('equal')
plt.show()

print('RINCIAN JUMLAH DATA (KESELURUHAN)')
for label, jumlah in jumlah_sentimen.items():
    print(f'- {nama_sentimen[label]}: {jumlah} ulasan')
print(f'Total keseluruhan: {jumlah_sentimen.sum()} ulasan')

print('\nRINCIAN JUMLAH DATA (PER PLATFORM)')
jumlah_platform = pd.crosstab(df_layak['sumber'], df_layak['label_lexicon']).reindex(
    columns=urutan_sentimen, fill_value=0
)
for platform, baris in jumlah_platform.iterrows():
    print(f'\nPlatform: {platform}')
    for label in urutan_sentimen:
        print(f'- {nama_sentimen[label]}: {baris[label]} ulasan')
    print(f'Total {platform}: {baris.sum()} ulasan')

detail_skor = df_sampel_konsisten['hasil_preprocessing'].apply(pipeline.hitung_skor_lexicon)
contoh_label = df_sampel_konsisten[['teks_review', 'hasil_preprocessing', 'label_lexicon']].copy()
contoh_label.insert(0, 'no_sampel', range(1, len(contoh_label) + 1))
contoh_label['skor_positif'] = [skor['positif'] for skor in detail_skor]
contoh_label['skor_negatif'] = [skor['negatif'] for skor in detail_skor]
display(contoh_label)

# =============================================================
# TAHAP 3 - PEMBAGIAN DATA 80:20 BERKELOMPOK
# =============================================================
df_layak = df_layak.sort_values(['hasil_preprocessing', 'teks_review', '_id_urut']).reset_index(drop=True)
list_teks = df_layak['hasil_preprocessing'].tolist()
y_label = df_layak['label_lexicon'].tolist()
jumlah_per_kelas = pd.Series(y_label).value_counts()
jumlah_kelompok = pd.DataFrame({'teks': list_teks, 'label': y_label}).drop_duplicates().groupby('label').size()

if len(jumlah_per_kelas) < 2 or jumlah_per_kelas.min() < 2:
    raise ValueError('SVM memerlukan minimal dua kelas dan minimal dua data per kelas.')
if jumlah_kelompok.min() < 5:
    raise ValueError('Grouped split memerlukan minimal lima kelompok teks unik per kelas.')

pembagi = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)
indeks_training, indeks_testing = next(pembagi.split(list_teks, y_label, groups=list_teks))
X_train_teks = [list_teks[i] for i in indeks_training]
X_test_teks = [list_teks[i] for i in indeks_testing]
y_train = [y_label[i] for i in indeks_training]
y_test = [y_label[i] for i in indeks_testing]

print('\nTAHAP 3 - PEMBAGIAN DATA')
print(f'Total: {len(list_teks)} | Training: {len(X_train_teks)} | Testing: {len(X_test_teks)}')
distribusi_split = pd.DataFrame({
    'Data Latih': pd.Series(y_train).value_counts(),
    'Data Uji': pd.Series(y_test).value_counts()
}).reindex(['POSITIF', 'NEGATIF', 'NETRAL']).fillna(0).astype(int)
display(distribusi_split)

# Diagram perbandingan jumlah data latih dan data uji.
jumlah_total_split = len(list_teks)
jumlah_latih = len(X_train_teks)
jumlah_uji = len(X_test_teks)
persen_latih = jumlah_latih / jumlah_total_split * 100
persen_uji = jumlah_uji / jumlah_total_split * 100

fig, ax = plt.subplots(figsize=(8, 4.2))
jenis_data = ['Data Latih', 'Data Uji']
jumlah_data = [jumlah_latih, jumlah_uji]
warna_split = ['#3498db', '#f39c12']
batang = ax.barh(jenis_data, jumlah_data, color=warna_split, height=0.62)

for baris, jumlah, persen in zip(batang, jumlah_data, [persen_latih, persen_uji]):
    ax.text(
        jumlah + jumlah_total_split * 0.015,
        baris.get_y() + baris.get_height() / 2,
        f'{jumlah} ulasan ({persen:.1f}%)',
        va='center', fontsize=10, fontweight='bold'
    )

ax.set_title('Pembagian Data Latih dan Data Uji 80:20', fontsize=14, fontweight='bold', pad=12)
ax.set_xlabel('Jumlah Ulasan')
ax.set_ylabel('Jenis Data')
ax.set_xlim(0, jumlah_total_split * 1.12)
ax.grid(axis='x', linestyle='--', alpha=0.3)
ax.set_axisbelow(True)
fig.text(
    0.125, 0.96,
    f'Menggunakan data layak hasil preprocessing dengan total: {jumlah_total_split} ulasan',
    fontsize=9
)
plt.tight_layout(rect=[0, 0, 1, 0.94])
plt.show()

df_layak['kelompok_data'] = ''
df_layak.loc[indeks_training, 'kelompok_data'] = 'Data Latih'
df_layak.loc[indeks_testing, 'kelompok_data'] = 'Data Uji'
sampel_pembagian = df_layak.set_index('_id_urut').loc[
    df_sampel_konsisten['_id_urut']
].reset_index()
contoh_split = sampel_pembagian[['teks_review', 'hasil_preprocessing', 'label_lexicon', 'kelompok_data']].copy()
contoh_split.insert(0, 'no_sampel', range(1, len(contoh_split) + 1))
print('Pembagian untuk 15 sampel yang sama:')
display(contoh_split)

# =============================================================
# TAHAP 4 - TF-IDF (HANYA FIT PADA DATA LATIH)
# =============================================================
vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_df=0.95, sublinear_tf=True)
X_train = vectorizer.fit_transform(X_train_teks)
X_test = vectorizer.transform(X_test_teks)
print('\nTAHAP 4 - TF-IDF')
print(f'Matriks data latih: {X_train.shape}')
print(f'Matriks data uji: {X_test.shape}')
print('Parameter: ngram_range=(1,2), min_df=2, max_df=0.95, sublinear_tf=True')
fitur = vectorizer.get_feature_names_out()
X_sampel = vectorizer.transform(sampel_pembagian['hasil_preprocessing'].tolist())
contoh_tfidf = pd.DataFrame(
    X_sampel.toarray(),
    columns=fitur,
    index=[f'Sampel {i + 1}' for i in range(len(sampel_pembagian))]
)
print('Contoh matriks TF-IDF untuk 15 sampel yang sama dan maksimal 15 fitur pertama.')
display(contoh_tfidf.iloc[:, :min(15, len(fitur))].round(4))

# =============================================================
# TAHAP 5 - SVM DAN CONFUSION MATRIX
# =============================================================
model = SVC(kernel='linear', class_weight='balanced', C=10, random_state=42)
model.fit(X_train, y_train)
y_pred = model.predict(X_test)

urutan_label = ['POSITIF', 'NEGATIF', 'NETRAL']
cm = confusion_matrix(y_test, y_pred, labels=urutan_label)
akurasi = cm.trace() / cm.sum() * 100

print('\nTAHAP 5 - EVALUASI SVM')
print(f'Akurasi: {akurasi:.2f}%')
fig, ax = plt.subplots(figsize=(7, 5))
ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=urutan_label).plot(cmap='Blues', ax=ax, values_format='d')
ax.set_title('Confusion Matrix SVM LCGC (Grouped Split 80:20)')
plt.tight_layout()
plt.show()
display(pd.DataFrame(classification_report(y_test, y_pred, labels=urutan_label, output_dict=True)).transpose().round(3))

# Arsip hasil agar tiap tahap dapat ditelusuri kembali.
df.to_csv('01_hasil_preprocessing_dan_seleksi.csv', index=False, encoding='utf-8-sig')
df_layak.to_csv('02_data_layak_dan_label_lexicon.csv', index=False, encoding='utf-8-sig')
df_arsip.to_csv('arsip_data_tidak_layak.csv', index=False, encoding='utf-8-sig')
files.download('02_data_layak_dan_label_lexicon.csv')
