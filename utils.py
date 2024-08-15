import pdfplumber
from collections import defaultdict

def find_horizontal_lines(lines, tolerance=1):
    horizontal_lines = []
    
    for line in lines:
        if abs(line["top"] - line["bottom"]) <= tolerance:  # Check if the line is horizontal
            horizontal_lines.append({
                "x0": line["x0"],
                "x1": line["x1"],
                "y": line["top"]
            })
    
    return horizontal_lines

def group_and_merge_lines(horizontal_lines, gap_threshold=0.1):
    # Group lines by their y-coordinate
    grouped_lines = defaultdict(list)
    
    for line in horizontal_lines:
        grouped_lines[line["y"]].append(line)
    
    merged_lines = []
    
    for y, lines in grouped_lines.items():
        # Sort lines by x0
        lines.sort(key=lambda line: line["x0"])
        
        merged_line = None
        for line in lines:
            if merged_line is None:
                merged_line = line
            else:
                # Check if the current line is close enough to merge
                if line["x0"] - merged_line["x1"] < gap_threshold:
                    # Merge the lines by extending the current merged line's x1
                    merged_line["x1"] = line["x1"]
                else:
                    # If not close enough, store the current merged line and start a new one
                    merged_lines.append(merged_line)
                    merged_line = line
        
        if merged_line:
            merged_lines.append(merged_line)
    
    return merged_lines

def extract_horizontal_lines_from_pdf(pdf_path, pageno):
    # Open the PDF file
    with pdfplumber.open(pdf_path) as pdf:
        # Select the page
        page = pdf.pages[pageno]
        
        # Extract all lines from the page
        lines = page.lines
        
        # Find horizontal lines
        horizontal_lines = find_horizontal_lines(lines)
        
        # Group and merge lines
        merged_lines = group_and_merge_lines(horizontal_lines)
        
        # Print the details of merged horizontal lines
        #for line in merged_lines:
        #    print(f"Merged horizontal line from x0 = {line['x0']} to x1 = {line['x1']}, at y = {line['y']}")
        return merged_lines


def findPdfVerticalLines(image_path):
    image = cv2.imread(image_path, 0)  # Load the image in grayscale
    edges = cv2.Canny(image, 50, 150, apertureSize=3)

    # Use HoughLines to detect lines
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=100, minLineLength=100, maxLineGap=10)

    vertical_lines = []
    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]
            if abs(x1 - x2) < 0.01:  # Almost vertical line
                vertical_lines.append(line[0])

    if vertical_lines:
        print(f"Found {len(vertical_lines)} vertical lines in the image.")
        for line in vertical_lines:
            print(f"Line: {line}")
        return True
    else:
        print("No vertical lines found in the image.")
        return False


def extract_tables_with_best_strategy(pdf_path, start_pageno, end_pageno):
    strategies = [
        {"horizontal_strategy": "lines", "vertical_strategy": "lines"},
        {"horizontal_strategy": "text", "vertical_strategy": "text"},
        {"horizontal_strategy": "lines", "vertical_strategy": "text"},
        {"horizontal_strategy": "text", "vertical_strategy": "lines"}
    ]

    best_table = None
    best_strategy = None
    max_cells = 0

    
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            if page_num != start_pageno - 1:
                continue

            for strategy in strategies:
                if 1:

                    # Crop the page to the bounding box
                    cropped_page = cropPage(page)
                    if cropped_page is None:
                        print("No table found with the given strategies.")
                        best_strategy = None
                        tables = []
                        break

                    # Extract the table from the cropped page
                    tables = cropped_page.extract_tables(strategy)
                else:
                    tables = page.extract_tables(strategy)

                print(f"Number of tables extracted from page {page_num}:", len(tables))

                for table in tables:
                    cell_count = sum(len(row) for row in table)
                    if cell_count > max_cells:
                        max_cells = cell_count
                        best_tables = tables
                        best_strategy = strategy

    if best_tables is not None:
        print(f"Best Strategy: {best_strategy}")
        all_tables = {}
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                if page_num > end_pageno - 1:
                    continue
                print("Page number is : ", page_num)
                if page_num == 0:
                    #tables = cropped_page.extract_tables(best_strategy)
                    tables = page.extract_words(keep_blank_chars=True, use_text_flow=True)
                else:
                    tables = page.extract_tables(best_strategy)
                print(f"Number of tables extracted from page {page_num}:", len(tables))
                print(tables)
                all_tables.update({page_num : [pd.DataFrame(table) for table in tables]})
        #for row in best_table:
        #    print(row)
        #Return a dict where every key, value pair represents list of dfs on that page
        return all_tables
    else:
        print(f"No table found with the given strategies.")
        return {}
