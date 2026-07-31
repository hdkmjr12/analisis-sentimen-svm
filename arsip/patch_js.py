import os

cetak_path = 'cetak_laporan.html'
with open(cetak_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the specific lines inside eksporPDF
js_to_replace = """        function eksporPDF(tipe) {
            tutupModalEkspor();
            
            const btn = document.getElementById('btn-ekspor');
            const originalHTML = btn.innerHTML;
            
            btn.innerHTML = '<span>Menyusun PDF...</span><i class="fa-solid fa-spinner fa-spin"></i>';
            btn.style.opacity = '0.8';
            btn.disabled = true;

            setTimeout(() => {"""

js_replacement = """        function eksporPDF(tipe) {
            setTimeout(() => {"""

content = content.replace(js_to_replace, js_replacement)

# also fix the restore logic at the end of eksporPDF
js_restore = """                    btn.innerHTML = originalHTML;
                    btn.style.opacity = '1';
                    btn.disabled = false;"""
js_restore_replacement = """                    // inline buttons restore logic not strictly needed, page is fine
"""
content = content.replace(js_restore, js_restore_replacement)

# also fix tutupModalEkspor error if it exists
js_tutup = """        function tutupModalEkspor() {
            document.getElementById('modal-ekspor').classList.remove('active');
        }"""
js_tutup_replacement = """        function tutupModalEkspor() {
            // modal-ekspor deleted
        }"""
content = content.replace(js_tutup, js_tutup_replacement)


# Also in eksporPDF, btn.style.display = 'none'; should be wrapped in if
content = content.replace("btn.style.display = 'none';", "/* btn hidden */")


with open(cetak_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Patched JS in cetak_laporan.html")
