# server.py - Backend API for dynamic watermarking (Python/Flask)
from flask import Flask, request, jsonify
from io import BytesIO
import base64
import os
import math # Needed for rotation calculation

# Libraries for Watermarking
from PIL import Image, ImageDraw, ImageFont # For Images
from PyPDF2 import PdfReader, PdfWriter # For PDFs
from reportlab.pdfgen import canvas # For creating PDF watermarks
from reportlab.lib.pagesizes import A4 # Use standard page sizes

# Initialize Flask App
app = Flask(__name__)

# --- Configuration ---
from flask_cors import CORS
CORS(app) 
# ---------------------

# --- Helper Functions ---

# Function to apply watermark to Images (JPEG, PNG) using Pillow (FIXED FOR DIAGONAL DENSITY)
def watermark_image(binary_data, text, alignment='diagonal'):
    try:
        # 1. Open the original image
        img = Image.open(BytesIO(binary_data)).convert("RGBA")
        width, height = img.size
        
        # Determine font size relative to image size for consistency (larger than PDF for visibility)
        font_size = int(width / 15) 
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except IOError:
            font = ImageFont.load_default() 
        
        text_width, text_height = ImageDraw.Draw(Image.new('RGBA', (1,1))).textbbox((0, 0), text, font=font)[2:]
        
        # --- Apply Diagonal Tiling (to match PDF logic) ---
        if alignment == 'diagonal':
            
            # 2. Create a transparent layer (same size as the image)
            watermark_layer = Image.new('RGBA', (width, height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(watermark_layer)
            
            # 3. Define Watermark properties (semi-transparent gray/white)
            fill_color = (128, 128, 128, 70) # Light gray, 70 opacity (0-255)
            spacing_factor = 2.5 # How many times the text height to leave as vertical space
            
            # 4. Calculate repetition necessary to cover the diagonal area
            # We need to loop vertically and horizontally over the image area
            
            # Vertical step size (space between diagonal lines)
            y_step = int(text_height * spacing_factor) 
            
            # Since the image is rotated later, we use the diagonal length of the image
            # to determine the loop range needed for full coverage.
            diag_length = math.sqrt(width**2 + height**2)
            
            # Vertical position (y_start) offset to cover the image from corner to corner
            y_start_offset = -int(diag_length / 2) 

            # Loop to draw diagonal lines
            y = y_start_offset
            while y < diag_length:
                # Loop horizontally along the rotated line
                x = 0
                while x < diag_length + width: # Ensure horizontal coverage
                    # Draw text
                    draw.text((x, y), text, font=font, fill=fill_color)
                    x += text_width + 150 # Horizontal spacing
                y += y_step
            
            # 5. Rotate the pattern layer (45 degrees counter-clockwise)
            watermark_layer = watermark_layer.rotate(45, expand=1, resample=Image.Resampling.BILINEAR)

            # 6. Center the rotated layer over the original image
            # Calculate offset to center the rotated image back over the original
            final_watermark = Image.new('RGBA', img.size, (0, 0, 0, 0))
            
            # Offset = (Rotated_Width - Original_Width) / 2
            offset_x = (watermark_layer.width - width) // 2
            offset_y = (watermark_layer.height - height) // 2
            
            # Paste the rotated layer onto the final layer
            final_watermark.paste(watermark_layer, (-offset_x, -offset_y), watermark_layer)
            
            # 7. Merge the final watermark layer onto the original image
            img = Image.alpha_composite(img, final_watermark)
            
        else:
             # --- Apply Static Alignment (Center/Bottom_Right) ---
             # This block uses the original static code for non-diagonal alignment
            drawing = ImageDraw.Draw(img)
            
            if alignment == 'center':
                x = (width - text_width) // 2
                y = (height - text_height) // 2
            elif alignment == 'bottom_right':
                x = width - text_width - (width // 20)
                y = height - text_height - (height // 20)
            else: # Default
                x = width // 20
                y = height - text_height - (height // 20)

            # Draw static text
            drawing.text((x + 2, y + 2), text, font=font, fill=(0, 0, 0, 100)) 
            drawing.text((x, y), text, font=font, fill=(255, 255, 255, 180)) 
        
        # 8. Save the modified image to a buffer
        output = BytesIO()
        img = img.convert("RGB") # Convert to RGB before saving final output (for JPEG/standard formats)
        img.save(output, format='JPEG') # Saving as JPEG standard
        output.seek(0)
        return output.read()
        
    except Exception as e:
        print(f"Image Watermarking Error: {e}")
        # Return original data on failure to prevent total crash
        return binary_data 

# Function to apply watermark to PDFs using ReportLab and PyPDF2 
def watermark_pdf(binary_data, text, alignment='diagonal'):
    # NOTE: PDF logic is kept as the previous working and fixed version
    try:
        # 1. Create the watermark PDF
        watermark_buffer = BytesIO()
        c = canvas.Canvas(watermark_buffer, pagesize=A4) 
        
        c.setFillColorRGB(0.5, 0.5, 0.5, alpha=0.2) # Grey, 20% opacity
        font_size = 24
        c.setFont("Helvetica-Bold", font_size)
        
        width, height = A4 
        center_x = width / 2
        center_y = height / 2

        if alignment == 'diagonal':
            # --- FIX: CALCULATE DENSE DIAGONAL PATTERN ---
            c.rotate(45) 
            c.translate(center_x, center_y) 

            spacing = 100 
            diag_span = 1000 
            
            for y_pos in range(-diag_span, diag_span, spacing):
                for x_pos in range(-diag_span, diag_span, 300):
                    c.drawString(x_pos, y_pos, text)
            
        elif alignment == 'bottom_right':
            c.translate(width - 250, 50) 
            c.rotate(0)
            c.drawString(0, 0, text)
            
        elif alignment == 'center':
            c.translate(center_x - 100, center_y) 
            c.rotate(0)
            c.drawString(0, 0, text)
            
        else: # Default diagonal
            c.rotate(45) 
            c.translate(center_x, center_y) 
            spacing = 100
            diag_span = 1000 
            for y_pos in range(-diag_span, diag_span, spacing):
                for x_pos in range(-diag_span, diag_span, 300):
                    c.drawString(x_pos, y_pos, text)


        c.save()
        watermark_buffer.seek(0)
        watermark_pdf = PdfReader(watermark_buffer)

        # 2. Merge the watermark into the original PDF
        original_pdf = PdfReader(BytesIO(binary_data))
        writer = PdfWriter()

        for page_num in range(len(original_pdf.pages)):
            page = original_pdf.pages[page_num]
            watermark_page = watermark_pdf.pages[0]
            
            page.merge_page(watermark_page)
            writer.add_page(page)

        # 3. Save the modified PDF to an output buffer
        output_buffer = BytesIO()
        writer.write(output_buffer)
        output_buffer.seek(0)
        return output_buffer.read()
        
    except Exception as e:
        print(f"PDF Watermarking Error: {e}")
        raise

# --- API Endpoint (Rest of file is unchanged) ---

@app.route('/api/watermark_file', methods=['POST'])
def watermark_file():
    data = request.get_json()
    
    if not data or 'document_base64' not in data:
        return jsonify({'error': 'Missing data fields'}), 400

    try:
        base64_data = data['document_base64']
        file_type = data['file_type']
        watermark_text = data['watermark_text']
        alignment = data.get('alignment', 'diagonal')
        
        binary_data = base64.b64decode(base64_data)
        modified_binary_data = None

        if 'image' in file_type:
            modified_binary_data = watermark_image(binary_data, watermark_text, alignment)
        elif 'pdf' in file_type:
            modified_binary_data = watermark_pdf(binary_data, watermark_text, alignment)
        else:
            return jsonify({'error': f'Unsupported file type: {file_type}'}), 400

        if modified_binary_data:
            watermarked_base64 = base64.b64encode(modified_binary_data).decode('utf-8')
            return jsonify({'watermarked_base64': watermarked_base64})
        
        return jsonify({'error': 'Processing failed: Output is empty.'}), 500

    except Exception as e:
        print(f"API Processing Error: {e}")
        return jsonify({'error': f'Server failed to process the file: {e}'}), 500

if __name__ == '__main__':
    print("Starting Watermark API on http://127.0.0.1:5000")
    app.run(host='0.0.0.0', port=5000)