# cypy/cli/ui.py
# ✦ Premium CLI UI and Console Grid Formatter for CYPY ✦

import unicodedata

class Colors:
    """ANSI color codes for premium terminal formatting."""
    PURPLE = "\033[95m"
    CYAN = "\033[96m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

def visual_len(text):
    """
    Returns the visual cell width of a string in the terminal,
    taking into account wide East Asian characters (CJK).
    """
    length = 0
    for char in text:
        # 'W' = Wide, 'F' = Fullwidth
        if unicodedata.east_asian_width(char) in ('W', 'F'):
            length += 2
        else:
            length += 1
    return length

def visual_ljust(text, width):
    """Pads a string to a visual width with trailing spaces."""
    v_len = visual_len(text)
    pad = max(0, width - v_len)
    return text + (' ' * pad)

def print_logo(version):
    """Prints the CYPY logo in a perfectly aligned box."""
    line1 = f"CYPY v{version} - Manga Translator"
    line2 = "Ready to translate~ (◠‿●) ~♪"
    
    # Calculate required box width
    width = max(visual_len(line1), visual_len(line2)) + 6
    
    pad1_left = (width - visual_len(line1)) // 2
    pad1_right = width - visual_len(line1) - pad1_left
    
    pad2_left = (width - visual_len(line2)) // 2
    pad2_right = width - visual_len(line2) - pad2_left
    
    print(f"\n{Colors.CYAN}{Colors.BOLD}┌{'─' * width}┐")
    print(f"│{' ' * pad1_left}{line1}{' ' * pad1_right}│")
    print(f"│{' ' * pad2_left}{line2}{' ' * pad2_right}│")
    print(f"└{'─' * width}┘{Colors.RESET}")

def print_box(title, options, col_width=28):
    """
    Dynamically prints a list of options in a compact 2-column grid layout inside an ASCII box,
    handling wide CJK characters for perfect alignment.
    """
    num_items = len(options)
    half = (num_items + 1) // 2
    
    # Dynamically find the maximum option visual length to prevent truncation/overflow
    max_opt_len = max(visual_len(opt) for opt in options) if options else 0
    # Add safety margin (e.g. 2 spaces) to the column width, ensuring it is at least col_width
    col_width = max(col_width, max_opt_len + 2)
    
    # Calculate box width
    box_width = (col_width * 2) + 1
    
    print(f"\n{Colors.PURPLE}┌{'─' * box_width}┐")
    
    padded_title = visual_ljust(f"  {title}", box_width)
    print(f"│{Colors.BOLD}{Colors.CYAN}{padded_title}{Colors.PURPLE}│")
    print(f"├{'─' * box_width}┤")
    
    for i in range(half):
        col1 = options[i]
        col2 = options[i + half] if (i + half) < num_items else ""
        
        col1_str = f" {visual_ljust(col1, col_width - 1)}"
        col2_str = f" {visual_ljust(col2, col_width - 1)}"
        
        print(f"│{Colors.RESET}{col1_str}│{col2_str}{Colors.PURPLE}│")
        
    print(f"└{'─' * box_width}┘{Colors.RESET}")

def tampilkan_status(provider, target_language):
    """Prints the currently active configuration status."""
    print(f"\n{Colors.GREEN}{Colors.BOLD}[+] Current Configuration:{Colors.RESET}")
    print(f"  {Colors.BOLD}Provider{Colors.RESET} : {provider.provider_name}")
    print(f"  {Colors.BOLD}Model{Colors.RESET}    : {provider.model_name}")
    if hasattr(provider, "base_url") and provider.base_url:
        print(f"  {Colors.BOLD}Base URL{Colors.RESET} : {provider.base_url}")
    print(f"  {Colors.BOLD}Language{Colors.RESET} : {target_language}")

def tampilkan_help():
    """Prints help menu options in a perfectly aligned box."""
    lines = [
        ("[drag file]", "Translate image, PDF or Archive"),
        ("[drag folder]", "Batch translate all images in folder"),
        ("lang / switch", "Change target language"),
        ("provider / api", "Switch API provider"),
        ("model", "Change the LLM model name"),
        ("status", "Show current settings"),
        ("test / api-test", "Test API provider connection"),
        ("tweak", "Adjust layout & filter parameters"),
        ("help", "Show this help menu"),
        ("stop / exit", "Exit cypy CLI")
    ]
    
    max_cmd_len = max(visual_len(cmd) for cmd, _ in lines)
    max_desc_len = max(visual_len(desc) for _, desc in lines)
    
    col1_w = max_cmd_len + 4 # 2 leading spaces + 2 padding
    col2_w = max_desc_len + 2 # 1 leading space + 1 padding
    box_w = col1_w + 1 + col2_w
    
    print(f"\n{Colors.CYAN}{Colors.BOLD}┌{'─' * box_w}┐")
    title_line = visual_ljust("  Available CLI Commands:", box_w)
    print(f"│{title_line}│")
    print(f"├{'─' * box_w}┤")
    
    for cmd, desc in lines:
        col1_str = f"  {visual_ljust(cmd, col1_w - 2)}"
        col2_str = f" {visual_ljust(desc, col2_w - 1)}"
        print(f"│{col1_str}│{col2_str}│")
        
    print(f"└{'─' * box_w}┘{Colors.RESET}")
