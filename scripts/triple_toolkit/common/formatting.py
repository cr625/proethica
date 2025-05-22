#!/usr/bin/env python3
"""
Formatting utilities for the Triple Toolkit.
"""

import textwrap
import shutil
from datetime import datetime

def get_terminal_width():
    """Get the terminal width or default to 80 columns."""
    width, _ = shutil.get_terminal_size((80, 20))
    return width

def format_triple(subject, predicate, object_value, is_literal=True, labels=None):
    """
    Format an RDF triple for display.
    
    Args:
        subject: The subject URI
        predicate: The predicate URI
        object_value: The object value (URI or literal)
        is_literal: Whether the object is a literal value
        labels: Optional dict with labels for subject, predicate, object
        
    Returns:
        Formatted string representation of the triple
    """
    labels = labels or {}
    width = get_terminal_width()
    
    # Get labels if available
    subject_label = labels.get('subject_label', '')
    predicate_label = labels.get('predicate_label', '')
    object_label = labels.get('object_label', '')
    
    # Format the triple components
    if subject_label:
        subject_display = f"{subject} ({subject_label})"
    else:
        subject_display = subject
        
    if predicate_label:
        predicate_display = f"{predicate} ({predicate_label})"
    else:
        predicate_display = predicate
        
    if object_label and not is_literal:
        object_display = f"{object_value} ({object_label})"
    else:
        object_display = object_value
    
    # Wrap and format the triple
    subject_wrapped = textwrap.fill(subject_display, width=width-4)
    predicate_wrapped = textwrap.fill(predicate_display, width=width-4)
    object_wrapped = textwrap.fill(object_display, width=width-4)
    
    triple_str = f"S: {subject_wrapped}\n"
    triple_str += f"P: {predicate_wrapped}\n"
    triple_str += f"O: {object_wrapped}"
    
    return triple_str

def format_datetime(dt):
    """Format a datetime object for display."""
    if not dt:
        return "N/A"
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
        except ValueError:
            return dt
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def print_header(title, width=None):
    """Print a formatted header."""
    width = width or get_terminal_width()
    print("=" * width)
    print(title.center(width))
    print("=" * width)

def print_section(title, width=None):
    """Print a formatted section header."""
    width = width or get_terminal_width()
    print("\n" + "-" * width)
    print(title)
    print("-" * width)

def print_key_value(key, value, indent=0, width=None):
    """Print a key-value pair with wrapping."""
    width = width or get_terminal_width()
    indent_str = " " * indent
    key_str = f"{indent_str}{key}: "
    value_str = str(value)
    
    # Calculate remaining width for the value
    remaining_width = width - len(key_str)
    
    # Wrap the value if needed
    if len(value_str) > remaining_width:
        wrapped_value = textwrap.fill(
            value_str, 
            width=remaining_width,
            initial_indent="",
            subsequent_indent=" " * (len(key_str))
        )
        print(f"{key_str}{wrapped_value}")
    else:
        print(f"{key_str}{value_str}")

def format_table(headers, rows, max_width=None):
    """
    Format data as a simple ASCII table.
    
    Args:
        headers: List of column headers
        rows: List of rows (each row is a list of values)
        max_width: Maximum width for each column (defaults to terminal width / num columns)
        
    Returns:
        Formatted table as a string
    """
    if not rows:
        return "No data to display"
    
    # Ensure all rows have the same number of columns
    num_cols = len(headers)
    rows = [row[:num_cols] + [''] * (num_cols - len(row)) for row in rows]
    
    # Determine column widths
    term_width = get_terminal_width()
    if max_width is None:
        max_width = max(20, term_width // num_cols - 3)  # -3 for padding and borders
    
    col_widths = []
    for i in range(num_cols):
        col_data = [str(row[i]) for row in rows] + [headers[i]]
        col_widths.append(min(max_width, max(len(x) for x in col_data)))
    
    # Format the header
    header = '| '
    header += ' | '.join(h.ljust(w) for h, w in zip(headers, col_widths))
    header += ' |'
    
    # Format the separator
    separator = '+-' + '-+-'.join('-' * w for w in col_widths) + '-+'
    
    # Format the rows
    formatted_rows = []
    for row in rows:
        formatted_row = '| '
        for i, cell in enumerate(row):
            # Truncate long values
            cell_str = str(cell)
            if len(cell_str) > col_widths[i]:
                cell_str = cell_str[:col_widths[i] - 3] + '...'
            formatted_row += cell_str.ljust(col_widths[i]) + ' | '
        formatted_rows.append(formatted_row)
    
    # Assemble the table
    table = separator + '\n' + header + '\n' + separator + '\n'
    table += '\n'.join(formatted_rows) + '\n' + separator
    
    return table
