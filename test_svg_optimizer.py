#!/usr/bin/env python3
"""
Test script for the SVG optimizer

This script tests the SVG optimizer by:
1. Running the optimizer on a sample SVG file
2. Verifying that unnecessary elements are removed
3. Checking that essential elements are preserved
4. Measuring the size reduction achieved
"""

import sys
from svg_optimizer import simplify_svg

def run_test():
    """Run the SVG optimizer test and display results"""
    print("=== SVG OPTIMIZER TEST ===")
    
    # Original SVG content from the user's request
    original_svg_content = """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.0//EN" "svg.dtd">
<!-- ========================================================================================== -->
<!-- Detailed Standard Map                                                                      -->
<!--   background (and quite nice) map bitmap by J. Fatula III                                  -->
<!--   SVG by Zach DelProposto                                                                  -->
<!-- Copyright jDip - GPL License                                                               -->
<!-- ========================================================================================== -->
<svg color-rendering="optimizeQuality" height="680px" preserveAspectRatio="xMinYMin" version="1.0" viewBox="0 0 1835 1360" width="918px" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:jdipNS="svg.dtd">

    <jdipNS:DISPLAY>
        <jdipNS:ZOOM min="5" max="2200" factor="1.2"/>
        <jdipNS:LABELS brief="true" full="true"/>
    </jdipNS:DISPLAY>

    <jdipNS:ORDERDRAWING>
        <jdipNS:POWERCOLORS>
            <jdipNS:POWERCOLOR power="austria" color="#c48f85"/>
            <jdipNS:POWERCOLOR power="england" color="darkviolet"/>
            <jdipNS:POWERCOLOR power="france" color="royalblue"/>
            <jdipNS:POWERCOLOR power="germany" color="#a08a75"/>
            <jdipNS:POWERCOLOR power="italy" color="forestgreen"/>
            <jdipNS:POWERCOLOR power="russia" color="#757d91"/>
            <jdipNS:POWERCOLOR power="turkey" color="#b9a61c"/>
        </jdipNS:POWERCOLORS>

        <jdipNS:SYMBOLSIZE name="Fleet" width="40" height="40"/>
        <jdipNS:SYMBOLSIZE name="Army" width="40" height="40"/>
        <jdipNS:SYMBOLSIZE name="Wing" width="40" height="40"/>
        <jdipNS:SYMBOLSIZE name="DislodgedFleet" width="40" height="40"/>
        <jdipNS:SYMBOLSIZE name="DislodgedArmy" width="40" height="40"/>
        <jdipNS:SYMBOLSIZE name="DislodgedWing" width="40" height="40"/>
        <jdipNS:SYMBOLSIZE name="FailedOrder" width="30" height="30"/>
        <jdipNS:SYMBOLSIZE name="SupplyCenter" width="20" height="20"/>
        <jdipNS:SYMBOLSIZE name="BuildUnit" width="60" height="60"/>
        <jdipNS:SYMBOLSIZE name="RemoveUnit" width="50" height="50"/>
        <jdipNS:SYMBOLSIZE name="WaivedBuild" width="40" height="40"/>
        <jdipNS:SYMBOLSIZE name="HoldUnit" width="66.6" height="66.6"/>
        <jdipNS:SYMBOLSIZE name="SupportHoldUnit" width="76.6" height="76.6"/>
        <jdipNS:SYMBOLSIZE name="ConvoyTriangle" width="66.4" height="57.4"/>
        <!-- Special symbol size to contain stroke width for plain (in "height") and power-colored lines (in "width") -->
        <jdipNS:SYMBOLSIZE name="Stroke" width="6" height="10"/>
    </jdipNS:ORDERDRAWING>

    <jdipNS:PROVINCE_DATA>
        <jdipNS:PROVINCE name="adr">
            <jdipNS:UNIT x="793.5" y="1048.0"/>
            <jdipNS:DISLODGED_UNIT x="782.0" y="1038.0"/>
        </jdipNS:PROVINCE>
        </jdipNS:PROVINCE_DATA>

    <defs>
        <style type="text/css"><![CDATA[
        /* text */
        svg { font-size: 100% }
        .labeltext24 {font-size:1.4em;}
        ]]></style>
    </defs>

    <g id="MapLayer" transform="translate(-195 -170)">
        <rect fill="black" height="1360" width="1835" x="195" y="170"/>
        <path class="nopower" d="M 1424 1364 C 1437 1361 1448 1353 1459 1346 C 1464 1343 1470 1337 1475 1336 C 1482 1334 1492 1338 1499 1340 C 1510 1342 1518 1341 1528 1336 C 1544 1328 1555 1307 1575 1297 C 1587 1291 1598 1293 1611 1293 C 1614 1293 1621 1292 1624 1292 C 1646 1286 1638 1257 1637 1241 C 1618 1244 1604 1253 1583 1253 C 1566 1253 1565 1248 1554 1246 C 1553 1247 1553 1248 1551 1248 C 1548 1249 1541 1242 1538 1240 C 1535 1242 1529 1247 1526 1246 C 1521 1245 1517 1235 1511 1235 C 1507 1236 1507 1239 1497 1241 C 1483 1243 1471 1243 1457 1249 C 1450 1253 1440 1261 1435 1266 C 1433 1268 1421 1282 1420 1284 C 1419 1286 1419 1290 1419 1292 C1419 1300 1423 1305 1425 1312 1428 1318 1430 1326 1431 1333 C 1432 1342 1427 1355 1424 1364 z" id="_ank"/>
    </g>
</svg>
"""

    # Test the optimizer
    print("\nRunning SVG optimizer...")
    optimized_svg = simplify_svg(original_svg_content)

    # Print the optimized SVG (first 500 chars for brevity)
    print("\n=== OPTIMIZED SVG (PREVIEW) ===")
    preview_length = min(500, len(optimized_svg))
    print(f"{optimized_svg[:preview_length]}...")
    print(f"[Total length: {len(optimized_svg)} characters]")

    # Print some stats
    original_size = len(original_svg_content)
    optimized_size = len(optimized_svg)
    reduction = (1 - optimized_size / original_size) * 100

    print("\n=== OPTIMIZATION STATS ===")
    print(f"Original size: {original_size:,} bytes")
    print(f"Optimized size: {optimized_size:,} bytes")
    print(f"Size reduction: {reduction:.2f}%")

    # Check if key elements were removed/preserved
    print("\n=== VERIFICATION ===")
    
    # Elements that should be removed
    removed_elements = [
        ("DOCTYPE declaration", "<!DOCTYPE", True),
        ("Comments", "<!--", True),
        ("jdipNS namespace", "jdipNS:", True),
        ("DISPLAY element", "<jdipNS:DISPLAY>", True),
        ("ORDERDRAWING element", "<jdipNS:ORDERDRAWING>", True),
        ("PROVINCE_DATA element", "<jdipNS:PROVINCE_DATA>", True),
        ("Style definitions", "<style", True),
    ]
    
    # Elements that should be preserved
    preserved_elements = [
        ("SVG root element", "<svg", True),
        ("MapLayer group", "MapLayer", True),
        ("Path element", "<path", True),
        ("Rectangle element", "<rect", True),
        ("viewBox attribute", "viewBox=", True),
    ]
    
    # Check removed elements
    print("\nElements that should be removed:")
    all_removed = True
    for name, pattern, should_be_removed in removed_elements:
        is_removed = pattern not in optimized_svg
        status = "✓ REMOVED" if is_removed else "✗ STILL PRESENT"
        if not is_removed:
            all_removed = False
        print(f"  {name}: {status}")
    
    # Check preserved elements
    print("\nElements that should be preserved:")
    all_preserved = True
    for name, pattern, should_be_preserved in preserved_elements:
        is_preserved = pattern in optimized_svg
        status = "✓ PRESERVED" if is_preserved else "✗ MISSING"
        if not is_preserved:
            all_preserved = False
        print(f"  {name}: {status}")
    
    # Overall test result
    print("\n=== TEST RESULT ===")
    if all_removed and all_preserved:
        print("✅ SUCCESS: All tests passed!")
    else:
        print("❌ FAILURE: Some tests failed!")
        if not all_removed:
            print("  - Some elements that should be removed are still present")
        if not all_preserved:
            print("  - Some elements that should be preserved are missing")
    
    # Return success status for potential CI/CD integration
    return all_removed and all_preserved

if __name__ == "__main__":
    success = run_test()
    sys.exit(0 if success else 1) 