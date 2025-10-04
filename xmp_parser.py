#!/usr/bin/env python3
"""
XMP (Extensible Metadata Platform) Parser Module

This module provides utilities for parsing and extracting metadata from XMP files,
specifically for handling both Nitro and Adobe Lightroom XMP formats.

XMP is an ISO standard (ISO 16684-1) for embedding metadata in files using RDF/XML.
This parser focuses on extracting camera raw settings, crop information, and other
photographic metadata commonly used in RAW image processing workflows.
"""

import xml.etree.ElementTree as ET
import html
import plistlib
import json
import re
from typing import Dict, List, Optional, Union, Any, Tuple
from pathlib import Path
from dataclasses import dataclass
from enum import Enum


class XMPSource(Enum):
    """Enumeration of XMP file sources/creators."""
    NITRO = "nitro"
    ADOBE = "adobe"
    UNKNOWN = "unknown"


@dataclass
class CropData:
    """Container for normalized crop data."""
    left: float
    top: float 
    right: float
    bottom: float
    angle: float
    has_crop: bool
    aspect_width: Optional[int] = None
    aspect_height: Optional[int] = None
    
    def __post_init__(self):
        """Validate crop data after initialization."""
        if not (0 <= self.left <= 1 and 0 <= self.top <= 1 and 
                0 <= self.right <= 1 and 0 <= self.bottom <= 1):
            raise ValueError("Crop coordinates must be normalized between 0 and 1")
        if self.left >= self.right or self.top >= self.bottom:
            raise ValueError("Invalid crop rectangle: left >= right or top >= bottom")


@dataclass
class ImageSize:
    """Container for image dimensions."""
    width: int
    height: int
    
    def __str__(self) -> str:
        return f"{self.width}x{self.height}"
    
    @classmethod
    def from_string(cls, size_str: str) -> Optional['ImageSize']:
        """Parse size from string format like '{6960, 4640}' or '6960x4640'."""
        # Handle curly brace format: {width, height}
        if size_str.startswith('{') and size_str.endswith('}'):
            try:
                parts = size_str.strip("{}").split(", ")
                if len(parts) == 2:
                    return cls(int(parts[0]), int(parts[1]))
            except (ValueError, IndexError):
                pass
        
        # Handle dimension format: widthxheight
        if 'x' in size_str:
            try:
                parts = size_str.split('x')
                if len(parts) == 2:
                    return cls(int(parts[0]), int(parts[1]))
            except (ValueError, IndexError):
                pass
                
        return None


@dataclass
class CameraSettings:
    """Container for camera/EXIF data extracted from XMP."""
    make: Optional[str] = None
    model: Optional[str] = None
    lens: Optional[str] = None
    focal_length: Optional[float] = None
    aperture: Optional[str] = None
    shutter_speed: Optional[str] = None
    iso: Optional[int] = None
    exposure_bias: Optional[str] = None
    date_taken: Optional[str] = None
    orientation: Optional[int] = None


@dataclass
class ProcessingSettings:
    """Container for image processing settings."""
    exposure: Optional[float] = None
    contrast: Optional[int] = None
    highlights: Optional[int] = None
    shadows: Optional[int] = None
    whites: Optional[int] = None
    blacks: Optional[int] = None
    clarity: Optional[int] = None
    vibrance: Optional[int] = None
    saturation: Optional[int] = None
    white_balance: Optional[str] = None


