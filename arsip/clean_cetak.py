import re
import sys

try:
    with open('cetak_laporan.html', 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Remove previously added inline buttons block
    # It starts with <div class="ekspor-btn-group" and ends with </div>
    # Actually, we can use a more precise regex.
    content = re.sub(
        r'<div class="ekspor-btn-group" style="display: flex; gap: 10px; flex-wrap: wrap;">.*?<\/div>',
        '',
        content,
        flags=re.DOTALL
    )

    # 2. Inject new UI and wrap area-cetak
    new_ui = """
            <div id="cetak-ui" style="display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 70vh; padding: 20px;">
                <i class="fa-solid fa-print" style="font-size: 5rem; color: var(--primary-blue); margin-bottom: 25px;"></i>
                <h1 style="font-size: 2.2rem; margin-bottom: 15px; color: #0f172a;">Menu Cetak Laporan</h1>
                <p style="color: #64748b; margin-bottom: 40px; font-size: 1.1rem; max-width: 500px; text-align: center;">Silakan pilih jenis laporan yang ingin Anda unduh. Laporan akan di-generate berdasarkan keseluruhan data sentimen.</p>
                
                <div class="ekspor-btn-group" style="display: flex; gap: 15px; justify-content: center; flex-wrap: wrap;" id="cetak-buttons">
                    <button class="btn btn-outline" onclick="eksporPDF('preprocessing')" style="padding: 12px 24px; font-size: 1.05rem; cursor: pointer; border-radius: 8px; border: 2px solid var(--primary-blue); color: var(--primary-blue); background: transparent; font-weight: 600;">
                        <i class="fa-solid fa-filter"></i> Laporan Preprocessing
                    </button>
                    <button class="btn btn-outline" onclick="eksporPDF('sentimen')" style="padding: 12px 24px; font-size: 1.05rem; cursor: pointer; border-radius: 8px; border: 2px solid var(--primary-blue); color: var(--primary-blue); background: transparent; font-weight: 600;">
                        <i class="fa-solid fa-chart-pie"></i> Laporan Sentimen
                    </button>
                    <button class="btn btn-primary" onclick="eksporPDF('semua')" style="padding: 12px 24px; font-size: 1.05rem; cursor: pointer; border-radius: 8px; border: none; background: var(--primary-blue); color: white; font-weight: 600; box-shadow: 0 4px 10px rgba(74,133,246,0.3);">
                        <i class="fa-solid fa-file-pdf"></i> Cetak Semua (PDF)
                    </button>
                    <button class="btn btn-success" onclick="eksporCSV()" style="padding: 12px 24px; font-size: 1.05rem; cursor: pointer; border-radius: 8px; border: none; background: #16a34a; color: white; font-weight: 600; box-shadow: 0 4px 10px rgba(22,163,74,0.3);">
                        <i class="fa-solid fa-file-csv"></i> Ekspor CSV
                    </button>
                </div>
                
                <div id="cetak-loading" style="display: none; margin-top: 35px; font-size: 1.3rem; color: var(--primary-blue); font-weight: 600;">
                    <i class="fa-solid fa-spinner fa-spin"></i> Sedang Menyusun File PDF...
                </div>
            </div>

            <div id="area-cetak-wrapper" style="position: absolute; left: -9999px; top: 0; width: 1200px; background: white;">
"""

    if '<div id="area-cetak-wrapper"' not in content:
        content = content.replace('<div id="area-cetak">', new_ui + '\n<div id="area-cetak">')
        # Close the wrapper div before the end of content-area
        # finding the closing of content-area is tricky, but it's right before </main>
        # we can just find </main> and replace the div above it.
        # Actually it's easier to just find `</div> \n        </div>\n    </main>`
        
        # Let's just insert </div> right before the final </div> of content-area.
        # A simple way is to replace </main> with </div></main> since we added one open div.
        content = content.replace('</main>', '</div></main>')

    # 3. Update the eksporPDF function to show loading
    js_update_1 = """
        function eksporPDF(tipe) {
            document.getElementById('cetak-buttons').style.display = 'none';
            document.getElementById('cetak-loading').style.display = 'block';

            setTimeout(() => {"""
    
    # We replace the beginning of eksporPDF
    content = re.sub(
        r'function eksporPDF\(tipe\)\s*\{\s*setTimeout\(\(\)\s*=>\s*\{',
        js_update_1,
        content
    )

    # 4. Update the end of eksporPDF (html2pdf().then)
    js_update_2 = """
                    document.getElementById('cetak-buttons').style.display = 'flex';
                    document.getElementById('cetak-loading').style.display = 'none';
"""
    # find where to inject restoring buttons
    # in html2pdf().then(() => { ... })
    content = content.replace("judulHalaman.style.display = 'block';", "judulHalaman.style.display = 'block';\n" + js_update_2)


    # Same for eksporCSV
    csv_update_1 = """
        function eksporCSV() {
            document.getElementById('cetak-buttons').style.display = 'none';
            document.getElementById('cetak-loading').style.display = 'block';
            document.getElementById('cetak-loading').innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Menyusun CSV...';
"""
    content = re.sub(
        r'function eksporCSV\(\)\s*\{',
        csv_update_1,
        content
    )

    # at the end of eksporCSV
    csv_update_2 = """
            setTimeout(() => {
                document.getElementById('cetak-buttons').style.display = 'flex';
                document.getElementById('cetak-loading').style.display = 'none';
            }, 1000);
        }
    </script>
"""
    content = re.sub(
        r'\}\s*<\/script>',
        csv_update_2,
        content
    )


    with open('cetak_laporan.html', 'w', encoding='utf-8') as f:
        f.write(content)

    print("Success")
except Exception as e:
    print(f"Error: {e}")
