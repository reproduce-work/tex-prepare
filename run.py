import os
from pathlib import Path
import toml
from dotenv import load_dotenv
import json


def get_toml_key(data, key):

    # Check if the key exists
    if key in data:
        # Extract the value
        if 'value' in data[key]:
            value = data[key]['value']
        else:
            value = '\texttt{error with reproduce.work developer}'
        
        # Extract metadata
        metadata = data[key].copy()

        return value, metadata
    else:
        return None, None


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
        replacement_value, metadata = get_toml_key(data, var_name)

        exists = replacement_value is not None
        if exists:
            if metadata is None or 'description' not in metadata:
                metadata_str = ''
            else:
                print(metadata['description'])
                metadata_str = metadata['description']

            # Using \hyperdef and \hyperref to create the "dummy" link
            dummy_link = rf"\hyperlink{{reproduce.work}}{{{replacement_value}}}"
            
            print(f"Replacing {var_name} with {replacement_value}")
            content = content[:start_idx] + dummy_link + content[end_idx + 1:]
            
            start_pos = start_idx + len(dummy_link)
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

        print(var_name, replacement_value)

        print(f"Replacing {var_name} with {replacement_value}")
        content = content[:start_idx] + replacement_value + content[end_idx + 1:]
        start_pos = start_idx + len(replacement_value)

    return content


def run_lowdown(input_file, output_file):
    lowdown_cmd = f'''lowdown -stlatex --parse-no-intraemph --parse-no-super {input_file} | sed -n '/\\\\begin{{document}}/,/\\\\end{{document}}/p' | sed '1d;$d' > {output_file}'''
    print(lowdown_cmd)
    os.system(lowdown_cmd)


def lowdown_postprocess(input_file, output_file):

    # Read input text file
    with open(input_file, 'r') as f:
        content = f.read()

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
            print(f"Replacing {key} with {value}")
            content = content.replace(key, value)

    # Write modified content to output .tex file
    with open(output_file, 'w') as f:
        f.write(content)

if __name__ == '__main__':

    load_dotenv()
    reproduce_dir = os.getenv("REPROWORKDIR")
    output_file = os.getenv("REPROWORKOUTFILE")

    # ensure tmp dir exists
    os.makedirs(f'./{reproduce_dir}/tmp', exist_ok=True)

    #print(os.listdir('/'))
    #print(Path(os.getcwd()))
    #print(reproduce_dir)
    #print(os.listdir(f'{reproduce_dir}'))
    #print(os.listdir(Path(os.getcwd())))

    def read_base_config():
        with open(Path(reproduce_dir, 'config.toml'), 'r') as f:
            data = toml.load(f)
        return data
    base_config = read_base_config()
    
    print('Replacing \INSERTs with TOML data in latex_template file')
    with open(Path( base_config['repro']['files']['latex_template']), 'r') as f:
        latex_template_content = f.read()


    def replace_config_inserts(content):
        #timestamp = base_config['project']['timestamp']
        #tmp_config = { k:{'value': v, 'timestamp': timestamp} for k,v in base_config.items()}
        tmp_config = base_config.copy()
        print(tmp_config)
        content = replace_inserts_in_content_plain(
            content.replace('\\INSERT{config.', '\\INSERT{'),
            tmp_config
        )
        return content

    latex_template_content = replace_config_inserts(latex_template_content)
    
    with open(f'./{reproduce_dir}/tmp/latex_template_interim.tex', 'w') as f:
        f.write(latex_template_content)
    

    print('Replacing \INSERTs with TOML data in main input file')
    # Read input text file
    with open(Path( base_config['repro']['files']['input']), 'r') as f:
        content = f.read()
    with open(Path( base_config['repro']['files']['dynamic']), 'r') as f:  
        data_toml = toml.load(f)

    content = replace_inserts_in_content(content, data_toml)

    with open(f'./{reproduce_dir}/tmp/lowdown_input.md', 'w') as f:
        f.write(content)


    print('Running lowdown')
    run_lowdown(f'./{reproduce_dir}/tmp/lowdown_input.md', f'./{reproduce_dir}/tmp/lowdown_output.tex')

    print('Postprocessing lowdown output')
    lowdown_postprocess(f'./{reproduce_dir}/tmp/lowdown_output.tex', f'./{reproduce_dir}/tmp/lowdown_processed.tex')

    print('Inserting lowdown output into template')
    with open(f'./{reproduce_dir}/tmp/lowdown_processed.tex', 'r') as f:
        content = f.read()

    with open(f'./{reproduce_dir}/tmp/latex_template_interim.tex', 'r') as f:
        template = f.read()

    compiled = template.replace('%%@@LOWDOWN_CONTENT@@%%', content)

    # ensure output_file dir exists
    os.makedirs(os.path.dirname(Path( output_file)), exist_ok=True)

    print(f'Writing compiled output {output_file}')
    with open(Path( output_file), 'w') as f:
        f.write(compiled)

    print('Done')