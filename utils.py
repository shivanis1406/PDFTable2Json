import pdfplumber, fitz
from collections import defaultdict
import cv2, re
import numpy as np
from PIL import Image, ImageDraw
import pandas as pd

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
            if abs(x1 - x2) < 0.001:  # Almost vertical line
                vertical_lines.append(line[0])

    if vertical_lines:
        print(f"Found {len(vertical_lines)} vertical lines in the image.")
        for line in vertical_lines:
            print(f"Line: {line}")
        return True
    else:
        print("No vertical lines found in the image.")
        return False

def draw_lines_on_image(image, lines, orientation, color="red"):
    """Draw lines on the image."""
    draw = ImageDraw.Draw(image)
    for line in lines:
        if orientation == "Vertical":
            draw.line([(line[0], line[1]), (line[2], line[3])], fill=color, width=2)
        elif orientation == "Horizontal":
            draw.line([(line[0], line[1]), (line[2], line[3])], fill=color, width=2)
    return image

def combine_lines(lines, orientation):
    """Combine contiguous or overlapping lines."""
    # Sort lines based on their start and end points
    if orientation == "Vertical":
        # Sort vertical lines by x, then by y0
        lines.sort(key=lambda line: (line[0], line[1]))
    elif orientation == "Horizontal":
        # Sort horizontal lines by y, then by x0
        lines.sort(key=lambda line: (line[1], line[0]))

    combined_lines = []
    current_line = lines[0]

    for line in lines[1:]:
        if orientation == "Vertical":
            # If x coordinates are less than 1 unit distance apart (column width is much greater than 1) and lines are contiguous or overlapping in y
            if abs(line[0] - current_line[0]) <= 1 and line[1] <= current_line[3]:
                # Extend the current line
                current_line = (current_line[0], min(current_line[1], line[1]), current_line[2], max(current_line[3], line[3]))
            else:
                combined_lines.append(current_line)
                current_line = line
        elif orientation == "Horizontal":
            # If y coordinates match and lines are contiguous or overlapping in x
            if line[1] == current_line[1] and line[0] <= current_line[2]:
                # Extend the current line
                current_line = (min(current_line[0], line[0]), current_line[1], max(current_line[2], line[2]), current_line[3])
            else:
                combined_lines.append(current_line)
                current_line = line

    combined_lines.append(current_line)
    return combined_lines

def draw_rectangles_on_image(image, rectangles, color="red"):
    """Draw rectangles on the image."""
    draw = ImageDraw.Draw(image)
    for rect in rectangles:
        draw.rectangle([(rect[0], rect[1]), (rect[2], rect[3])], outline=color, width=2)
    return image

def isVerticallineCrossingRange(x0, y0, x1, y1, y_range_bottom, y_range_top):
    # Ensure y_start is the smaller y-coordinate and y_end is the larger one
    y_start, y_end = min(y0, y1), max(y0, y1)
    print("y_start is ", y_start, "y_end is ", y_end, "y_range_bottom is ", y_range_bottom, "y_range_top is ", y_range_top)
    # Check if the vertical line crosses the y0, y1 range
    if (y_start <= y_range_bottom <= y_end) or (y_start <= y_range_top <= y_end) or (y_range_bottom <= y_start and y_range_top >= y_end):
        #print("Crossing range")
        #print("y_start is ", y_start, "y_end is ", y_end, "y_range_bottom is ", y_range_bottom, "y_range_top is ", y_range_top)
        return (x0, y_start, x1, y_end)
    else:
        return None

def is_visible_drawing(drawing):
    # Check if the drawing has a stroke or fill color
    return "stroke" in drawing or "fill" in drawing

