from fpdf import FPDF
from datetime import datetime

class PDF(FPDF):
    def header(self):
        # Page Border at 5mm from edge (A4 210x297)
        # Rect(x, y, w, h) -> x=5, y=5, w=200, h=287
        self.set_line_width(0.5)
        self.rect(5, 5, 200, 287)
        self.set_line_width(0.2)

    def footer(self):
        # Move text up to avoid hitting bottom border (at y=292)
        self.set_y(-20) 
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

def create_invoice(invoice_num):
    pdf = PDF()
    
    # Text Margins at 10mm (Requested)
    # This leaves 5mm gap between Border(5mm) and Text(10mm)
    pdf.set_margins(10, 10, 10)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=10) 

    # --- CONSTANTS ---
    CONTENT_WIDTH = 190 # 210 - 10 - 10
    RIGHT_ALIGN_X = 10 + CONTENT_WIDTH # 200

    # Helper for Bold Label + Normal Value
    def print_field(label, value, ln=1):
        pdf.set_font('Arial', 'B', 11)
        lbl_w = pdf.get_string_width(label)
        pdf.cell(lbl_w, 5, label, 0, 0)
        
        pdf.set_font('Arial', '', 11)
        pdf.cell(0, 5, f" {value}", 0, ln)

    # Helper for Right Aligned Field
    def print_right_field(label, value):
        pdf.set_font('Arial', 'B', 11)
        lbl_w = pdf.get_string_width(label)
        pdf.set_font('Arial', '', 11)
        val_w = pdf.get_string_width(f" {value}")
        
        total_w = lbl_w + val_w
        start_x = RIGHT_ALIGN_X - total_w 
        
        pdf.set_x(start_x)
        pdf.set_font('Arial', 'B', 11)
        pdf.cell(lbl_w, 6, label, 0, 0)
        pdf.set_font('Arial', '', 11)
        pdf.cell(val_w, 6, f" {value}", 0, 1)

    # --- HEADER ---
    # Top Left
    top_y = pdf.get_y() # Should be 15

    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 8, "ANIRUDDHA BORSE.", 0, 1)
    
    # Address Block
    print_field("Address:", "75 PIGDONS RD WAURN PONDS ,")
    pdf.set_font('Arial', '', 11)
    # Indent or just print? Image showing it below address label inline or next line?
    # Reference image: "Address: 75 ... , \n VIC Australia"
    # It wraps under the value, not the label.
    # We'll just print it on next line flush left or indented?
    # Flush left looks fine based on simple layouts.
    pdf.cell(0, 5, "VIC Australia 3216", 0, 1)
    
    print_field("Phone:", "+61 413757694")
    print_field("Email:", "aniruddhaborse9@gmail.com")

    # Top Right Block
    # We must reset Y to top but keep X
    pdf.set_y(top_y)
    
    # "INVOICE" Title Big
    pdf.set_font('Arial', 'B', 16) 
    # Use Cell width matching content width to create right alignment manually?
    # Or just set X.
    # pdf.cell(0, 8, "INVOICE", 0, 1, 'R') -> This respects margins (0 width = until margin).
    pdf.cell(0, 8, "INVOICE", 0, 1, 'R')
    
    pdf.ln(5)
    # Details aligned right
    # We need to manually set X for each line to align end to RIGHT_ALIGN_X (195)
    # But print_right_field handles X calc.
    # We just need to make sure we don't overwrite left content if it overlaps (it doesn't here).
    
    # Reset Y to match lines? 
    # Left side has Name (8) + Addr (5) + VIC (5) + Phone (5) + Email (5) ~ 28mm height
    # Right side "INVOICE" (8) + Gap (5) + Invoice# (6) + Date (6) ~ 25mm
    # So they fit side-by-side approximately.
    
    # Move cursor down to align with Address lines roughly?
    # pdf.set_y(top_y + 13) # Approx where VIC/Phone is
    # Let's simple LN relative to INVOICE title
    
    print_right_field("INVOICE:", invoice_num)
    
    pdf.set_x(130)
    today = datetime.now().strftime("%d/%m/%Y")
    print_right_field("DATE:", today)

    # --- TO SECTION ---
    # Ensure Y is below both blocks
    current_y = pdf.get_y()
    left_block_bottom = top_y + 8 + 5 + 5 + 5 + 5 # ~ 43
    pdf.set_y(max(current_y, left_block_bottom) + 10)
    
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 6, "TO:", 0, 1)
    
    print_field("Contact:", "Kahn Vincent")
    print_field("Company:", "CTS Environmental Pty. Ltd.")
    print_field("Address:", "5 - 7 Brentwood Way, Waurn Pond, Victoria, 3216")
    print_field("Phone:", "+61 412 603 423")
    
    pdf.ln(5)
    
    # Separator Line
    # Full width of content (10 to 200)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    
    # --- TABLE SECTION ---
    pdf.ln(5)
    
    # Column Widths - Total 190
    w_item = 15
    w_cat = 45   
    w_desc = 102
    w_hrs = 28   
    
    pdf.set_font('Arial', 'B', 10)
    # Headers
    pdf.cell(w_item, 8, "Item", 1, 0, 'C', 0)
    pdf.cell(w_cat, 8, "Activity Category", 1, 0, 'C', 0)
    pdf.cell(w_desc, 8, "Description of Work", 1, 0, 'C', 0)
    pdf.cell(w_hrs, 8, "Hours", 1, 1, 'C', 0)

    data = [
        (1, "Analysis & Planning", "Integration Planning:", " Analyzing the existing project architecture to design the safe integration of the new Chemical Visualization module.", 2.5),
        (2, "Development", "Chemical Visualization Logic:", " Implementing enhancements to the contour generation backend.", 3.5),
        (3, "Development", "Flow Visualization:", " Restoring and calibrating quiver arrows for groundwater flow direction.", 2.0),
        (4, "Optimization", "Data Pipeline Optimization:", " Optimizing data ingestion routines and refining parameter detection logic to reduce processing overhead.", 2.0),
    ]

    pdf.set_font('Arial', '', 10)
    total_hours = 0
    
    def draw_description_cell(x, y, w, text_bold, text_normal):
        h = 5 
        current_x = x
        current_y = y
        
        max_x = x + w
        
        def print_chunk(text, font_style):
            nonlocal current_x, current_y
            pdf.set_font('Arial', font_style, 10)
            words = text.split()
            for word in words:
                word_w = pdf.get_string_width(word + " ")
                if current_x + word_w > max_x:
                    current_y += h
                    current_x = x
                
                pdf.set_xy(current_x, current_y)
                pdf.cell(word_w, h, word + " ", 0, 0)
                current_x += word_w

        if text_bold:
            print_chunk(text_bold, 'B')
            
        if text_normal:
            print_chunk(text_normal, '')
            
        return (current_y - y) + h

    for item, category, desc_bold, desc_normal, hours in data:
        start_x = pdf.get_x()
        start_y = pdf.get_y()
        desc_x = start_x + w_item + w_cat
        
        # Calc Height
        h_line = 5
        curr_x = desc_x
        num_lines = 1
        max_desc_x = desc_x + w_desc
        
        # Simulation
        def simulate_chunk(text, font_style):
            nonlocal curr_x, num_lines
            pdf.set_font('Arial', font_style, 10)
            words = text.split()
            for word in words:
                word_w = pdf.get_string_width(word + " ")
                if curr_x + word_w > max_desc_x:
                    num_lines += 1
                    curr_x = desc_x
                curr_x += word_w

        if desc_bold: simulate_chunk(desc_bold, 'B')
        if desc_normal: simulate_chunk(desc_normal, '')
        
        row_height = max(8, num_lines * h_line + 2)
        
        if start_y + row_height > 275: 
            pdf.add_page()
            start_y = pdf.get_y()
            start_x = 10 
        
        # Draw Borders
        pdf.set_xy(start_x, start_y)
        pdf.cell(w_item, row_height, str(item), 1, 0, 'C')
        pdf.cell(w_cat, row_height, category, 1, 0, 'L')
        
        pdf.set_xy(desc_x, start_y)
        pdf.cell(w_desc, row_height, "", 1, 0)
        
        draw_description_cell(desc_x + 1, start_y + 1, w_desc - 2, desc_bold, desc_normal)
        
        pdf.set_xy(desc_x + w_desc, start_y)
        pdf.cell(w_hrs, row_height, f"{hours:.1f}", 1, 1, 'C')
        
        # Next Row
        pdf.set_y(start_y + row_height)
        
        total_hours += hours

    # --- TOTALS ---
    pdf.ln(2) 
    pdf.set_font('Arial', 'B', 10)
    # Use sum of widths minus Hours col for label alignment
    label_w = w_item + w_cat + w_desc
    pdf.cell(label_w, 8, "Total Hours", 0, 0, 'R') 
    pdf.cell(w_hrs, 8, f"{total_hours:.1f}", 1, 1, 'C') 

    pdf.ln(8)
    amount = total_hours * 80
    pdf.cell(label_w, 8, "Total Cost (@ $80/hr)", 0, 0, 'R')
    pdf.cell(w_hrs, 8, f"${amount:,.2f}", 1, 1, 'C')

    # --- FOOTER ---
    pdf.ln(15)
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(0, 6, "BANK DEPOSIT DETAILS", 0, 1)
    
    print_field("Account Name:", "Aniruddha Borse")
    print_field("Bank Name:", "Westpac")
    print_field("Account No.:", "670075")
    print_field("BSB:", "033226")
    
    pdf.ln(5)
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(0, 6, "PAYMENT TERMS 15 DAYS", 0, 1)
    
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(10, 6, "Note:", 0, 0)
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 6, " If payment not received within 15 days of invoice further charges may be incurred.", 0, 1)

    # Output Filename logic
    # Filename format: Invoice_{invoice_num}.pdf
    
    output_filename = f"Invoice_{invoice_num}.pdf"
    output_path = f"d:/anirudh_kahn/adi_version/{output_filename}"
    
    pdf.output(output_path)
    print(f"PDF Generated: {output_path}")

if __name__ == '__main__':
    # Input Invoice Number
    inv_num = input("Enter Invoice Number (e.g. 2026_004): ").strip()
    if not inv_num:
        inv_num = "2026_004" # Default
    
    create_invoice(inv_num)