class XMPParser:
    """
    A comprehensive parser for XMP metadata files.
    
    This parser can handle XMP files from different sources including:
    - Nitro (with embedded plist data)
    - Adobe Lightroom/Camera Raw
    - Generic XMP files
    """
    
    # Common XMP namespaces
    NAMESPACES = {
        'x': 'adobe:ns:meta/',
        'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
        'xmp': 'http://ns.adobe.com/xap/1.0/',
        'nitro': 'http://com.gentlemencoders/xmp/nitro/1.0/',
        'tiff': 'http://ns.adobe.com/tiff/1.0/',
        'exif': 'http://ns.adobe.com/exif/1.0/',
        'aux': 'http://ns.adobe.com/exif/1.0/aux/',
        'photoshop': 'http://ns.adobe.com/photoshop/1.0/',
        'dc': 'http://purl.org/dc/elements/1.1/',
        'xmpMM': 'http://ns.adobe.com/xap/1.0/mm/',
        'crd': 'http://ns.adobe.com/camera-raw-defaults/1.0/',
        'crs': 'http://ns.adobe.com/camera-raw-settings/1.0/',
    }
    
    def __init__(self, debug: bool = False):
        """
        Initialize the XMP parser.
        
        Args:
            debug: Enable debug logging
        """
        self.debug = debug
        self._tree: Optional[ET.ElementTree] = None
        self._root: Optional[ET.Element] = None
        
    def parse_file(self, xmp_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Parse an XMP file and extract all available metadata.
        
        Args:
            xmp_path: Path to the XMP file
            
        Returns:
            Dictionary containing all extracted metadata
        """
        xmp_path = Path(xmp_path)
        
        if not xmp_path.exists():
            raise FileNotFoundError(f"XMP file not found: {xmp_path}")
            
        try:
            self._tree = ET.parse(xmp_path)
            self._root = self._tree.getroot()
            
            # Extract metadata
            result = {
                'file_path': str(xmp_path),
                'source': self._detect_source(),
                'basic_metadata': self._extract_basic_metadata(),
                'camera_settings': self._extract_camera_settings(),
                'processing_settings': self._extract_processing_settings(),
                'crop_data': self._extract_crop_data(),
                'image_sizes': self._extract_image_sizes(),
                'raw_namespaces': self._extract_all_namespaces(),
                'nested_metadata': self._extract_nested_metadata(),
            }
            
            # Add Nitro-specific data if present
            if result['source'] == XMPSource.NITRO:
                result['nitro_data'] = self._extract_nitro_data()
                
            return result
            
        except ET.ParseError as e:
            raise ValueError(f"Invalid XML in XMP file {xmp_path}: {e}")
        except Exception as e:
            raise RuntimeError(f"Error parsing XMP file {xmp_path}: {e}")
    
    def _detect_source(self) -> XMPSource:
        """Detect the source application that created the XMP file."""
        if self._root is None:
            return XMPSource.UNKNOWN
            
        # Look for Nitro-specific elements
        nitro_elements = self._root.findall('.//nitro:EditModel', self.NAMESPACES)
        if nitro_elements:
            return XMPSource.NITRO
            
        # Look for Adobe-specific elements
        creator_tool = self._get_attribute_value('xmp:CreatorTool')
        if creator_tool:
            if 'Adobe' in creator_tool or 'Lightroom' in creator_tool:
                return XMPSource.ADOBE
            elif 'Nitro' in creator_tool:
                return XMPSource.NITRO
                
        # Check for CRS namespace usage
        crs_elements = self._root.findall('.//*[@crs:Version]', self.NAMESPACES)
        if crs_elements:
            return XMPSource.ADOBE
            
        return XMPSource.UNKNOWN
    
    def _extract_basic_metadata(self) -> Dict[str, Any]:
        """Extract basic XMP metadata."""
        result = {
            'creator_tool': self._get_attribute_value('xmp:CreatorTool'),
            'metadata_date': self._get_attribute_value('xmp:MetadataDate'),
            'create_date': self._get_attribute_value('xmp:CreateDate'),
            'modify_date': self._get_attribute_value('xmp:ModifyDate'),
            'format': self._get_attribute_value('dc:format'),
        }
        
        # Add Nitro-specific metadata if present
        nitro_edited_size = self._get_attribute_value('nitro:EditedPixelSize')
        nitro_original_size = self._get_attribute_value('nitro:OriginalPixelSize')
        
        if nitro_edited_size:
            result['nitro_edited_pixel_size'] = nitro_edited_size
        if nitro_original_size:
            result['nitro_original_pixel_size'] = nitro_original_size
            
        return result
    
    def _extract_camera_settings(self) -> CameraSettings:
        """Extract camera/EXIF metadata."""
        return CameraSettings(
            make=self._get_attribute_value('tiff:Make'),
            model=self._get_attribute_value('tiff:Model'),
            lens=self._get_attribute_value('aux:Lens'),
            focal_length=self._get_float_value('exif:FocalLength'),
            aperture=self._get_attribute_value('exif:FNumber'),
            shutter_speed=self._get_attribute_value('exif:ExposureTime'),
            iso=self._get_int_value('exif:RecommendedExposureIndex'),
            exposure_bias=self._get_attribute_value('exif:ExposureBiasValue'),
            date_taken=self._get_attribute_value('exif:DateTimeOriginal'),
            orientation=self._get_int_value('tiff:Orientation'),
        )
    
    def _extract_processing_settings(self) -> ProcessingSettings:
        """Extract image processing settings (primarily Adobe CRS)."""
        return ProcessingSettings(
            exposure=self._get_float_value('crs:Exposure2012'),
            contrast=self._get_int_value('crs:Contrast2012'),
            highlights=self._get_int_value('crs:Highlights2012'),
            shadows=self._get_int_value('crs:Shadows2012'),
            whites=self._get_int_value('crs:Whites2012'),
            blacks=self._get_int_value('crs:Blacks2012'),
            clarity=self._get_int_value('crs:Clarity2012'),
            vibrance=self._get_int_value('crs:Vibrance'),
            saturation=self._get_int_value('crs:Saturation'),
            white_balance=self._get_attribute_value('crs:WhiteBalance'),
        )
    
    def _extract_crop_data(self) -> Optional[CropData]:
        """Extract crop data from either Adobe CRS or Nitro format."""
        # Try Adobe CRS format first
        adobe_crop = self._extract_adobe_crop()
        if adobe_crop:
            return adobe_crop
            
        # Try Nitro format
        nitro_crop = self._extract_nitro_crop()
        if nitro_crop:
            return nitro_crop
            
        return None
    
    def _extract_adobe_crop(self) -> Optional[CropData]:
        """Extract Adobe CRS crop data."""
        has_crop = self._get_attribute_value('crs:HasCrop')
        if has_crop != 'True':
            return None
            
        left = self._get_float_value('crs:CropLeft')
        top = self._get_float_value('crs:CropTop') 
        right = self._get_float_value('crs:CropRight')
        bottom = self._get_float_value('crs:CropBottom')
        angle = self._get_float_value('crs:CropAngle')
        
        if all(v is not None for v in [left, top, right, bottom, angle]):
            return CropData(
                left=left,
                top=top,
                right=right,
                bottom=bottom,
                angle=angle,
                has_crop=True
            )
        return None
    
    def _extract_nitro_crop(self) -> Optional[CropData]:
        """Extract crop data from Nitro plist format."""
        nitro_data = self._extract_nitro_data()
        if not nitro_data:
            return None
            
        edit_model = nitro_data.get('edit_model')
        if not edit_model or not isinstance(edit_model, dict):
            return None
            
        # Look for crop data in versions
        versions = edit_model.get('versions', [])
        for version in versions:
            adj_data_arr = version.get('adjDataArr', [])
            for adj in adj_data_arr:
                if adj.get('id') == 'Crop':
                    return self._parse_nitro_crop_json(adj.get('json'))
        
        return None
    
    def _parse_nitro_crop_json(self, crop_json_str: str) -> Optional[CropData]:
        """Parse Nitro crop JSON string into CropData."""
        try:
            crop_data = json.loads(crop_json_str)
            
            if not crop_data.get('enabled', False):
                return None
                
            crop_rect = crop_data.get('cropRect')
            if not crop_rect or len(crop_rect) != 2:
                return None
                
            # Nitro uses different coordinate system - would need conversion
            # This is a simplified version - actual conversion requires image dimensions
            # and the logic from crop_calc.py
            
            return CropData(
                left=0.0,  # Placeholder - needs proper conversion
                top=0.0,
                right=1.0,
                bottom=1.0,
                angle=crop_data.get('numeric', {}).get('straighten', 0.0),
                has_crop=True,
                aspect_width=crop_data.get('aspectWidth'),
                aspect_height=crop_data.get('aspectHeight')
            )
            
        except (json.JSONDecodeError, KeyError):
            return None
    
    def _extract_image_sizes(self) -> Dict[str, Optional[ImageSize]]:
        """Extract original and edited image dimensions."""
        sizes = {}
        
        # Standard TIFF dimensions
        width = self._get_int_value('tiff:ImageWidth')
        height = self._get_int_value('tiff:ImageLength')
        if width and height:
            sizes['tiff'] = ImageSize(width, height)
            
        # EXIF pixel dimensions
        width = self._get_int_value('exif:PixelXDimension')
        height = self._get_int_value('exif:PixelYDimension')
        if width and height:
            sizes['exif'] = ImageSize(width, height)
            
        # Nitro-specific sizes
        original_size_str = self._get_attribute_value('nitro:OriginalPixelSize')
        if original_size_str:
            sizes['nitro_original'] = ImageSize.from_string(original_size_str)
            
        edited_size_str = self._get_attribute_value('nitro:EditedPixelSize')
        if edited_size_str:
            sizes['nitro_edited'] = ImageSize.from_string(edited_size_str)
            
        return sizes
    
    def _extract_nitro_data(self) -> Optional[Dict[str, Any]]:
        """Extract and parse Nitro-specific plist data."""
        if self._root is None:
            return None
            
        # Find the Description element with nitro:EditModel
        description = self._root.find('.//rdf:Description[@nitro:EditModel]', self.NAMESPACES)
        if description is None:
            return None
            
        encoded_plist = description.get(f'{{{self.NAMESPACES["nitro"]}}}EditModel')
        if not encoded_plist:
            return None
            
        try:
            # Decode HTML entities
            decoded_plist = html.unescape(encoded_plist)
            
            # Parse the plist
            plist_data = plistlib.loads(decoded_plist.encode('utf-8'))
            
            # Parse the JSON object in the editModel key if it exists
            if 'editModel' in plist_data and isinstance(plist_data['editModel'], str):
                try:
                    plist_data['edit_model'] = json.loads(plist_data['editModel'])
                    # Keep the original string version too
                    plist_data['edit_model_raw'] = plist_data['editModel']
                    del plist_data['editModel']  # Remove the string version
                except json.JSONDecodeError:
                    plist_data['edit_model'] = None
                    plist_data['edit_model_raw'] = plist_data.get('editModel')
            
            return plist_data
            
        except Exception as e:
            if self.debug:
                print(f"Error parsing Nitro plist data: {e}")
            return None
    
    def _extract_nested_metadata(self) -> Dict[str, Any]:
        """Extract complex nested metadata structures like tone curves, history, etc."""
        if self._root is None:
            return {}
        
        nested_data = {}
        
        # Common nested elements to extract
        nested_elements = [
            'crs:ToneCurvePV2012',
            'crs:ToneCurvePV2012Red', 
            'crs:ToneCurvePV2012Green',
            'crs:ToneCurvePV2012Blue',
            'crs:PointColors',
            'exif:ISOSpeedRatings',
            'xmpMM:History',
            'exif:Flash',
        ]
        
        for element_path in nested_elements:
            data = self._get_nested_element_data(element_path)
            if data is not None:
                # Convert path to a more readable key
                key = element_path.replace(':', '_').lower()
                nested_data[key] = data
        
        # Also extract any other complex child elements we find
        description_elements = self._root.findall('.//rdf:Description', self.NAMESPACES)
        
        for desc_elem in description_elements:
            for child in desc_elem:
                child_name = child.tag
                if child_name.startswith('{'):
                    ns_end = child_name.find('}')
                    if ns_end > 0:
                        namespace = child_name[1:ns_end]
                        local_name = child_name[ns_end + 1:]
                        
                        # Find the namespace prefix
                        ns_prefix = None
                        for prefix, uri in self.NAMESPACES.items():
                            if uri == namespace:
                                ns_prefix = prefix
                                break
                        
                        if ns_prefix:
                            readable_name = f"{ns_prefix}:{local_name}"
                            key = readable_name.replace(':', '_').lower()
                            
                            # Only add if it has complex structure (children or multiple attributes)
                            if list(child) or len(child.attrib) > 1:
                                if key not in nested_data:  # Don't overwrite what we already extracted
                                    structure = self._parse_element_structure(child)
                                    if isinstance(structure, (list, dict)):
                                        nested_data[key] = structure
        
        return nested_data
    
    def _extract_all_namespaces(self) -> Dict[str, List[str]]:
        """Extract all elements grouped by namespace for debugging."""
        if self._root is None:
            return {}
            
        namespaces = {}
        for elem in self._root.iter():
            if elem.tag.startswith('{'):
                # Extract namespace from tag
                ns_end = elem.tag.find('}')
                if ns_end > 0:
                    namespace = elem.tag[1:ns_end]
                    local_name = elem.tag[ns_end + 1:]
                    
                    if namespace not in namespaces:
                        namespaces[namespace] = []
                    if local_name not in namespaces[namespace]:
                        namespaces[namespace].append(local_name)
                        
            # Also check attributes
            for attr_name in elem.attrib:
                if attr_name.startswith('{'):
                    ns_end = attr_name.find('}')
                    if ns_end > 0:
                        namespace = attr_name[1:ns_end]
                        local_name = attr_name[ns_end + 1:]
                        
                        if namespace not in namespaces:
                            namespaces[namespace] = []
                        if local_name not in namespaces[namespace]:
                            namespaces[namespace].append(local_name)
        
        return namespaces
    
    def _get_attribute_value(self, attr_path: str) -> Optional[str]:
        """
        Get attribute value using namespace:attribute format.
        Looks for both attributes and child elements.
        """
        if self._root is None:
            return None
            
        if ':' not in attr_path:
            return None
            
        namespace, attr_name = attr_path.split(':', 1)
        if namespace not in self.NAMESPACES:
            return None
            
        # First, look for the attribute in any Description element
        xpath = f'.//rdf:Description[@{attr_path}]'
        elements = self._root.findall(xpath, self.NAMESPACES)
        
        for elem in elements:
            full_attr = f'{{{self.NAMESPACES[namespace]}}}{attr_name}'
            value = elem.get(full_attr)
            if value is not None:
                return value
        
        # If not found as attribute, look for child elements (Nitro format)
        xpath = f'.//rdf:Description'
        description_elements = self._root.findall(xpath, self.NAMESPACES)
        
        for desc_elem in description_elements:
            # Look for child element with the specified namespace:name
            child_xpath = f'{namespace}:{attr_name}'
            child_elements = desc_elem.findall(child_xpath, self.NAMESPACES)
            
            for child_elem in child_elements:
                if child_elem.text is not None:
                    return child_elem.text
        
        return None
    
    def _get_nested_element_data(self, attr_path: str) -> Optional[Union[List[str], Dict[str, Any]]]:
        """
        Get nested element data for complex structures like sequences and nested elements.
        Returns structured data for elements containing rdf:Seq, rdf:li, etc.
        """
        if self._root is None:
            return None
            
        if ':' not in attr_path:
            return None
            
        namespace, attr_name = attr_path.split(':', 1)
        if namespace not in self.NAMESPACES:
            return None
            
        # Look for the element in Description elements
        xpath = f'.//rdf:Description'
        description_elements = self._root.findall(xpath, self.NAMESPACES)
        
        for desc_elem in description_elements:
            # Look for child element with the specified namespace:name
            child_xpath = f'{namespace}:{attr_name}'
            child_elements = desc_elem.findall(child_xpath, self.NAMESPACES)
            
            for child_elem in child_elements:
                # Check if this element has structured content
                return self._parse_element_structure(child_elem)
        
        return None
    
    def _parse_element_structure(self, element: ET.Element) -> Union[str, List[str], Dict[str, Any]]:
        """
        Parse the structure of an XML element, handling common XMP patterns.
        """
        # If element has only text and no children, return the text
        if element.text and not list(element):
            return element.text.strip()
        
        # Handle rdf:Seq structures (sequences)
        seq_elements = element.findall('.//rdf:Seq', self.NAMESPACES)
        if seq_elements:
            for seq in seq_elements:
                items = []
                li_elements = seq.findall('rdf:li', self.NAMESPACES)
                for li in li_elements:
                    if li.text:
                        items.append(li.text.strip())
                return items
        
        # Handle rdf:Bag structures (unordered collections)
        bag_elements = element.findall('.//rdf:Bag', self.NAMESPACES)
        if bag_elements:
            for bag in bag_elements:
                items = []
                li_elements = bag.findall('rdf:li', self.NAMESPACES)
                for li in li_elements:
                    if li.text:
                        items.append(li.text.strip())
                return items
        
        # Handle rdf:Alt structures (alternatives)
        alt_elements = element.findall('.//rdf:Alt', self.NAMESPACES)
        if alt_elements:
            for alt in alt_elements:
                items = []
                li_elements = alt.findall('rdf:li', self.NAMESPACES)
                for li in li_elements:
                    if li.text:
                        items.append(li.text.strip())
                return items
        
        # Handle nested structures with attributes
        if element.attrib or list(element):
            result = {}
            
            # Add attributes
            for attr_name, attr_value in element.attrib.items():
                # Convert namespaced attribute names to readable format
                if attr_name.startswith('{'):
                    ns_end = attr_name.find('}')
                    if ns_end > 0:
                        namespace = attr_name[1:ns_end]
                        local_name = attr_name[ns_end + 1:]
                        
                        # Find the namespace prefix
                        ns_prefix = None
                        for prefix, uri in self.NAMESPACES.items():
                            if uri == namespace:
                                ns_prefix = prefix
                                break
                        
                        if ns_prefix:
                            readable_name = f"{ns_prefix}:{local_name}"
                        else:
                            readable_name = local_name
                            
                        result[readable_name] = attr_value
                else:
                    result[attr_name] = attr_value
            
            # Add child elements
            for child in element:
                child_name = child.tag
                if child_name.startswith('{'):
                    ns_end = child_name.find('}')
                    if ns_end > 0:
                        namespace = child_name[1:ns_end]
                        local_name = child_name[ns_end + 1:]
                        
                        # Find the namespace prefix
                        ns_prefix = None
                        for prefix, uri in self.NAMESPACES.items():
                            if uri == namespace:
                                ns_prefix = prefix
                                break
                        
                        if ns_prefix:
                            readable_name = f"{ns_prefix}:{local_name}"
                        else:
                            readable_name = local_name
                            
                        result[readable_name] = self._parse_element_structure(child)
            
            return result if result else element.text
        
        # Fallback to text content
        return element.text.strip() if element.text else None
    
    def _get_float_value(self, attr_path: str) -> Optional[float]:
        """Get attribute value as float."""
        value = self._get_attribute_value(attr_path)
        if value is None:
            return None
            
        try:
            # Handle fractional values like "433985/100000"
            if '/' in value:
                parts = value.split('/')
                if len(parts) == 2:
                    return float(parts[0]) / float(parts[1])
            return float(value)
        except (ValueError, ZeroDivisionError):
            return None
    
    def _get_int_value(self, attr_path: str) -> Optional[int]:
        """Get attribute value as integer."""
        value = self._get_attribute_value(attr_path)
        if value is None:
            return None
            
        try:
            return int(float(value))  # Convert via float to handle "400.0" etc.
        except ValueError:
            return None
    
    def get_all_attributes(self) -> Dict[str, str]:
        """Get all attributes from all Description elements."""
        if self._root is None:
            return {}
            
        attributes = {}
        descriptions = self._root.findall('.//rdf:Description', self.NAMESPACES)
        
        for desc in descriptions:
            for attr_name, attr_value in desc.attrib.items():
                # Convert namespaced attribute names to readable format
                if attr_name.startswith('{'):
                    ns_end = attr_name.find('}')
                    if ns_end > 0:
                        namespace = attr_name[1:ns_end]
                        local_name = attr_name[ns_end + 1:]
                        
                        # Find the namespace prefix
                        ns_prefix = None
                        for prefix, uri in self.NAMESPACES.items():
                            if uri == namespace:
                                ns_prefix = prefix
                                break
                        
                        if ns_prefix:
                            readable_name = f"{ns_prefix}:{local_name}"
                        else:
                            readable_name = local_name
                            
                        attributes[readable_name] = attr_value
                else:
                    attributes[attr_name] = attr_value
        
        return attributes
    
    def get_all_elements_and_attributes(self) -> Dict[str, Any]:
        """Get all metadata as a flat dictionary, including both attributes and elements."""
        if self._root is None:
            return {}
            
        all_data = {}
        
        # Get all attributes
        attributes = self.get_all_attributes()
        all_data.update(attributes)
        
        # Get all child elements from Description elements
        descriptions = self._root.findall('.//rdf:Description', self.NAMESPACES)
        
        for desc in descriptions:
            for child in desc:
                child_name = child.tag
                if child_name.startswith('{'):
                    ns_end = child_name.find('}')
                    if ns_end > 0:
                        namespace = child_name[1:ns_end]
                        local_name = child_name[ns_end + 1:]
                        
                        # Find the namespace prefix
                        ns_prefix = None
                        for prefix, uri in self.NAMESPACES.items():
                            if uri == namespace:
                                ns_prefix = prefix
                                break
                        
                        if ns_prefix:
                            readable_name = f"{ns_prefix}:{local_name}"
                        else:
                            readable_name = local_name
                        
                        # Parse the element structure
                        structure = self._parse_element_structure(child)
                        all_data[readable_name] = structure
        
        return all_data
    
    def pretty_print_metadata(self, metadata: Dict[str, Any]) -> str:
        """Format metadata dictionary for human-readable output."""
        lines = []
        lines.append(f"=== XMP Metadata: {Path(metadata['file_path']).name} ===")
        lines.append(f"Source: {metadata['source'].value}")
        lines.append("")
        
        # Basic metadata
        basic = metadata.get('basic_metadata', {})
        if any(basic.values()):
            lines.append("Basic Metadata:")
            for key, value in basic.items():
                if value:
                    lines.append(f"  {key}: {value}")
            lines.append("")
        
        # Camera settings
        camera = metadata.get('camera_settings')
        if camera and any(vars(camera).values()):
            lines.append("Camera Settings:")
            for key, value in vars(camera).items():
                if value is not None:
                    lines.append(f"  {key}: {value}")
            lines.append("")
        
        # Image sizes
        sizes = metadata.get('image_sizes', {})
        if sizes:
            lines.append("Image Sizes:")
            for size_type, size_obj in sizes.items():
                if size_obj:
                    lines.append(f"  {size_type}: {size_obj}")
            lines.append("")
        
        # Crop data
        crop = metadata.get('crop_data')
        if crop:
            lines.append("Crop Data:")
            lines.append(f"  left: {crop.left:.4f}")
            lines.append(f"  top: {crop.top:.4f}")
            lines.append(f"  right: {crop.right:.4f}")
            lines.append(f"  bottom: {crop.bottom:.4f}")
            lines.append(f"  angle: {crop.angle:.4f}")
            lines.append(f"  has_crop: {crop.has_crop}")
            if crop.aspect_width and crop.aspect_height:
                lines.append(f"  aspect: {crop.aspect_width}:{crop.aspect_height}")
            lines.append("")
        
        # Processing settings (abbreviated)
        processing = metadata.get('processing_settings')
        if processing and any(vars(processing).values()):
            lines.append("Processing Settings:")
            for key, value in vars(processing).items():
                if value is not None:
                    lines.append(f"  {key}: {value}")
            lines.append("")
        
        # Nitro-specific data
        nitro_data = metadata.get('nitro_data')
        if nitro_data:
            lines.append("Nitro Data:")
            for key, value in nitro_data.items():
                if key == 'edit_model' and isinstance(value, dict):
                    lines.append(f"  {key}: (parsed JSON object)")
                    lines.append(f"    format_version: {value.get('formatVersion')}")
                    lines.append(f"    default_orientation: {value.get('defaultOrientation')}")
                    versions = value.get('versions', [])
                    lines.append(f"    versions: {len(versions)} version(s)")
                elif key != 'edit_model_raw':  # Skip the raw string version
                    lines.append(f"  {key}: {value}")
            lines.append("")
        
        # Nested metadata (complex structures)
        nested = metadata.get('nested_metadata', {})
        if nested:
            lines.append("Nested Metadata:")
            for key, value in nested.items():
                if isinstance(value, list):
                    lines.append(f"  {key}: [{len(value)} items]")
                    # Show first few items for lists
                    for i, item in enumerate(value[:3]):
                        lines.append(f"    {i}: {item}")
                    if len(value) > 3:
                        lines.append(f"    ... and {len(value) - 3} more")
                elif isinstance(value, dict):
                    lines.append(f"  {key}: (object with {len(value)} properties)")
                    # Show a few key properties
                    for i, (prop_key, prop_value) in enumerate(list(value.items())[:3]):
                        lines.append(f"    {prop_key}: {prop_value}")
                    if len(value) > 3:
                        lines.append(f"    ... and {len(value) - 3} more properties")
                else:
                    lines.append(f"  {key}: {value}")
            lines.append("")
        
        lines.append("="*60)
        return "\n".join(lines)


def main():
    """Command-line interface for the XMP parser."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python xmp_parser.py <xmp_file>      # Parse and display metadata")
        print("  python xmp_parser.py <xmp_dir>       # Parse all XMP files in directory")
        print("")
        print("This script parses XMP metadata files and displays their contents.")
        sys.exit(1)
    
    path = Path(sys.argv[1])
    parser = XMPParser(debug=True)
    
    if path.is_file():
        # Parse single file
        try:
            metadata = parser.parse_file(path)
            print(parser.pretty_print_metadata(metadata))
        except Exception as e:
            print(f"Error parsing {path}: {e}")
    elif path.is_dir():
        # Parse all XMP files in directory
        xmp_files = sorted(path.glob("*.xmp"))
        if not xmp_files:
            print(f"No XMP files found in {path}")
            return
        
        print(f"Found {len(xmp_files)} XMP files to parse\n")
        
        for xmp_file in xmp_files:
            try:
                metadata = parser.parse_file(xmp_file)
                print(parser.pretty_print_metadata(metadata))
                print()  # Extra spacing between files
            except Exception as e:
                print(f"Error parsing {xmp_file}: {e}\n")
    else:
        print(f"Error: {path} is not a valid file or directory")
        sys.exit(1)


if __name__ == "__main__":
    main()