def extract_lines_from_pdf(pdf_path, output_image_path, bottoms, tops):
    # Open the PDF
    pdf_document = fitz.open(pdf_path)
    print(f"Number of pages in the PDF is {pdf_document.page_count}")
    is_vertical_lines = False

    # Iterate through each page
    for page_number in range(pdf_document.page_count):
        if page_number > 0:
            #Check if the page is the first page. Skip for other pages
            continue
        page = pdf_document[page_number]
        # Extract drawings (includes lines)
        all_drawings = page.get_drawings()
        #drawings = [drawing for drawing in all_drawings if is_visible_drawing(drawing)]
        drawings = all_drawings
        print("Number of drawings found on page", page_number + 1, ":", len(drawings))
        #if len(drawings) < 5:
        #    print(drawings)
        pix = page.get_pixmap()  # Render the page as an image
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        vertical_lines = []
        horizontal_lines = []
        rectangles = []
        vertical_lines_crossing_range = []

        for drawing in drawings:
            for item in drawing['items']:
                # Look for lines in the drawing items
                print("Item is : ")
                print(item)
                if item[0] == 'l':  # 'l' denotes a line in PyMuPDF
                    start_point = item[1]  # Starting point of the line
                    end_point = item[2]    # Ending point of the line

                    x0, y0 = start_point.x, start_point.y
                    x1, y1 = end_point.x, end_point.y

                    print("Found line beween ", x0, y0, x1, y1)
                    line_type = "Solid"
                    if len(item) > 3 and item[3]:  # If there's a dash pattern, it's a dashed line
                        line_type = "Dashed"
                        print("Dashed line found")

                    # Classify and store the line based on orientation
                    if x0 == x1:
                        ##Check if the vertical line is between bottoms and tops
                        isCrossing = isVerticallineCrossingRange(x0, y0, x1, y1, bottoms[0], tops[0])
                        vertical_lines.append((x0, y0, x1, y1))
                        if isCrossing is not None:
                            vertical_lines_crossing_range.append(isCrossing)
                    #elif y0 == y1:
                    #    horizontal_lines.append((min(x0, x1), y0, max(x0, x1), y1))

                elif item[0] == 're':  # 're' denotes a rectangle in PyMuPDF
                    rect = item[1]
                    x0, y0 = rect.x0, rect.y0
                    x1, y1 = rect.x1, rect.y1
                    
                    ##Line1 [x0,y0] and [x0, y1], Line2 [x1, y0] and [x1, y1]
                    vertical_lines.append((x1, y0, x1, y1))
                    vertical_lines.append((x0, y0, x0, y1))

                    #line 1 of rectangle
                    isCrossing = isVerticallineCrossingRange(x0, y0, x0, y1, bottoms[0], tops[0])

                    if isCrossing is not None:
                        rectangles.append((x0, y0, x1, y1))
                        vertical_lines_crossing_range.append(isCrossing)
                    
                    #line 2 of rectangle
                    isCrossing = isVerticallineCrossingRange(x1, y0, x1, y1, bottoms[0], tops[0])

                    if isCrossing is not None:
                        rectangles.append((x1, y0, x1, y1))
                        vertical_lines_crossing_range.append(isCrossing)

        # Combine lines
        if len(vertical_lines_crossing_range) > 0:
            combined_vertical_lines = combine_lines(vertical_lines_crossing_range, "Vertical")
            # Print the combined lines
            for line in combined_vertical_lines:
                print(f"Page {page_number + 1}: Vertical line from ({line[0]}, {line[1]}) to ({line[2]}, {line[3]})")
            print("Total number of vertical lines found on page", page_number + 1, ":", len(combined_vertical_lines))
            # Draw the lines on the image
            img = draw_lines_on_image(img, combined_vertical_lines, "Vertical", color="blue")
            is_vertical_lines = True
        else:
            print(f"No vertical lines found on page {page_number + 1}")

        #if len(horizontal_lines) > 0:
        #    combined_horizontal_lines = combine_lines(horizontal_lines, "Horizontal")
        #    for line in combined_horizontal_lines:
        #        print(f"Page {page_number + 1}: Combined Horizontal line from ({line[0]}, {line[1]}) to ({line[2]}, {line[3]})")
        #    img = draw_lines_on_image(img, combined_horizontal_lines, "Horizontal", color="green")
        #else:
        #    print(f"No horizontal lines found on page {page_number + 1}")

        #if len(rectangles) > 0:
        #    img = draw_rectangles_on_image(img, rectangles, color="red")
        #else:
        #    print("No rectangles found on page", page_number + 1)
       
        # Save the output image
        img.save(output_image_path)

    # Close the PDF
    pdf_document.close()
    return is_vertical_lines


