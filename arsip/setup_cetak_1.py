import os
import re
import glob
import shutil

html_files = glob.glob('*.html')

# 1. Update sidebars in all files
for filename in html_files:
    if filename in ['tentang.html', 'tentang_sistem.html']:
        continue
    
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()

    # check if 'cetak_laporan.html' is already in sidebar
    if 'href="cetak_laporan.html"' not in content:
        # We find the Hasil Analisis li and append after it
        content = re.sub(
            r'(<li class="menu-item">\s*<a href="hasil\.html"[^>]*>Hasil Analisis</a>\s*</li>)',
            r'\1\n                <li class="menu-item menu-admin"><a href="cetak_laporan.html" class="menu-link">Cetak Laporan</a></li>',
            content
        )
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)

# 2. Modify hasil.html to point to cetak_laporan.html and hide the button from non-admins
hasil_path = 'hasil.html'
if os.path.exists(hasil_path):
    with open(hasil_path, 'r', encoding='utf-8') as f:
        hasil_content = f.read()

    # modify button behavior
    hasil_content = re.sub(
        r'<button class="btn-ekspor fade-up-item h-delay-4" id="btn-ekspor" onclick="bukaModalEkspor\(\)">',
        r'<button class="btn-ekspor fade-up-item h-delay-4 menu-admin" id="btn-ekspor" onclick="window.location.href=\'cetak_laporan.html\'">',
        hasil_content
    )
    with open(hasil_path, 'w', encoding='utf-8') as f:
        f.write(hasil_content)
        
print("Updated sidebars and hasil.html")
