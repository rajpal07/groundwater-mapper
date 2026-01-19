from pypdf import PdfReader

reader = PdfReader("d:/anirudh_kahn/adi_version/Invoice_2025_003_final (1).pdf")
page = reader.pages[0]
print(page.extract_text())