def keep_visible_lines(obj):
    """
    If the object is a ``rect`` type, keep it only if the lines are visible.

    A visible line is the one having ``non_stroking_color`` as 0.
    """
    if obj['object_type'] == 'rect':
        return obj['non_stroking_color'] == 0
    return True

def extract_tables_with_best_strategy(pdf_path, start_pageno, end_pageno):
    strategies = [
        {"horizontal_strategy": "lines", "vertical_strategy": "lines"},
        {"horizontal_strategy": "text", "vertical_strategy": "text"},
        {"horizontal_strategy": "lines", "vertical_strategy": "text"},
        {"horizontal_strategy": "text", "vertical_strategy": "lines"}
    ]
    #strategies = [
    #    {"horizontal_strategy": "lines", "vertical_strategy": "lines"},
    #]

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
                    #cropped_page = cropPage(page)
                    cropped_page = page
                    if cropped_page is None:
                        print("No table found with the given strategies.")
                        best_strategy = None
                        tables = []
                        break

                    # Extract the table from the cropped page
                    #https://github.com/jsvine/pdfplumber/issues/488 
                    cropped_page.filter(keep_visible_lines)
                    tables = cropped_page.extract_tables(strategy)
                else:
                    tables = page.extract_tables(strategy)

                print(f"Number of tables extracted from page {page_num}:", len(tables))

                for table in tables:
                    cell_count = max(len(row) for row in table)
                    for row in table:
                        print(f"Row is {row}")
                    print("Cell count is ", cell_count, "max_cells is ", max_cells, "strategy is ", strategy)
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
                tables = page.extract_tables(best_strategy)
                #tables = page.extract_words(keep_blank_chars=True, use_text_flow=True)
                print(f"Number of tables extracted from page {page_num}:", len(tables))
                #for table in tables:
                #    print("Table is : ")    
                #    print(table)
                all_tables.update({page_num : [pd.DataFrame(table) for table in tables]})
        #for row in best_table:
        #    print(row)
        #Return a dict where every key, value pair represents list of dfs on that page
        return all_tables
    else:
        print(f"No table found with the given strategies.")
        return {}

