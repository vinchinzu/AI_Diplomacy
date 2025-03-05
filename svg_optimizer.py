#!/usr/bin/env python3
"""
SVG Optimizer - A tool to simplify and optimize SVG files

This module provides functions to clean up SVG files by:
1. Removing unnecessary metadata, comments, and custom namespaces
2. Simplifying paths using the svgelements library
3. Standardizing dimensions with viewBox
4. Removing inline styles and unnecessary attributes

Author: AI Assistant
"""

import xml.etree.ElementTree as ET
import io
import re
import os
from svgelements import Path

def simplify_svg(svg_content):
    """
    Simplifies and optimizes SVG content by:
    1. Removing unnecessary metadata, comments, and hidden elements.
    2. Simplifying paths and shapes.
    3. Standardizing dimensions (setting viewBox).
    
    Args:
        svg_content (str): The SVG content as a string
        
    Returns:
        str: The optimized SVG content
    """
    # Remove comments before parsing (ElementTree doesn't handle comments well)
    svg_content = re.sub(r'<!--[\s\S]*?-->', '', svg_content)
    
    # Parse the SVG content
    try:
        # Register SVG namespaces to avoid prefix generation
        ET.register_namespace('', 'http://www.w3.org/2000/svg')
        ET.register_namespace('xlink', 'http://www.w3.org/1999/xlink')
        
        # Parse the SVG
        tree = ET.parse(io.StringIO(svg_content))
        root = tree.getroot()
    except ET.ParseError as e:
        return f"Error parsing SVG: {e}"
    
    # 1. Remove metadata, custom elements, and unnecessary elements
    for element in list(root):  # Iterate over a copy to allow modification
        tag = element.tag
        if (tag.endswith('}DISPLAY') or
            tag.endswith('}ORDERDRAWING') or
            tag.endswith('}PROVINCE_DATA') or
            tag == '{http://www.w3.org/2000/svg}defs' or
            tag == '{http://www.w3.org/2000/svg}metadata' or
            tag == '{http://www.w3.org/2000/svg}style'):
            root.remove(element)
    
    # Remove jdipNS namespace declaration and attributes as they are custom
    jdipns_prefix = '{svg.dtd}'
    for element in root.iter():
        attrib_to_remove = []
        for attrib_name in element.attrib:
            if attrib_name.startswith('{svg.dtd}'):
                attrib_to_remove.append(attrib_name)
        for attrib_name in attrib_to_remove:
            del element.attrib[attrib_name]
    
    # 2. Simplify paths and shapes
    for path_element in root.findall('.//{http://www.w3.org/2000/svg}path'):
        d_attribute = path_element.get('d')
        if d_attribute:
            try:
                # Parse the path data
                path = Path(d_attribute)
                
                # Simplify the path using svgelements
                # First convert all arcs to cubic bezier curves for better handling
                path.approximate_arcs_with_cubics()
                
                # Basic path simplification - remove redundant commands
                simplified_d = path.d()
                
                # Set the simplified path back
                path_element.set('d', simplified_d)
            except Exception as e:
                print(f"Path simplification error for path {path_element.get('id', 'unknown')}: {e}")
                # Keep the original path if simplification fails
                continue
    
    # 3. Standardize dimensions with viewBox
    if 'viewBox' not in root.attrib:
        # Try to get width and height
        width = root.get('width')
        height = root.get('height')
        
        if width and height:
            # Extract numeric values
            width_value = re.match(r'(\d+)', width)
            height_value = re.match(r'(\d+)', height)
            
            if width_value and height_value:
                width_num = float(width_value.group(1))
                height_num = float(height_value.group(1))
                root.set('viewBox', f"0 0 {width_num} {height_num}")
    
    # Remove width and height if viewBox is present
    if 'viewBox' in root.attrib:
        if 'width' in root.attrib:
            del root.attrib['width']
        if 'height' in root.attrib:
            del root.attrib['height']
    
    # 4. Export as clean SVG code snippet
    output_io = io.StringIO()
    tree.write(output_io, encoding='unicode', xml_declaration=True, short_empty_elements=True)
    
    # Get the output and clean it up
    optimized_svg_code = output_io.getvalue()
    
    # Remove DOCTYPE from string output as ElementTree doesn't fully remove it
    optimized_svg_code = re.sub(r'<!DOCTYPE[^>]*>', '', optimized_svg_code)
    
    # Remove comments that might have been missed by ElementTree
    optimized_svg_code = re.sub(r'<!--[\s\S]*?-->', '', optimized_svg_code)
    
    return optimized_svg_code.strip()


def find_parent(root, element):
    """
    Find the parent of an element in the XML tree
    
    Args:
        root (Element): The root element of the tree
        element (Element): The element to find the parent for
        
    Returns:
        Element: The parent element or None if not found
    """
    for parent in root.iter():
        for child in list(parent):
            if child == element:
                return parent
    return None


if __name__ == "__main__":
    # Test the function with a sample SVG
    test_svg = """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.0//EN" "svg.dtd">
<!-- Comment to be removed -->
<svg color-rendering="optimizeQuality" height="680px" preserveAspectRatio="xMinYMin" version="1.0" viewBox="0 0 1835 1360" width="918px" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:jdipNS="svg.dtd">
    <jdipNS:DISPLAY>
        <jdipNS:ZOOM min="5" max="2200" factor="1.2"/>
    </jdipNS:DISPLAY>
    <defs>
        <style type="text/css"><![CDATA[
        /* text */
        svg { font-size: 100% }
        ]]></style>
    </defs>
    <g id="MapLayer">
        <path id="test" d="M 10 10 L 20 20 L 30 30 Z"/>
    </g>
</svg>"""
    
    optimized = simplify_svg(test_svg)
    print(optimized) 