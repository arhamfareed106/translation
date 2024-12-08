from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import pytesseract
from PIL import Image
from deep_translator import GoogleTranslator
import re
import os
import logging

app = Flask(__name__, static_folder='.')
CORS(app)

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize translator
translator = GoogleTranslator(source='ko', target='en')

def clean_text(text):
    """Clean and normalize text."""
    # Replace various types of separators with standard ones
    text = re.sub(r'[：\s]+', ' ', text)
    text = re.sub(r'\s*[:]\s*', ': ', text)
    text = re.sub(r'\s*[-]\s*', '-', text)
    return text.strip()

def extract_field(text, field_names, additional_patterns=None):
    """Extract a field using multiple pattern matching attempts."""
    if isinstance(field_names, str):
        field_names = [field_names]
    
    patterns = []
    for field_name in field_names:
        patterns.extend([
            rf"{field_name}\s*[:：-]\s*([^,.\n]+)",  # Standard format
            rf"{field_name}[^\n:：-]*[:：-]\s*([^,.\n]+)",  # More flexible format
            rf"{field_name}[^\n]*?([^,.\n]+)",  # Very flexible format
            rf"\b{field_name}\b[^\n]*?([^,.\n]+)"  # Word boundary format
        ])
    
    if additional_patterns:
        patterns.extend(additional_patterns)
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            if value and not value.isspace():
                logger.debug(f"Found match with pattern '{pattern}': {value}")
                return value
    
    logger.debug(f"No match found for patterns")
    return "Not found"

def extract_name(text):
    """Extract name using various patterns."""
    name_patterns = [
        r"name\s*[:：-]\s*([^,.\n]+)",
        r"성명\s*[:：-]\s*([^,.\n]+)",  # Korean for "name"
        r"이름\s*[:：-]\s*([^,.\n]+)",  # Alternative Korean for "name"
        r"\b[A-Z][a-z]+\s+[A-Z][a-z]+\b",  # Western name format
        r"[가-힣]+\s*[가-힣]+",  # Korean name format
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, text)
        if match:
            name = match.group(1) if '(' in pattern else match.group(0)
            return clean_text(name)
    return "Not found"

def extract_phone(text):
    """Extract phone number using various formats."""
    phone_patterns = [
        r"phone\s*[:：-]\s*(\d[\d\s\-\.]+\d)",
        r"전화\s*[:：-]\s*(\d[\d\s\-\.]+\d)",  # Korean for "phone"
        r"연락처\s*[:：-]\s*(\d[\d\s\-\.]+\d)",  # Alternative Korean for "contact"
        r"\b\d{2,4}[-.\s]?\d{3,4}[-.\s]?\d{4}\b",  # Standard phone format
        r"\b\d{10,11}\b"  # Just numbers
    ]
    
    for pattern in phone_patterns:
        match = re.search(pattern, text)
        if match:
            phone = match.group(1) if ':' in pattern else match.group(0)
            # Format phone number
            phone = re.sub(r'[\s\-\.]', '', phone)
            if len(phone) >= 10:
                return f"{phone[:3]}-{phone[3:7]}-{phone[7:]}"
    return "Not found"

def extract_address(text):
    """Extract address using various patterns."""
    address_patterns = [
        r"address\s*[:：-]\s*([^,.\n]+)",
        r"주소\s*[:：-]\s*([^,.\n]+)",  # Korean for "address"
        r"location\s*[:：-]\s*([^,.\n]+)",
        r"(?:street|road|ave|avenue)\s*[:：-]\s*([^,.\n]+)",
        r"\d+\s+[A-Za-z\s]+(?:street|road|ave|avenue)",
        r"\b\d{1,5}\s+[A-Za-z\s]+(?:street|road|ave|avenue|st|rd)",
        r"[A-Za-z0-9\s]+(?:street|road|ave|avenue|st|rd|lane|way)[,\s]+[A-Za-z\s]+[,\s]+[A-Z]{2}\s+\d{5}"
    ]
    
    for pattern in address_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            address = match.group(1) if ':' in pattern else match.group(0)
            return clean_text(address)
    
    # Try to find any location-like text
    location_indicators = [
        r"\b\d{1,5}\s+[A-Za-z\s]+\b",  # Basic street number + name
        r"[A-Za-z]+\s+(?:Building|Complex|Plaza|Tower)",
        r"(?:Apt|Suite|Unit|Room)\s*[#]?\s*\d+",
    ]
    
    for pattern in location_indicators:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return clean_text(match.group(0))
    
    return "Address information unavailable"

