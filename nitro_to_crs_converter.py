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
import math

from pathlib import Path
from datetime import datetime
from crop_calc import CropRect, Point


class NitroToCRSConverter:
    def __init__(self, debug: bool | None = None):
        self.crs_namespace = "http://ns.adobe.com/camera-raw-settings/1.0/"
        # Verbose debug logging can be enabled via ctor or env var
        env_dbg = os.environ.get("NITRO_DEBUG_CROP") or os.environ.get("NITRO_DEBUG")
        self.debug = bool(debug) if debug is not None else bool(env_dbg)
        self.orientation = 1  # Default orientation
        
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
        
        Nitro cropRect format: [[x1, y1], [width, height]] where:
        - (x1, y1) is the lower-left corner
        
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

            # Get rotation/straighten angle
            straighten = crop_json.get('numeric', {}).get('straighten', 0)

            # Get corner coordinates and desired edited size (Nitro semantics: lower-left, final width/height)
            x1, y1 = crop_rect[0]  # lower-left in pixels (Nitro uses bottom-left origin)
            w, h = crop_rect[1]    # final edited pixel width/height of the image after rotation

            if x1 == 0 and y1 == 0 and w == 0 and h == 0:
                # Special rotation-only case
                transformer = CropRect([[x1, y1], [original_width, original_height]])
            else:
                transformer = CropRect(crop_rect)
            
            return transformer.crop_factors(straighten, original_width, original_height)            
        except Exception as e:
            print(f"Error converting crop data: {e}")
            return {}

    def maybe_rotate_crop(self, crs_crop_data):
        if self.orientation == 8:
            print(f"Rotating crop for portrait orientation {self.orientation}")
            cl = crs_crop_data.get('crs:CropLeft', 0.0)
            ct = crs_crop_data.get('crs:CropTop', 0.0)
            cr = crs_crop_data.get('crs:CropRight', 1.0)
            cb = crs_crop_data.get('crs:CropBottom', 1.0)

            crs_crop_data['crs:CropLeft'] = 1.0 - cb
            crs_crop_data['crs:CropTop'] = cl
            crs_crop_data['crs:CropRight'] = 1.0 - ct
            crs_crop_data['crs:CropBottom'] = cr
        return crs_crop_data

    def update_adobe_xmp(self, adobe_xmp_path, crs_crop_data):
        """
        Update an existing Adobe XMP file with CRS crop settings.
        
        Args:
            adobe_xmp_path (str): Path to the existing Adobe XMP file to update
            crs_crop_data (dict): CRS crop properties
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Read the current XMP file
            with open(adobe_xmp_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Update CRS crop properties using string replacement
            import re
            
            for prop_name, prop_value in crs_crop_data.items():
                # Convert values to strings
                if isinstance(prop_value, bool):
                    value_str = str(prop_value)
                elif isinstance(prop_value, (int, float)):
                    if isinstance(prop_value, float):
                        value_str = f"{prop_value:.6f}"
                    else:
                        value_str = str(prop_value)
                else:
                    value_str = str(prop_value)
                
                # Look for existing property and replace it
                pattern = rf'{re.escape(prop_name)}="[^"]*"'
                replacement = f'{prop_name}="{value_str}"'
                
                if re.search(pattern, content):
                    # Replace existing property
                    content = re.sub(pattern, replacement, content)
                else:
                    # Add new property - find a good place to insert it
                    # Look for other crs: properties and add near them
                    crs_pattern = r'(crs:[^=]+="[^"]*"\n)'
                    matches = list(re.finditer(crs_pattern, content))
                    if matches:
                        # Insert after the last crs: property
                        last_match = matches[-1]
                        insert_pos = last_match.end()
                        # Match the indentation of the previous line
                        prev_line_start = content.rfind('\n', 0, last_match.start()) + 1
                        prev_line = content[prev_line_start:last_match.start()]
                        indent = len(prev_line) - len(prev_line.lstrip())
                        new_line = ' ' * indent + f'{prop_name}="{value_str}"\n'
                        content = content[:insert_pos] + new_line + content[insert_pos:]
            
            # Write the updated content back to the file
            with open(adobe_xmp_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return True
            
        except Exception as e:
            print(f"Error updating {adobe_xmp_path}: {e}")
            return False

    def convert_file(self, nitro_path, adobe_path):
        """
        Convert crop settings from a Nitro XMP file and update the corresponding Adobe XMP file.
        
        Args:
            nitro_path (str): Path to Nitro XMP file
            adobe_path (str): Path to Adobe XMP file to update
            
        Returns:
            bool: True if conversion successful, False otherwise
        """
        try:
            # Extract plist data from Nitro file
            plist_data = self.extract_plist_from_xmp(nitro_path)
            if not plist_data:
                print(f"No Nitro edit model found in {nitro_path}")
                return False
            
            # Get original image dimensions
            original_size = plist_data.get('originalImagePixelSize')
            if not original_size:
                print(f"No originalImagePixelSize found in {nitro_path}")
                return False
            
            width, height = self.parse_size_string(original_size)
            if not width or not height:
                print(f"Invalid originalImagePixelSize format: {original_size}")
                return False
            
            # Look for a portrait orientation
            if 'editModel' in plist_data and 'defaultOrientation' in plist_data['editModel']:
                self.orientation = plist_data['editModel']['defaultOrientation']
            
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
                print(f"No crop data found in {nitro_path}")
                return False
            
            self.maybe_rotate_crop(crs_crop_data)
            
            # Check if Adobe XMP file exists
            if not os.path.exists(adobe_path):
                print(f"Adobe XMP file not found: {adobe_path}")
                return False
            
            # Update the existing Adobe XMP file
            if self.update_adobe_xmp(adobe_path, crs_crop_data):
                print(f"Updated {Path(adobe_path).name} with crop settings from {Path(nitro_path).name}")
                print(f"  Original size: {width}x{height}")
                print(f"  Rotation angle: {crs_crop_data.get('crs:CropAngle', 0):.8f}")
                print(f"  CRS crop: Left={crs_crop_data.get('crs:CropLeft', 0):.4f}, "
                      f"Top={crs_crop_data.get('crs:CropTop', 0):.4f}, "
                      f"Right={crs_crop_data.get('crs:CropRight', 1):.4f}, "
                      f"Bottom={crs_crop_data.get('crs:CropBottom', 1):.4f}")
                return True
            else:
                print(f"Failed to update {adobe_path}")
                return False
            
        except Exception as e:
            print(f"Error converting {nitro_path}: {e}")
            return False

    def pretty_print_editmodel(self, nitro_path):
        """
        Pretty-print the contents of the nitro:EditModel plist from an XMP file.
        
        Args:
            nitro_path (str): Path to Nitro XMP file
        """
        try:
            plist_data = self.extract_plist_from_xmp(nitro_path)
            if not plist_data:
                print(f"No Nitro edit model found in {nitro_path}")
                return
            
            print(f"\n=== Nitro EditModel Contents: {Path(nitro_path).name} ===")
            
            # Print top-level plist keys
            print("\nTop-level plist keys:")
            for key, value in plist_data.items():
                if key == 'editModel':
                    print(f"  {key}: <parsed JSON object>")
                else:
                    print(f"  {key}: {value}")
            
            # Print editModel JSON structure if present
            if 'editModel' in plist_data and isinstance(plist_data['editModel'], dict):
                edit_model = plist_data['editModel']
                print(f"\nEditModel JSON structure:")
                print(f"  formatVersion: {edit_model.get('formatVersion')}")
                print(f"  defaultOrientation: {edit_model.get('defaultOrientation')}")
                print(f"  currentVersionIndex: {edit_model.get('currentVersionIndex')}")
                print(f"  editingJPEGHalf: {edit_model.get('editingJPEGHalf')}")
                print(f"  lowResMask: {edit_model.get('lowResMask')}")
                
                versions = edit_model.get('versions', [])
                print(f"  versions: {len(versions)} version(s)")
                
                for i, version in enumerate(versions):
                    print(f"\n  Version {i}:")
                    adj_data_arr = version.get('adjDataArr', [])
                    masks = version.get('masks', [])
                    print(f"    adjDataArr: {len(adj_data_arr)} adjustment(s)")
                    print(f"    masks: {len(masks)} mask(s)")
                    
                    for j, adj in enumerate(adj_data_arr):
                        adj_id = adj.get('id', 'Unknown')
                        print(f"      Adjustment {j}: {adj_id}")
                        
                        if adj_id == 'Crop' and 'json' in adj:
                            try:
                                crop_data = json.loads(adj['json'])
                                print(f"        Crop details:")
                                print(f"          enabled: {crop_data.get('enabled')}")
                                print(f"          disclosed: {crop_data.get('disclosed')}")
                                print(f"          cropRect: {crop_data.get('cropRect')}")
                                print(f"          aspectRatioType: {crop_data.get('aspectRatioType')}")
                                print(f"          aspectWidth: {crop_data.get('aspectWidth')}")
                                print(f"          aspectHeight: {crop_data.get('aspectHeight')}")
                                print(f"          orientationIsRelative: {crop_data.get('orientationIsRelative')}")
                                
                                numeric = crop_data.get('numeric', {})
                                if numeric:
                                    print(f"          numeric:")
                                    for key, val in numeric.items():
                                        print(f"            {key}: {val}")
                            except json.JSONDecodeError as e:
                                print(f"        Error parsing crop JSON: {e}")
            
            print("\n" + "="*60)
            
        except Exception as e:
            print(f"Error reading {nitro_path}: {e}")

    def convert_directory(self, nitro_dir, adobe_dir):
        """
        Convert all XMP files from Nitro directory and update corresponding files in Adobe directory.
        
        Args:
            nitro_dir (str): Nitro XMP files directory path
            adobe_dir (str): Adobe XMP files directory path
        """
        nitro_path = Path(nitro_dir)
        adobe_path = Path(adobe_dir)
        
        if not adobe_path.exists():
            print(f"Adobe directory '{adobe_dir}' not found")
            return
        
        # Find all XMP files in Nitro directory
        nitro_files = sorted(nitro_path.glob("*.xmp"))
        
        if not nitro_files:
            print(f"No XMP files found in {nitro_dir}")
            return
        
        print(f"Found {len(nitro_files)} Nitro XMP files to process")
        
        successful = 0
        for nitro_file in nitro_files:
            # Find corresponding Adobe XMP file
            adobe_file = adobe_path / nitro_file.name
            
            if adobe_file.exists():
                if self.convert_file(str(nitro_file), str(adobe_file)):
                    successful += 1
            else:
                print(f"Adobe XMP file not found for {nitro_file.name}, skipping...")
        
        print(f"\nConversion complete: {successful}/{len(nitro_files)} files updated successfully")


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python nitro_to_crs_converter.py <nitro_file>                    # Pretty-print editModel contents")
        print("  python nitro_to_crs_converter.py <nitro_dir>                     # Pretty-print all editModel contents")  
        print("  python nitro_to_crs_converter.py <nitro_file> <adobe_file>       # Update single Adobe XMP file")
        print("  python nitro_to_crs_converter.py <nitro_dir> <adobe_dir>         # Update Adobe XMP directory")
        print("")
        print("This script can either inspect Nitro XMP files or update existing Adobe XMP files with crop settings.")
        sys.exit(1)
    
    nitro_path = sys.argv[1]
    converter = NitroToCRSConverter()
    
    # If only one argument provided, pretty-print the editModel contents
    if len(sys.argv) == 2:
        if os.path.isfile(nitro_path):
            # Pretty-print single file
            converter.pretty_print_editmodel(nitro_path)
        elif os.path.isdir(nitro_path):
            # Pretty-print all files in directory
            nitro_dir = Path(nitro_path)
            nitro_files = sorted(nitro_dir.glob("*.xmp"))
            
            if not nitro_files:
                print(f"No XMP files found in {nitro_path}")
                return
            
            print(f"Found {len(nitro_files)} Nitro XMP files")
            
            for nitro_file in nitro_files:
                converter.pretty_print_editmodel(str(nitro_file))
        else:
            print(f"Error: {nitro_path} is not a valid file or directory")
            sys.exit(1)
        return
    
    # Two arguments provided - conversion mode
    adobe_path = sys.argv[2]
    
    if os.path.isfile(nitro_path) and os.path.isfile(adobe_path):
        # Convert single file pair
        converter.convert_file(nitro_path, adobe_path)
    elif os.path.isdir(nitro_path) and os.path.isdir(adobe_path):
        # Convert directories
        converter.convert_directory(nitro_path, adobe_path)
    else:
        print(f"Error: Both paths must be either files or directories")
        print(f"  Nitro path: {nitro_path} ({'file' if os.path.isfile(nitro_path) else 'directory' if os.path.isdir(nitro_path) else 'not found'})")
        print(f"  Adobe path: {adobe_path} ({'file' if os.path.isfile(adobe_path) else 'directory' if os.path.isdir(adobe_path) else 'not found'})")
        sys.exit(1)


if __name__ == "__main__":
    main()