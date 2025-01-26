"""
Convert synthtabnet dataset into huggingface
"""
import json
import io
import os
import PIL
from tqdm import tqdm
import datasets


ANNOTATION_LOCATION: str # Path to .../synthetic_data.jsonl
TEST_IMAGES_LOCATION: str # Directory containing images
dataset_variant_names = ["fintabnet", "marketing", "pubtabnet", "sparse"]
DATASET_VARIANT = 3
DATASET_NAME = dataset_variant_names[DATASET_VARIANT]

print("Processing", DATASET_NAME)

def regenerate_table_html(json_obj):
    """
    Regenerates an HTML table from a specialized JSON format.
    
    Args:
        json_obj (dict): JSON object containing HTML table information with:
            - html.cells: List of cell objects with tokens and bbox
            - html.structure.tokens: List of HTML structural tokens
    
    Returns:
        str: Reconstructed HTML table string
    """
    cells = json_obj['html']['cells']
    structure_tokens = json_obj['html']['structure']['tokens']
    
    # Initialize variables
    current_cell = 0
    output = []
    
    assert len([x for x in structure_tokens if '<td' in x]) == len(cells), "Mismatch in structure and cell count"
    tokens = iter(structure_tokens)
    for token in tokens:
        if token.startswith('<td'):
            cell_content = ''.join(cells[current_cell]['tokens'])
            output.append(token)

            if token == '<td':
                while token != '>': # colspan is actually split into 3 tokens: "<td", "colspan="x"", ">"
                    token = next(tokens, None)
                    assert token # we shouldn't run out of tokens
                    output.append(token)
            output.append(cell_content)
            current_cell += 1
        else:
            output.append(token)
    
    return ''.join(output)

def to_bboxes_and_words(json_obj):
    cells = json_obj['html']['cells']

    bboxes = []
    words = []
    flags = []
    
    for cell in cells:
        if cell.get('bbox'):
            word = ''.join(cell['tokens'])

            bbox = cell['bbox'][:4]
            flag = cell['bbox'][4]
            bboxes.append(bbox)
            words.append(word)
            flags.append(flag)

    return bboxes, words, flags

def main():


    result = {
        'filename': [],
        'word_bboxes': [],
        'words': [],
        'flag': [],
        'variant': [],
        'html': [],
        'imgid': []
    }

    total_files_estimate = 150000
    with open(ANNOTATION_LOCATION, "r", encoding='utf-8') as f:
        for i, line in enumerate(tqdm(f, total=total_files_estimate)):
            try:
                obj = json.loads(line, strict=False)
            except json.JSONDecodeError:
                # NOTE: jsonl has some invalid json lines
                # ie. "tokens": [" ", ],
                
                # print("Cleanup required for line", i)
                line = line.replace(", ]", "]")
                obj = json.loads(line, strict=False)
            if obj['split'] == 'test':
                filename = os.path.basename(obj['filename'])
                word_bboxes, words, flags = to_bboxes_and_words(obj)
                result['filename'].append(filename)
                result['word_bboxes'].append(word_bboxes)
                result['words'].append(words)
                result['flag'].append(flags)
                result['variant'].append(DATASET_VARIANT)
                result['imgid'].append(obj['imgid'])
                

                html = regenerate_table_html(obj)
                result['html'].append(html)

                # if len(result['filename']) > 100:
                #     break


    df = datasets.Dataset.from_dict(result, split='test')
    df.features['variant'] = datasets.ClassLabel(names=dataset_variant_names)

    # huggingface: load the dataset images
    root = TEST_IMAGES_LOCATION
    df = df.map(lambda x: {'image': PIL.Image.open(os.path.join(root, x['filename']) )})

    df.save_to_disk(f"experiments/synthtabnet_{DATASET_NAME}_test")

if __name__ == "__main__":
    main()