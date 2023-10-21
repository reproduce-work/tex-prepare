import os
from pathlib import Path
import toml
from dotenv import load_dotenv
import re
import subprocess
import hashlib


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

def get_toml_key(data, key):

    if 'img/scatter' in key:
        print(data,key)

    # Check if the key exists
    if key in data:
        # Extract the value
        if 'type' in data[key] and data[key]['type']=='file':
            # file types, return filepath (should we return the contents of the file instead?)
            value = key
        elif 'value' in data[key]:
            value = data[key]['value']
        
        else:
            raise Exception(f"Key {key} does not have a value field in TOML data:\n\n{data.keys()}")
        
        # Extract metadata
        metadata = data[key].copy()

        return value, metadata
    else:
        return None, None

def fix_lowdown_var_quotes(text):
    pattern = r'\\INSERT\{\\"([^"]*)\'\'\}'
    return re.sub(pattern, r'\\INSERT{"\1"}', text)

def replace_inserts_in_content(content, data):
    start_pos = 0

    while True:

        start_idx = content.find(r'\INSERT{', start_pos)
        if start_idx == -1:
            break
        end_idx = content.find('}', start_idx)
        if end_idx == -1:
            break

        var_name = content[start_idx + 8:end_idx]
        
        # fix lowdown quotes
        if var_name.endswith("''"):
            pattern = r'([^"]*)\'\''
            var_name = re.sub(pattern, r'\1"', var_name)
        
        if (var_name.startswith('"') and var_name.endswith('"')) or (var_name.startswith("'") and var_name.endswith("'")):
            var_name = var_name[1:-1]

        if var_name in data:
            replacement_value, metadata = get_toml_key(data, var_name)
        elif generate_filepath_key(var_name) in data:
            print('^^^: filepath var found')
            var_name = generate_filepath_key(var_name)
            print(var_name, data[var_name].keys())
            replacement_value, metadata = data[var_name]['filepath'], data[var_name].copy()
            print(f"^^^: {var_name}, {replacement_value}, {metadata}")
        else:
            print(f"^^^ WARNING: {var_name} not found in TOML data")

        exists = replacement_value is not None

        if exists:
            # get published_url
            if 'badge_link' in metadata:
                badge_link = metadata['badge_link']
            elif 'published_url' in metadata:
                badge_link = metadata['published_url']
            else:
                raise Exception(f"Key {key} does not have a badge_link or published_url field in TOML data:\n\n{data.keys()}")

            if 'plot' in metadata and metadata['plot'] in [True,'True','true']:
                
                if 'badge' in metadata:
                    badge_str = (
                        r'\hfill {\footnotesize \href{' + badge_link + r'}'
                        r'{\texttt{source} \raisebox{-1mm}'
                        r'{\includegraphics[width=5mm]{../../../../img/logo.png}} }} \hspace{-1.5mm}$\;$'
                    )
                else:
                    badge_str = ''
                            
                replacement_value = (
                    r'\begin{figure}[h]' '\n'
                    r'\centering' '\n'
                    r'\begin{minipage}{0.75\textwidth}' '\n'
                    r'\centering' '\n'
                    r'\caption{A scatter plot generated using Python and compiled into this report using \texttt{reproduce.work} software}' '\n'
                    r'\label{fig:scatter}' '\n'
                    r'\includegraphics[width=.8\textwidth]{../../../../' + replacement_value + '}' '\n'
                    + badge_str + '\n'
                    r'\end{minipage}' '\n'
                    r'\end{figure}'
                )


            elif 'badge' in metadata:
                if metadata['badge'] == 'reproduce-work-logo':
                    # ADDING LOGO BADGE
                    
                    replacement_value = (
                        replacement_value
                        .replace(r'\begin{center}', '')
                        .replace(r'\end{center}', '')
                    )
                    replacement_value = (
                        r'\begin{center}\begin{tabular}{r}' + 
                        replacement_value +
                        r'\\ \hfill {\footnotesize \href{' + badge_link + 
                        r'}{\texttt{source} \raisebox{-1mm}{\includegraphics[width=5mm]{../../../../img/logo.png}} }} \hspace{-1.5mm}$\;$' +
                        r'\end{tabular}\end{center}'
                    )

            
            print(f"^ Replacing {var_name} with {replacement_value}")
            content = content[:start_idx] + replacement_value + content[end_idx + 1:]
            
            start_pos = start_idx + len(replacement_value)

        else:
            start_pos = end_idx + 1

    return content


