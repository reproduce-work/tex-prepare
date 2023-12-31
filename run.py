import os
from pathlib import Path
import toml
from dotenv import load_dotenv
import re
import subprocess
import hashlib
import datetime
import shutil


def generate_filepath_key(path):
    # Extract the filename from the path
    filename = path.split("/")[-1]
    
    # Replace slashes, dots, and underscores with TOML-compatible delimiters
    transformed_filename = filename.replace("_", "_us_").replace("/", "__").replace(".", "_dot_")
    
    # Compute the hash of the entire path
    hash_value = hashlib.sha256(path.encode()).hexdigest()

    # Chop off everything after and including "_dot_"
    keyname = transformed_filename.split("_dot_")[0]
    
    # Replace "_us_" with "_"
    keyname = keyname.replace("_us_", "_")
    
    # Combine the transformed filename with the first 8 characters of the hash
    key = f"{keyname}_{hash_value[:8]}"
    
    return key

def get_toml_value(data, key_str):
    
    # Ensure data is a dictionary
    if not isinstance(data, dict):
        raise ValueError("Provided data is not a dictionary.")
    
    # if embedded object is a file, return filepath
    if generate_filepath_key(key_str) in data:
        curr_data = data[generate_filepath_key(key_str)]
        value = curr_data['filepath']

    else:
        keys = key_str.split('.')
        curr_data = data

        for key in keys:
            # Check for list notation
            if '[' in key and ']' in key:
                # Extract list index and key name
                list_key = key.split('[')[0]
                index = int(key.split('[')[1].split(']')[0])
                
                if list_key not in curr_data:
                    return f"Key {list_key} does not exist.", None

                curr_data = curr_data[list_key][index]
            else:
                if key in curr_data:
                    curr_data = curr_data[key]            
                else:
                    return f"Key {key} does not exist.", None
        
        # At this point, curr_data is the final value we want to extract
        if isinstance(curr_data, dict) and 'value' in curr_data:
            value = curr_data['value']
        elif isinstance(curr_data, (str, int, float, bool, list, datetime.datetime)):
            value = curr_data
        else:
            raise Exception(f"Key {key_str} does not have a valid structure in TOML data.")
        
    # Extract metadata
    metadata = curr_data.copy() if isinstance(curr_data, dict) else {}

    return value, metadata

def fix_lowdown_var_quotes(text):
    pattern = r'\\INSERT\{\\"([^"]*)\'\'\}'
    return re.sub(pattern, r'\\INSERT{"\1"}', text)

def replace_inserts_in_content(content, data):
    start_pos = 0

    # Define the pattern
    pattern = r'\\(INSERT|LINK|FILE|BADGE|WRAP){'

    while True:
        # Use re.search to find the first occurrence of the pattern
        match = re.search(pattern, content[start_pos:])
        if match is None:
            break

        # The start index of the match in the content
        start_idx = match.start() + start_pos
        # The end index of the match in the content
        end_idx = content.find('}', start_idx)
        if end_idx == -1:
            break

        # The matched command
        command = match.group(1)
        # The variable name
        var_name = content[start_idx + len(command) + 2:end_idx]

        # Update start_pos for the next iteration
        start_pos = end_idx + 1
        
        # fix lowdown quotes
        if var_name.endswith("''"):
            pattern = r'([^"]*)\'\''
            var_name = re.sub(pattern, r'\1"', var_name)
        
        if (var_name.startswith('"') and var_name.endswith('"')) or (var_name.startswith("'") and var_name.endswith("'")):
            var_name = var_name[1:-1]
        
        replacement_value, metadata = get_toml_value(data, var_name)

        print(command, var_name, replacement_value, metadata)

        exists = replacement_value is not None

        if exists:
 
            if command == 'INSERT':
                replacement_value = f"{replacement_value}"

            elif command == 'LINK':
                link_source = metadata['published_url']
                replacement_value = rf"\href{{{link_source}}}{{{replacement_value}}}"

            elif command == 'FILE':
                # copy file from location to reproduce/tmp/latex/_static/{file}
                existing_path = replacement_value
                new_path = os.path.join(reproduce_dir, 'tmp', 'report', 'latex', '_static', existing_path)
                os.makedirs(os.path.dirname(new_path), exist_ok=True)
                print(f"Copying {existing_path} to {new_path}")
                shutil.copy(existing_path, new_path)
                replacement_value = f"_static/{existing_path}"

            elif command == 'BADGE':
                link_source = metadata['published_url']
                badge_str = (
                        r'{\footnotesize \href{' + link_source + r'}'
                        r'{\texttt{source} \raisebox{-1mm}'
                        r'{\includegraphics[width=5mm]{_static/logo.png}} }} \hspace{-1.5mm}$\;$'
                    )
                replacement_value = badge_str

            elif command == 'WRAP':
                link_source = metadata['published_url']
                rv = replacement_value.strip()

                center_begin = ''
                center_end = ''
                if rv.startswith(r'\begin{center}') and rv.endswith(r'\end{center}'):

                    replacement_value = (
                        replacement_value
                        .replace(r'\begin{center}', '')
                        .replace(r'\end{center}', '')
                    )
                    center_begin = r'\begin{center}'
                    center_end = r'\end{center}'

                replacement_value = (
                    center_begin + r'\begin{tabular}{r}' + 
                    replacement_value +
                    r'\\ \hfill {\footnotesize \href{' + link_source + 
                    r'}{\texttt{source} \raisebox{-1mm}{\includegraphics[width=5mm]{_static/logo.png}} }} \hspace{-5mm}$\;$' +
                    r'\end{tabular}' + center_end
                )


            print(f"^ Replacing '{var_name}' with '{replacement_value}'")
            content = content[:start_idx] + replacement_value + content[end_idx + 1:]
            
            start_pos = start_idx + len(replacement_value)

        else:
            print(f"^^^ WARNING: {var_name} not found in TOML data")
            start_pos = end_idx + 1

    return content