def extract_type(text):
    """Extract type of information."""
    type_patterns = [
        r"type\s*[:：-]\s*([^,.\n]+)",
        r"종류\s*[:：-]\s*([^,.\n]+)",  # Korean for "type"
        r"유형\s*[:：-]\s*([^,.\n]+)",  # Alternative Korean for "type"
        r"분류\s*[:：-]\s*([^,.\n]+)",  # Another Korean word for "classification"
    ]
    
    result = extract_field(text, ["type", "종류", "유형", "분류"], type_patterns)
    if result == "Not found":
        # Try to find any categorical words
        categories = re.findall(r'\b(?:document|certificate|license|permit|card|ID)\b', text, re.IGNORECASE)
        if categories:
            return categories[0].capitalize()
    return result

def parse_fields(text):
    """Parse specific fields dynamically from translated text."""
    logger.debug(f"Parsing text: {text}")
    text = clean_text(text)
    
    fields = {
        "Name": extract_name(text),
        "Phone": extract_phone(text),
        "Address": extract_address(text),
        "Type of Information": extract_type(text)
    }
    
    # Add any additional information found
    extra_info = []
    date_matches = re.findall(r'\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b', text)
    if date_matches:
        extra_info.append(f"Date found: {date_matches[0]}")
    
    email_matches = re.findall(r'\b[\w\.-]+@[\w\.-]+\.\w+\b', text)
    if email_matches:
        extra_info.append(f"Email found: {email_matches[0]}")
    
    if extra_info:
        fields["Additional Information"] = "; ".join(extra_info)
    
    return fields

def validate_contact_info(field_value, field_name):
    """Validate and provide appropriate defaults for contact information."""
    if not field_value or field_value == "Not found":
        if field_name == "name":
            return "Unknown"
        elif field_name == "phone":
            return "No phone number"
        elif field_name == "address":
            # Try to extract address if it's in the original text
            try:
                extracted_address = extract_address(field_value)
                if extracted_address != "Address information unavailable":
                    return extracted_address
            except Exception:
                pass
            return "Address pending verification"
        elif field_name == "type":
            return "General Contact"
    return field_value

def display_contact_details(name, phone, address, type_info):
    """Display contact details in a structured format with validation."""
    details = {
        "Name": validate_contact_info(name, "name"),
        "Phone": validate_contact_info(phone, "phone"),
        "Address": validate_contact_info(address, "address"),
        "Type": validate_contact_info(type_info, "type")
    }
    
    formatted_details = []
    for key, value in details.items():
        formatted_details.append(f"{key}: {value}")
    
    return "\n".join(formatted_details)

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

@app.route('/process', methods=['POST'])
def process_image():
    if 'image' not in request.files:
        return jsonify({'error': 'No image provided'}), 400
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    try:
        # Read the image
        image = Image.open(file)
        
        # Perform OCR with additional configurations
        original_text = pytesseract.image_to_string(
            image,
            lang='kor+eng',  # Support both Korean and English
            config='--psm 3 --oem 3'  # Page segmentation mode 3 and OCR Engine Mode 3
        )
        
        logger.debug(f"Original text from OCR: {original_text}")
        
        # Translate text
        try:
            translated_text = translator.translate(text=original_text if original_text.strip() else "No text detected")
            logger.debug(f"Translated text: {translated_text}")
        except Exception as e:
            logger.error(f"Translation error: {str(e)}")
            translated_text = f"Translation error: {str(e)}"
        
        # Parse fields
        fields = parse_fields(translated_text)
        
        # Also try parsing the original text for better accuracy
        original_fields = parse_fields(original_text)
        
        # Merge results, preferring non-"Not found" values
        for key in fields:
            if fields[key] == "Not found" and original_fields.get(key, "Not found") != "Not found":
                fields[key] = original_fields[key]
        
        response_data = {
            'original_text': original_text,
            'translated_text': translated_text,
            'parsed_fields': fields
        }
        logger.debug(f"Response data: {response_data}")
        
        return jsonify(response_data)
    
    except Exception as e:
        logger.error(f"Processing error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/contact', methods=['POST'])
def process_contact():
    data = request.json
    name = data.get('name', '').strip()
    phone = data.get('phone', '').strip()
    address = data.get('address', '').strip()
    type_info = data.get('type', '').strip()
    
    result = display_contact_details(name, phone, address, type_info)
    return jsonify({
        "result": result,
        "status": "success",
        "message": "Contact information processed successfully"
    })

if __name__ == '__main__':
    app.run(debug=True)
