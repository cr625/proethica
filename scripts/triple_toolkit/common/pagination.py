#!/usr/bin/env python3
"""
Pagination utilities for the Triple Toolkit.
"""

import sys
import os
import shutil

def get_terminal_size():
    """Get the terminal size."""
    return shutil.get_terminal_size((80, 20))

def paginate(items, page_size=None):
    """
    Paginate a list of items for terminal display.
    
    Args:
        items: List of items to paginate
        page_size: Number of items per page (default: auto-calculate based on terminal height)
        
    Returns:
        Generator that yields pages of items
    """
    if not items:
        yield []
        return
    
    # Calculate page size if not provided
    if page_size is None:
        term_height = get_terminal_size()[1]
        # Leave room for header, footer, and prompt
        page_size = max(5, term_height - 10)
    
    total_items = len(items)
    total_pages = (total_items + page_size - 1) // page_size
    
    for page_num in range(total_pages):
        start_idx = page_num * page_size
        end_idx = min(start_idx + page_size, total_items)
        yield items[start_idx:end_idx]

def interactive_pager(items, formatter=None, page_size=None, title=None):
    """
    Display paginated items with interactive navigation.
    
    Args:
        items: List of items to display
        formatter: Function to format each item (defaults to str)
        page_size: Number of items per page (default: auto-calculate)
        title: Optional title to display
        
    Returns:
        None
    """
    if not items:
        print("No items to display")
        return
    
    if formatter is None:
        formatter = str
    
    # Use automatic paging if not specified
    if page_size is None:
        term_height = get_terminal_size()[1]
        # Leave room for header, footer, and prompt
        page_size = max(5, term_height - 10)
    
    total_items = len(items)
    total_pages = (total_items + page_size - 1) // page_size
    current_page = 0
    
    # Display header
    if title:
        term_width = get_terminal_size()[0]
        print("=" * term_width)
        print(title.center(term_width))
        print("=" * term_width)
    
    while True:
        # Clear screen (for better readability)
        os.system('cls' if os.name == 'nt' else 'clear')
        
        # Display title if provided
        if title:
            term_width = get_terminal_size()[0]
            print("=" * term_width)
            print(title.center(term_width))
            print("=" * term_width)
        
        # Calculate page bounds
        start_idx = current_page * page_size
        end_idx = min(start_idx + page_size, total_items)
        
        # Display items
        for i, item in enumerate(items[start_idx:end_idx], start=start_idx+1):
            print(f"{i}. {formatter(item)}")
        
        # Display navigation footer
        print(f"\nPage {current_page + 1} of {total_pages} " +
              f"(Items {start_idx + 1}-{end_idx} of {total_items})")
        
        # Navigation prompt
        if total_pages <= 1:
            print("\nPress q to quit, or enter to continue")
        else:
            print("\nNavigation: n(ext), p(rev), q(uit), g(o to page), or enter item number")
        
        choice = input("> ").strip().lower()
        
        if choice == 'q':
            break
        elif choice == 'n' and current_page < total_pages - 1:
            current_page += 1
        elif choice == 'p' and current_page > 0:
            current_page -= 1
        elif choice.startswith('g'):
            # Go to specific page
            try:
                page_num = int(choice[1:].strip()) - 1
                if 0 <= page_num < total_pages:
                    current_page = page_num
            except ValueError:
                pass
        elif choice.isdigit():
            # Select specific item
            try:
                item_num = int(choice) - 1
                if 0 <= item_num < total_items:
                    # Display the selected item
                    os.system('cls' if os.name == 'nt' else 'clear')
                    print(f"Selected item {item_num + 1}:\n")
                    
                    # Format the item with more detail if available
                    item = items[item_num]
                    try:
                        if hasattr(item, 'to_dict'):
                            details = item.to_dict()
                            for key, value in details.items():
                                print(f"{key}: {value}")
                        else:
                            print(formatter(item))
                    except Exception as e:
                        print(formatter(item))
                        print(f"Error displaying details: {e}")
                    
                    input("\nPress enter to continue")
            except ValueError:
                pass
        elif choice == '':
            break

def simple_paginator(items, formatter=None, page_size=None, prompt=True):
    """
    Simple paginator that displays items with basic pagination.
    
    Args:
        items: List of items to display
        formatter: Function to format each item (defaults to str)
        page_size: Number of items per page (default: auto-calculate)
        prompt: Whether to prompt for continuation (default: True)
        
    Returns:
        None
    """
    if not items:
        print("No items to display")
        return
    
    if formatter is None:
        formatter = str
    
    pages = list(paginate(items, page_size))
    total_pages = len(pages)
    
    for i, page in enumerate(pages):
        for item in page:
            print(formatter(item))
        
        if prompt and i < total_pages - 1:
            if input(f"\nPage {i+1} of {total_pages}. Press Enter to continue or q to quit: ").lower() == 'q':
                break