def replace_inserts_in_content_plain(content, data):
    start_pos = 0
    while True:

        start_idx = content.find(r'\INSERT{', start_pos)
        if start_idx == -1:
            break
        end_idx = content.find('}', start_idx)
        if end_idx == -1:
            break

        var_name = content[start_idx + 8:end_idx]        
        replacement_value, metadata = get_toml_value(data, var_name)  # Use a default value if var_name is not in TOML data
        if not replacement_value:
            print( f"^^^ WARNING: {var_name} not found in TOML data")
            #return content 
        
        print(var_name, replacement_value)

        if 'badge' in data and data['badge'] == 'reproduce-work-logo':
            print('ADDING LOGO BADGE')
            #replacement_value = rf"\href{{https://reproduce.work}}{{\includegraphics[width=0.2\textwidth]{{/img/logo.png}}}}"
            replacement_value += 'BADGE2!'


        print(f"^^ Replacing '{var_name}' with '{replacement_value}'")
        content = content[:start_idx] + (replacement_value) + content[end_idx + 1:]
        start_pos = start_idx + len(replacement_value)

    return content


def run_lowdown(input_string):
    lowdown_cmd = [
        'lowdown', '-stlatex', '--parse-no-intraemph', '--parse-no-super', '-'
    ]
    
    # Run the lowdown command
    process = subprocess.Popen(lowdown_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    lowdown_output, _ = process.communicate(input_string.encode())
    
    # Use python regex to extract between \begin{document} and \end{document}
    # match across lines
    #match = re.search(r'\\begin\{document\}(.*)\\end\{document\}', lowdown_output.decode(), re.DOTALL)
    match = re.search(r'\\begin{document}(.*)\\end{document}', lowdown_output.decode(), re.DOTALL)

    #extract the group from the match object
    result = match.group(1)
    
    print(type(result))
    if result is None:
        result = ""  # or handle it in some other appropriate way

    # replace quotes messed up by lowdown
    # replace anything that matches \INSERT{(.*)''} with  \INSERT{(.*)"}    
    content = fix_lowdown_var_quotes(result)
    

    # Postprocess the lowdown output

    lowdown_postprocessing = { 
        '\emph{': '*', # order matters
        'textbackslash{}': '',
        '\{': '{',
        '\}': '}',
        '\#': '#',
        '\$': '$',
        '\%': '%',
        '\&': '&',
        '\_': '_',
        '\\textasciicircum{}': '^',
        # need to add fix for `` characters
    }

    for key, value in lowdown_postprocessing.items():
        if key in content:
            print(f"^^^ Replacing {key} with {value}")
            content = content.replace(key, value)

    return content



def extract_chunks(content):
    """
    Extracts and identifies chunks from the content based on reproduce.work tags.
    """
    chunk_patterns = {
        'latex': ('<!--%#latex-->', '<!--%#/latex-->'),
        'comment': ('<!--%#comment-->', '<!--%#/comment-->'),
        'python': ('<!--%#python-->', '<!--%#/python-->'),
        'md': ('<!--%#(md|markdown)-->', '<!--%#/(md|markdown)-->'),
    }
    content = content.replace('\x08', '\\b')
    
    # Find all chunk tags (start and end) and their positions
    tag_positions = []
    for chunk_type, (start_tag, end_tag) in chunk_patterns.items():
        for match in re.finditer(re.escape(start_tag), content):
            tag_positions.append((match.start(), chunk_type, start_tag, end_tag))
        for match in re.finditer(re.escape(end_tag), content):
            tag_positions.append((match.start(), "end", start_tag, end_tag))
    
    # Sort tag positions
    tag_positions.sort(key=lambda x: x[0])
    
    chunks = []
    last_pos = 0
    current_chunk_type = 'md'  # Default is markdown

    for pos, tag_type, start_tag, end_tag in tag_positions:
        
        # Capture everything before the current tag as current chunk type
        chunk_content = content[last_pos:pos].strip()
        if chunk_content:
            chunks.append((current_chunk_type, chunk_content))
        
        # Update the current chunk type if we encounter a start tag
        if tag_type != "end":
            current_chunk_type = tag_type
        else:
            current_chunk_type = 'md'  # Revert back to markdown on encountering an end tag

        last_pos = pos + len(start_tag if tag_type != "end" else end_tag)

    # If there's content left after the last tag, capture it
    if last_pos < len(content):
        chunks.append((current_chunk_type, content[last_pos:].strip()))

    # Cleaning chunks from unwanted tags
    cleaned_chunks = []
    for chunk_type, chunk_content in chunks:
        for _, (start_tag, end_tag) in chunk_patterns.items():
            chunk_content = chunk_content.replace(start_tag, "").replace(end_tag, "")
        cleaned_content = chunk_content.strip()
        if cleaned_content:  # Avoid adding empty content chunks
            cleaned_chunks.append((chunk_type, cleaned_content))

    # Fixing the issue where a comment chunk contains md tag
    final_chunks = []
    for i, (chunk_type, chunk_content) in enumerate(cleaned_chunks):
        if chunk_type == 'comment' and '<!--%#md-->' in chunk_content:
            parts = chunk_content.split('<!--%#md-->')
            chunk_content =  parts[0].strip()
       
        # Search for any remaming tags in the chunk content and remove them
        # use regex swap out anything between <!--%# and --> on a single line
        chunk_content = re.sub(r'<!--%#.*?-->', '', chunk_content).strip()
        
        print(f'{chunk_type}: {chunk_content}')
        final_chunks.append((chunk_type, chunk_content))


    return final_chunks



def process_markdown_chunk(chunk_content, data_toml):
    """
    Processes a markdown chunk.
    - Replaces \INSERT{*} variables.
    - Passes through lowdown (simulated for now).
    """
    # Replace \INSERT{*} variables
    chunk_content = replace_inserts_in_content(chunk_content, data_toml)
    
    # For the sake of demonstration, simulating passing through lowdown.
    # In a real-world scenario, we would invoke the lowdown tool here.
    chunk_content = f"[Processed by lowdown]: {chunk_content}"
    
    return chunk_content



def replace_config_inserts(content):
    if '\\INSERT{config.' in content:
        #timestamp = base_config['project']['timestamp']
        base_config = read_base_config()
        #tmp_config = { k:{'value': v, 'timestamp': timestamp} for k,v in base_config.items()}
        tmp_config = base_config.copy()
        content = replace_inserts_in_content_plain(
            content.replace('\\INSERT{config.', '\\INSERT{'),
            tmp_config
        )
    return content

# Test processing of chunks
def process_chunks(chunks, data_toml):
    processed_chunks = []
    for chunk_type, chunk_content in chunks:
        chunk_content = replace_config_inserts(chunk_content)
        if chunk_type == 'md':
            # render with lowdown
            chunk_content = replace_config_inserts(chunk_content)
            rendered_chunk = run_lowdown(chunk_content)
            print(f'rendered_chunk_content: {rendered_chunk}')
            rendered_chunk = replace_inserts_in_content(rendered_chunk, data_toml)
            rendered_chunk = replace_config_inserts(rendered_chunk)
            processed_chunks.append(rendered_chunk) 
        elif chunk_type == 'latex':
            chunk_content = replace_inserts_in_content(chunk_content, data_toml)
            processed_chunks.append(chunk_content)
        elif chunk_type == 'comment':
            pass
        else:
            # For comment and python chunks, keep them as they are for now.
            processed_chunks.append(chunk_content)

    combined_chunks = '\n\n'.join(str(chunk) for chunk in processed_chunks)
    return combined_chunks

class ReproduceWorkEncoder(toml.TomlEncoder):
    def dump_str(self, v):
        """Encode a string."""
        if "\n" in v:
            return '"""\n' + v.strip() + '\n' + '"""'
        return super().dump_str(v)
    
    def dump_value(self, v):
        """Determine the type of a Python object and serialize it accordingly."""
        if isinstance(v, str) and "\n" in v:
            return '"""\n' + v.strip() + '\n' + '"""'
        return super().dump_value(v)

if __name__ == '__main__':
    
    load_dotenv()
    reproduce_dir = os.getenv("REPROWORKDIR")
    def read_base_config():
        with open(Path(reproduce_dir, 'config.toml'), 'r') as f:
            data = toml.load(f)
        return data
    base_config = read_base_config()

    if Path('project.toml').exists():
        with open('project.toml', 'r') as f:
            user_project_data = toml.load(f)
            
        # Add user project data to base config.toml
        for k in ['project_name', 'full_title', 'abstract','watch']:
            if k in user_project_data:
                base_config['project'][k] = user_project_data[k]

        if 'authors' in user_project_data:
            base_config['authors'] = user_project_data['authors']
        
        if 'environment' in user_project_data:
            if 'repro' not in base_config:
                base_config['repro'] = {}
            
            base_config['repro']['environment'] = user_project_data['environment']
    
        # Write the updated config.toml
        with open(Path(reproduce_dir, 'config.toml'), 'w') as f:
            toml.dump(base_config, f, encoder=ReproduceWorkEncoder())
    
    output_linefile = base_config['repro']['files']['output_linefile']
    
    # raise error if f'./{reproduce_dir}/tmp/' doesn't exist
    if not os.path.exists(f'./{reproduce_dir}/tmp/'):
        raise Exception(f'./{reproduce_dir}/tmp/ does not exist')

    print('Replacing \INSERTs with TOML data in latex_template file')
    template_filepath = base_config['repro']['files']['template']
    with open(Path(template_filepath), 'r') as f:
        latex_template_content = f.read()

    latex_template_content = replace_config_inserts(latex_template_content)
    
    # make interfim file
    # enusre latex dir exists
    interim_filename = 'latex_template_interim.tex'
    tmp_latex_dir = os.path.join(reproduce_dir, 'tmp', os.path.dirname(template_filepath))
    os.makedirs(tmp_latex_dir, exist_ok=True)

    interim_filepath = os.path.join(tmp_latex_dir, interim_filename)
    with open(interim_filepath, 'w+') as f:
        f.write(latex_template_content)

    # Read input text file
    print(f"Reading INPUT files: {base_config['repro']['files']['input']}")
    with open(Path( base_config['repro']['files']['input']), 'r') as f:
        content = f.read()

    # Read TOML data
    print(f"Reading TOML data: {base_config['repro']['files']['dynamic']}")
    with open(Path( base_config['repro']['files']['dynamic']), 'r') as f:
        data_toml = toml.load(f)

    print('Replacing \INSERTs with TOML data in main input file')
    chunks = extract_chunks(content)
    content = process_chunks(chunks, data_toml)

    with open(interim_filepath, 'r') as f:
        template = f.read()

    compiled = template.replace('%%@@LOWDOWN_CONTENT@@%%', content)

    linefile_fullpath = os.path.join(reproduce_dir, 'tmp', output_linefile)
    
    print(f'Writing compiled output {linefile_fullpath}')
    with open(linefile_fullpath, 'w+') as f:
        f.write(compiled)

    print('Done')