def get_toml_val(data, key):
    keys = key.split(".")
    current_data = data
    for k in keys:
        if k in current_data:
            current_data = current_data[k]
        else:
            return False
    if type(current_data) != str:
        current_data = str(current_data)
    return current_data


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
        replacement_value = get_toml_val(data, var_name)  # Use a default value if var_name is not in TOML data
        if not replacement_value:
            print( f"^^^ WARNING: {var_name} not found in TOML data")
            return content 
        
        print(var_name, replacement_value)

        if 'badge' in data and data['badge'] == 'reproduce-work-logo':
            print('ADDING LOGO BADGE')
            #replacement_value = rf"\href{{https://reproduce.work}}{{\includegraphics[width=0.2\textwidth]{{/img/logo.png}}}}"
            replacement_value += 'BADGE2!'


        print(f"^^ Replacing {var_name} with {replacement_value}")
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
            chunk_content = replace_inserts_in_content_plain(chunk_content, data_toml)
            processed_chunks.append(chunk_content)
        elif chunk_type == 'comment':
            pass
        else:
            # For comment and python chunks, keep them as they are for now.
            processed_chunks.append(chunk_content)

    combined_chunks = '\n\n'.join(str(chunk) for chunk in processed_chunks)
    return combined_chunks



if __name__ == '__main__':

    load_dotenv()
    reproduce_dir = os.getenv("REPROWORKDIR")

    def read_base_config():
        with open(Path(reproduce_dir, 'config.toml'), 'r') as f:
            data = toml.load(f)
        return data
    base_config = read_base_config()

    document_dir = base_config['repro']['document_dir']
    output_linefile = base_config['repro']['files']['output_linefile']
    
    # ensure tmp dir exists
    os.makedirs(f'./{reproduce_dir}/tmp', exist_ok=True)
    os.makedirs(f'./{reproduce_dir}/tmp/{document_dir}', exist_ok=True)

    # copy contents from document_dir except report.pdf to reproduce_dir/tmp/document_dir
    #os.system(f'find ./{document_dir}/ -type f ! -name "report.pdf" -exec cp {{}} ./{reproduce_dir}/tmp/{document_dir}/ \;')

    # Delete contents of target directory
    # List of files to copy
    files_to_copy = [
        "main.md",
        "latex/apa.bst",
        "latex/bibliography.bib",
        "latex/template.tex"
    ]

    # Loop over each file and copy it to the target directory
    for file in files_to_copy:
        os.system(f'cp ./{document_dir}/{file} ./{reproduce_dir}/tmp/{document_dir}/{file}')

    print('Replacing \INSERTs with TOML data in latex_template file')
    with open(Path( base_config['repro']['files']['latex_template']), 'r') as f:
        latex_template_content = f.read()

    latex_template_content = replace_config_inserts(latex_template_content)
    
    # make interfim file
    # enusre latex dir exists
    interim_filepath = f'./{reproduce_dir}/tmp/{document_dir}/latex/latex_template_interim.tex'
    os.makedirs(os.path.dirname(Path(interim_filepath)), exist_ok=True)
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

    chunks = extract_chunks(content)
    content = process_chunks(chunks, data_toml)

    with open(f'./{reproduce_dir}/tmp/{document_dir}/latex/latex_template_interim.tex', 'r') as f:
        template = f.read()

    compiled = template.replace('%%@@LOWDOWN_CONTENT@@%%', content)

    # ensure output_file dir exists
    linefile_fullpath = Path(reproduce_dir, 'tmp', output_linefile)
    os.makedirs(os.path.dirname(linefile_fullpath), exist_ok=True)

    print('Replacing \INSERTs with TOML data in main input file')

    print(f'Writing compiled output {linefile_fullpath}')
    with open(linefile_fullpath, 'w') as f:
        f.write(compiled)

    print('Done')