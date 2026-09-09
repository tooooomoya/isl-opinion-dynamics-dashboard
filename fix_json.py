
import re

def fix_json(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    fixed_lines = []
    in_array = False
    for line in lines:
        # Detect start of an array (source or traceback)
        if '"source": [' in line or '"traceback": [' in line or '"text": [' in line:
            in_array = True
            fixed_lines.append(line)
            continue
        
        if in_array:
            if ']' in line:
                in_array = False
                fixed_lines.append(line)
                continue
            
            # Try to fix unescaped quotes in the string
            # A line in these arrays should look like: "content\n", or "content"
            match = re.match(r'^(\s*)(")(.*)(")(,?\n)$', line)
            if match:
                indent, q1, content, q2, end = match.groups()
                # Escape unescaped double quotes in content
                # but be careful about already escaped quotes \"
                # and don't escape \u001b etc.
                
                # Simple way: escape all " that are not preceded by \
                fixed_content = ""
                escaped = False
                for i, char in enumerate(content):
                    if char == '"' and not escaped:
                        fixed_content += '\\"'
                    else:
                        fixed_content += char
                    
                    if char == '\\' and not escaped:
                        escaped = True
                    else:
                        escaped = False
                
                fixed_lines.append(f'{indent}{q1}{fixed_content}{q2}{end}')
            else:
                fixed_lines.append(line)
        else:
            fixed_lines.append(line)
            
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(fixed_lines)

fix_json('result-summary.ipynb')
