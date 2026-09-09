
import re

def remove_outputs(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    new_content = ""
    pos = 0
    while True:
        start = content.find('"outputs": [', pos)
        if start == -1:
            new_content += content[pos:]
            break
        
        new_content += content[pos:start]
        
        # Find matching bracket
        bracket_level = 1
        inner_pos = start + len('"outputs": [')
        while bracket_level > 0 and inner_pos < len(content):
            if content[inner_pos] == '[':
                bracket_level += 1
            elif content[inner_pos] == ']':
                bracket_level -= 1
            elif content[inner_pos] == '"':
                # Skip string content
                inner_pos += 1
                while inner_pos < len(content):
                    if content[inner_pos] == '"' and content[inner_pos-1] != '\\':
                        break
                    inner_pos += 1
            inner_pos += 1
        
        new_content += '"outputs": []'
        pos = inner_pos
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

remove_outputs('result-summary.ipynb')
