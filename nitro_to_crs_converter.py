#!/usr/bin/env python3
"""
Convert Nitro XMP crop settings to Adobe Lightroom CRS format.
"""

import xml.etree.ElementTree as ET
import html
import plistlib
import json
import sys
import os
from pathlib import Path
from datetime import datetime


class NitroToCRSConverter:
    def __init__(self):
        self.crs_namespace = "http://ns.adobe.com/camera-raw-settings/1.0/"
        
    def extract_plist_from_xmp(self, xmp_file_path):
        """
        Extract and decode the macOS plist from the nitro:EditModel tag in an XMP file.
        
        Args:
            xmp_file_path (str): Path to the XMP file
            
        Returns:
            dict: Decoded plist as a Python dictionary with parsed JSON editModel
        """
        try:
            # Parse the XMP file
            tree = ET.parse(xmp_file_path)
            root = tree.getroot()
            
            # Define namespace map
            namespaces = {
                'nitro': 'http://com.gentlemencoders/xmp/nitro/1.0/',
                'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
                'x': 'adobe:ns:meta/'
            }
            
            # Find the nitro:EditModel element
            edit_model_elem = root.find('.//nitro:EditModel', namespaces)
            
            if edit_model_elem is None:
                return None  # No nitro edit model found
            
            # Get the encoded plist content
            encoded_plist = edit_model_elem.text
            
            if not encoded_plist:
                return None
            
            # Decode HTML entities
            decoded_plist = html.unescape(encoded_plist)
            
            # Parse the plist
            plist_data = plistlib.loads(decoded_plist.encode('utf-8'))
            
            # Parse the JSON object in the "editModel" key if it exists
            if 'editModel' in plist_data and isinstance(plist_data['editModel'], str):
                try:
                    plist_data['editModel'] = json.loads(plist_data['editModel'])
                except json.JSONDecodeError as e:
                    print(f"Warning: Failed to parse editModel as JSON: {e}")
            
            return plist_data
            
        except Exception as e:
            print(f"Error processing {xmp_file_path}: {e}")
            return None

    def parse_size_string(self, size_str):
        """
        Parse a string of the form "{width, height}" and extract width, height as integers.
        
        Args:
            size_str (str): Size string in format "{width, height}"
            
        Returns:
            tuple: (width, height) or None if parsing fails
        """
        try:
            size_parts = size_str.strip("{}").split(", ")
            if len(size_parts) != 2:
                return None
            return int(size_parts[0]), int(size_parts[1])
        except (ValueError, IndexError):
            return None

    def nitro_crop_to_crs(self, crop_data, original_width, original_height):
        """
        Convert Nitro's crop data to Adobe CRS format.
        
        Nitro cropRect format: [[x1, y1], [x2, y2]] where:
        - (x1, y1) is the lower-left corner
        - (x2, y2) is the upper-right corner
        
        Adobe CRS format uses normalized coordinates (0-1) with:
        - CropLeft: left edge
        - CropTop: top edge  
        - CropRight: right edge
        - CropBottom: bottom edge
        - CropAngle: rotation in degrees
        - HasCrop: boolean indicating if crop is applied
        
        Args:
            crop_data (dict): Parsed JSON from Nitro's crop adjustment
            original_width (int): Original image width in pixels
            original_height (int): Original image height in pixels
            
        Returns:
            dict: CRS crop properties
        """
        try:
            # Parse crop data if it's a JSON string
            if isinstance(crop_data, str):
                crop_json = json.loads(crop_data)
            else:
                crop_json = crop_data
            
            # Extract crop rectangle
            crop_rect = crop_json.get('cropRect')
            if not crop_rect or len(crop_rect) != 2:
                return {}
            
            # Get corner coordinates
            x1, y1 = crop_rect[0]  # lower-left
            x2, y2 = crop_rect[1]  # upper-right
            
            # Convert to normalized coordinates (0-1)
            # Note: Nitro uses bottom-left origin, Adobe uses top-left
            # So we need to flip the Y coordinates
            crop_left = x1 / original_width
            crop_right = x2 / original_width
            crop_bottom = (original_height - y2) / original_height  # Flip Y
            crop_top = (original_height - y1) / original_height     # Flip Y
            
            # Get rotation/straighten angle
            straighten = crop_json.get('numeric', {}).get('straighten', 0)
            
            # Build CRS properties
            crs_crop = {
                'crs:CropLeft': crop_left,
                'crs:CropTop': crop_bottom,
                'crs:CropRight': crop_right,
                'crs:CropBottom': crop_top,
                'crs:CropAngle': straighten,
                'crs:HasCrop': True
            }
            
            # Add aspect ratio constraint if available
            if crop_json.get('aspectRatioType') == 3:  # Custom aspect ratio
                aspect_width = crop_json.get('aspectWidth')
                aspect_height = crop_json.get('aspectHeight')
                if aspect_width and aspect_height:
                    crs_crop['crs:CropConstrainToWarp'] = False
            
            return crs_crop
            
        except Exception as e:
            print(f"Error converting crop data: {e}")
            return {}

    def create_adobe_xmp(self, original_xmp_path, crs_crop_data):
        """
        Create a new XMP file with Adobe CRS crop settings.
        
        Args:
            original_xmp_path (str): Path to the original XMP file
            crs_crop_data (dict): CRS crop properties
            
        Returns:
            str: XML content for the new XMP file
        """
        # Create the XMP structure
        xmp_template = '''<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="XMP Core 5.5.0">
   <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
      <rdf:Description rdf:about=""
            xmlns:xmp="http://ns.adobe.com/xap/1.0/"
            xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/">
         <xmp:CreatorTool>Nitro to CRS Converter</xmp:CreatorTool>
         <xmp:MetadataDate>{metadata_date}</xmp:MetadataDate>
{crs_properties}
      </rdf:Description>
   </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>'''

        # Format CRS properties
        crs_props = []
        for key, value in crs_crop_data.items():
            if isinstance(value, bool):
                crs_props.append(f'         <{key}>{str(value).lower()}</{key}>')
            elif isinstance(value, (int, float)):
                crs_props.append(f'         <{key}>{value}</{key}>')
            else:
                crs_props.append(f'         <{key}>{value}</{key}>')
        
        # Generate current timestamp
        current_time = datetime.now().astimezone().isoformat()
        
        return xmp_template.format(
            metadata_date=current_time,
            crs_properties='\n'.join(crs_props)
        )

    def convert_file(self, input_path, output_dir):
        """
        Convert a single Nitro XMP file to Adobe CRS format.
        
        Args:
            input_path (str): Path to input XMP file
            output_dir (str): Directory to save converted file
            
        Returns:
            bool: True if conversion successful, False otherwise
        """
        try:
            # Extract plist data
            plist_data = self.extract_plist_from_xmp(input_path)
            if not plist_data:
                print(f"No Nitro edit model found in {input_path}")
                return False
            
            # Get original image dimensions
            original_size = plist_data.get('originalImagePixelSize')
            if not original_size:
                print(f"No originalImagePixelSize found in {input_path}")
                return False
            
            width, height = self.parse_size_string(original_size)
            if not width or not height:
                print(f"Invalid originalImagePixelSize format: {original_size}")
                return False
            
            # Look for crop data
            crs_crop_data = {}
            if 'editModel' in plist_data and 'versions' in plist_data['editModel']:
                for version in plist_data['editModel']['versions']:
                    if 'adjDataArr' in version:
                        for adj in version['adjDataArr']:
                            if adj['id'] == 'Crop':
                                crs_crop_data = self.nitro_crop_to_crs(
                                    adj['json'], width, height
                                )
                                break
            
            if not crs_crop_data:
                print(f"No crop data found in {input_path}")
                return False
            
            # Create output XMP content
            xmp_content = self.create_adobe_xmp(input_path, crs_crop_data)
            
            # Write to output file
            input_filename = Path(input_path).name
            output_path = Path(output_dir) / input_filename
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(xmp_content)
            
            print(f"Converted {input_filename} -> {output_path}")
            print(f"  Original size: {width}x{height}")
            print(f"  CRS crop: Left={crs_crop_data.get('crs:CropLeft', 0):.4f}, "
                  f"Top={crs_crop_data.get('crs:CropTop', 0):.4f}, "
                  f"Right={crs_crop_data.get('crs:CropRight', 1):.4f}, "
                  f"Bottom={crs_crop_data.get('crs:CropBottom', 1):.4f}")
            
            return True
            
        except Exception as e:
            print(f"Error converting {input_path}: {e}")
            return False

    def convert_directory(self, input_dir, output_dir):
        """
        Convert all XMP files in a directory from Nitro to CRS format.
        
        Args:
            input_dir (str): Input directory path
            output_dir (str): Output directory path
        """
        input_path = Path(input_dir)
        output_path = Path(output_dir)
        
        # Create output directory if it doesn't exist
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Find all XMP files
        xmp_files = list(input_path.glob("*.xmp"))
        
        if not xmp_files:
            print(f"No XMP files found in {input_dir}")
            return
        
        print(f"Found {len(xmp_files)} XMP files to process")
        
        successful = 0
        for xmp_file in xmp_files:
            if self.convert_file(str(xmp_file), str(output_path)):
                successful += 1
        
        print(f"\nConversion complete: {successful}/{len(xmp_files)} files converted successfully")


def main():
    if len(sys.argv) < 3:
        print("Usage:")
        print("  python nitro_to_crs_converter.py <input_file> <output_file>")
        print("  python nitro_to_crs_converter.py <input_dir> <output_dir>")
        sys.exit(1)
    
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    
    converter = NitroToCRSConverter()
    
    if os.path.isfile(input_path):
        # Convert single file
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        converter.convert_file(input_path, output_dir)
    elif os.path.isdir(input_path):
        # Convert directory
        converter.convert_directory(input_path, output_path)
    else:
        print(f"Error: {input_path} is not a valid file or directory")
        sys.exit(1)


if __name__ == "__main__":
    main()