def find_header_coordinates(pdf_path, end_pageno, start_pageno):
    x0s = []
    x1s = []
    texts = []
    bottoms = []
    end_indices = []
    start_indices = []
    #all_lines = [[] for _ in range(start_pageno - 1, end_pageno)]
    end_indices_page = []
    tops = []
    header_pattern_1 = re.compile(
                r"date.*balance.*withdrawal.*deposit|"
                r"date.*balance.*deposit.*withdrawal|"
                r"date.*withdrawal.*balance.*deposit|"
                r"date.*withdrawal.*deposit.*balance|"
                r"date.*deposit.*balance.*withdrawal|"
                r"date.*deposit.*withdrawal.*balance|"
                r"balance.*date.*withdrawal.*deposit|"
                r"balance.*date.*deposit.*withdrawal|"
                r"balance.*withdrawal.*date.*deposit|"
                r"balance.*withdrawal.*deposit.*date|"
                r"balance.*deposit.*date.*withdrawal|"
                r"balance.*deposit.*withdrawal.*date|"
                r"withdrawal.*date.*balance.*deposit|"
                r"withdrawal.*date.*deposit.*balance|"
                r"withdrawal.*balance.*date.*deposit|"
                r"withdrawal.*balance.*deposit.*date|"
                r"withdrawal.*deposit.*date.*balance|"
                r"withdrawal.*deposit.*balance.*date|"
                r"deposit.*date.*balance.*withdrawal|"
                r"deposit.*date.*withdrawal.*balance|"
                r"deposit.*balance.*date.*withdrawal|"
                r"deposit.*balance.*withdrawal.*date|"
                r"deposit.*withdrawal.*date.*balance|"
                r"deposit.*withdrawal.*balance.*date", 
                re.IGNORECASE
            )

    header_pattern_2 = re.compile(
                r"balance.*withdraw.*deposit|"
                r"balance.*deposit.*withdraw|"
                r"withdraw.*balance.*deposit|"
                r"withdraw.*deposit.*balance|"
                r"deposit.*balance.*withdraw|"
                r"deposit.*withdraw.*balance|",
                re.IGNORECASE
    )

    header_pattern_3 = re.compile(
                r"balance.*chq\.?.*date|"
                r"balance.*date.*chq\.?|"
                r"chq\.?.*balance.*date|"
                r"chq\.?.*date.*balance|"
                r"date.*balance.*chq\.?|"
                r"date.*chq\.?.*balance|",
                re.IGNORECASE
    )
    
    header_pattern_final = re.compile(
    r".*balance.*withdraw.*deposit|"
    r".*balance.*deposit.*withdraw|"
    r".*withdraw.*balance.*deposit|"
    r".*withdraw.*deposit.*balance|"
    r".*deposit.*balance.*withdraw|"
    r".*deposit.*withdraw.*balance|"
    r".*balance.*chq\.?.*date|"
    r".*balance.*date.*chq\.?|"
    r".*chq\.?.*balance.*date|"
    r".*chq\.?.*date.*balance|"
    r".*date.*balance.*chq\.?|"
    r".*date.*chq\.?.*balance|"
    r"date amount|" #Added for SBI
    r"date description amount", #Added for ICICI
    re.IGNORECASE
)

    start_index = -1
    end_index = -1
    words = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            #print("Page number is : ", page_num, start_pageno, end_pageno)
            if page_num < end_pageno and page_num >= start_pageno - 1:
                i = len(words)
                words.extend(page.extract_words())
                end_indices_page.append(len(words) - 1)
                print("Starting from index ", i, "Number of words after adding page ", page_num," is : ", len(words))
                while i < len(words):
                    j = i + 1
                    start_index = i
                    while j < len(words) and words[j]['bottom'] - words[i]['bottom'] < 0.001:
                        j += 1

                    if (j < len(words) and words[j]['bottom'] - words[i]['bottom'] > 0.001) or (j >= len(words) and words[j - 1]['bottom'] - words[i]['bottom'] < 0.001):
                        end_index = j - 1
                        i = j

                        strr = " ".join([words[i]['text'] for i in range(start_index, end_index + 1)])
                        #print("String is : ", strr)
                        #If the str is a row containing headers
                        if header_pattern_final.match(strr):
                            x0s.append([words[i]['x0'] for i in range(start_index, end_index + 1)])
                            x1s.append([words[i]['x1'] for i in range(start_index, end_index + 1)])
                            texts.append([words[i]['text'] for i in range(start_index, end_index + 1)])
                            #bottoms.append([words[i]['bottom'] for i in range(start_index, end_index + 1)])   
                            #tops.append([words[i]['top'] for i in range(start_index, end_index + 1)])   
                            end_indices.append(end_index)
                            start_indices.append(start_index)
                            bottoms.append(words[start_index]['bottom'])
                            tops.append(words[start_index]['top'])
                            print("Matched String is : ", strr)

                #Find lines on all the pages between start_pagno. and end_pageno.
                #all_lines.append(extract_horizontal_lines_from_pdf(pdf_path, page_num))
    print("length of start_indices is ", len(start_indices))
    print("length of end_indices is ", len(end_indices))
    print("length of bottoms is ", bottoms)
    print("length of tops is ", tops)
    return [x0s, x1s, texts, tops, bottoms, end_indices, start_indices, words, end_indices_page]
