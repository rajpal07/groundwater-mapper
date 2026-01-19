
import sys

try:
    import fitz  # PyMuPDF
except ImportError:
    print("Error: PyMuPDF (fitz) is not installed. Please install it using 'pip install pymupdf'.")
    sys.exit(1)

def modify_invoice_pdf(input_path, output_path, new_number):
    try:
        doc = fitz.open(input_path)
        page = doc[0]  # Assuming single page or first page

        # Search for the old number
        old_number = "2026_005"
        text_instances = page.search_for(old_number)

        if not text_instances:
            print(f"Warning: Text '{old_number}' not found. Searching for 'Invoice' label to approximate location.")
            # Fallback: search for "Invoice" or similar if the number is dynamic or not exact
            # For now, let's just exit if we can't find the specific number to replace, 
            # as blindly placing text might overwrite wrong things.
            # But let's try to find "Invoice No" or something if specific number fails?
            # Actually, user said change "2026_005" to "2026_004". I should look for that specific text.
            print(f"Could not find exact text '{old_number}'. Listing all text on page to debug:")
            print(page.get_text())
            return

        print(f"Found {len(text_instances)} instances of '{old_number}'.")

        for rect in text_instances:
            print(f"Modifying instance at {rect}")
            
            # 1. Add a white rectangle to cover the old text (Redaction)
            # We inflate the rect slightly to ensure full coverage
            # annot = page.add_redact_annot(rect, fill=(1, 1, 1)) # fill with white
            # page.apply_redactions() 
            # Using specific shape insertion to cover might be safer/easier than redaction validation workflow
            
            # Draw a white rectangle
            shape = page.new_shape()
            shape.draw_rect(rect)
            shape.finish(color=(1, 1, 1), fill=(1, 1, 1), width=0)
            shape.commit()

            # 2. Insert new text
            # precise placement is tricky. using rect.bl (bottom left) as origin?
            # fontsize needs to be guessed or measured. 
            # Let's try to match the fontsize. 
            # text_instances doesn't give font info directly.
            
            # Simple insertion:
            page.insert_text(rect.bl, new_number, fontsize=12, color=(0, 0, 0)) # Defaulting to 12, might need adjustment

        doc.save(output_path)
        print(f"Successfully modified PDF. Saved to: {output_path}")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    input_pdf = "d:/anirudh_kahn/adi_version/Invoice_2026_005.pdf"
    output_pdf = "d:/anirudh_kahn/adi_version/Invoice_2026_004.pdf"
    new_num = "2026_004"
    
    modify_invoice_pdf(input_pdf, output_pdf, new_num)
