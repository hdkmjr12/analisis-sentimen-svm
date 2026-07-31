import os
import re

# 1. Modify cetak_laporan.html
cetak_path = 'cetak_laporan.html'
with open(cetak_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Make sidebar active for Cetak Laporan
content = re.sub(
    r'<li class="menu-item"><a href="hasil\.html" class="menu-link active">Hasil Analisis</a></li>',
    r'<li class="menu-item"><a href="hasil.html" class="menu-link">Hasil Analisis</a></li>',
    content
)
content = re.sub(
    r'<li class="menu-item menu-admin"><a href="cetak_laporan\.html" class="menu-link">Cetak Laporan</a></li>',
    r'<li class="menu-item menu-admin"><a href="cetak_laporan.html" class="menu-link active">Cetak Laporan</a></li>',
    content
)

# Change Titles
content = content.replace('<title>Hasil Analisis - Analisis SVM</title>', '<title>Cetak Laporan - Analisis SVM</title>')
content = content.replace('<h1 class="page-title">Hasil Analisis Sentimen</h1>', '<h1 class="page-title">Cetak Laporan</h1>')

# Add Admin check in JS
admin_check_js = """
        // --- 1. FITUR ROLE (HAK AKSES) ---
        document.addEventListener("DOMContentLoaded", function() {
            const role = localStorage.getItem('role_akses');
            if (role !== 'admin') {
                window.location.href = 'dashboard.html';
                return;
            }
"""
content = re.sub(
    r'// --- 1\. FITUR ROLE \(HAK AKSES\) ---\s*document\.addEventListener\("DOMContentLoaded", function\(\) {',
    admin_check_js,
    content
)

# Replace the export button with inline export buttons
inline_buttons = """
                        <div class="ekspor-btn-group" style="display: flex; gap: 10px; flex-wrap: wrap;">
                            <button class="btn btn-outline" onclick="eksporPDF('preprocessing')" style="padding: 10px 15px; font-size: 0.9rem; cursor: pointer; border-radius: 8px; border: 1px solid var(--primary-blue); color: var(--primary-blue); background: transparent;">
                                <i class="fa-solid fa-filter"></i> Laporan Preprocessing
                            </button>
                            <button class="btn btn-outline" onclick="eksporPDF('sentimen')" style="padding: 10px 15px; font-size: 0.9rem; cursor: pointer; border-radius: 8px; border: 1px solid var(--primary-blue); color: var(--primary-blue); background: transparent;">
                                <i class="fa-solid fa-chart-pie"></i> Laporan Sentimen
                            </button>
                            <button class="btn btn-primary" onclick="eksporPDF('semua')" style="padding: 10px 15px; font-size: 0.9rem; cursor: pointer; border-radius: 8px; border: none; background: var(--primary-blue); color: white;">
                                <i class="fa-solid fa-file-pdf"></i> Cetak Semua (PDF)
                            </button>
                            <button class="btn btn-success" onclick="eksporCSV()" style="padding: 10px 15px; font-size: 0.9rem; cursor: pointer; border-radius: 8px; border: none; background: #16a34a; color: white;">
                                <i class="fa-solid fa-file-csv"></i> Ekspor CSV
                            </button>
                        </div>
"""
# Remove the btn-ekspor and replace with inline_buttons
content = re.sub(
    r'<button class="btn-ekspor fade-up-item h-delay-4[^>]*id="btn-ekspor"[^>]*>.*?<\/button>',
    inline_buttons,
    content,
    flags=re.DOTALL
)

# Remove modal-ekspor HTML
content = re.sub(
    r'<div class="modal-ekspor" id="modal-ekspor">.*?<\/div>\s*<\/div>',
    r'',
    content,
    flags=re.DOTALL
)

with open(cetak_path, 'w', encoding='utf-8') as f:
    f.write(content)


# 2. Modify hasil.html
hasil_path = 'hasil.html'
with open(hasil_path, 'r', encoding='utf-8') as f:
    hasil_content = f.read()

# Remove the btn-ekspor completely
hasil_content = re.sub(
    r'<button class="btn-ekspor fade-up-item h-delay-4[^>]*id="btn-ekspor"[^>]*>.*?<\/button>',
    r'',
    hasil_content,
    flags=re.DOTALL
)
# Remove modal-ekspor completely
hasil_content = re.sub(
    r'<div class="modal-ekspor" id="modal-ekspor">.*?<\/div>\s*<\/div>',
    r'',
    hasil_content,
    flags=re.DOTALL
)

with open(hasil_path, 'w', encoding='utf-8') as f:
    f.write(hasil_content)

print("Modification done.")
