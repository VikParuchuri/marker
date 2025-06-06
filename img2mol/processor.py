from operator import truediv
import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
import sys

main_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# print("main_dir", main_dir)
sys.path.append(main_dir)

## 关闭yolo的打印
os.environ['YOLO_VERBOSE'] = str(False)

import io
import cairosvg
import base64
import json
import math
import numpy as np
import torch
import easyocr
import logging
import pytesseract
import PIL
from PIL import Image, ImageDraw, ImageFont
import cv2
from img2table import document
import layoutparser as lp
import PyPDF2

from pdf2image import convert_from_path ## 从pdf抽取图片的工具
from script.image_utils import crop_image ## 对专利图片进行裁剪
from script.image_utils import judge_patent ## 判断是不是专利
from script.image_utils import rotate_bound ## 旋转
from script.image_utils import read_image ## 读取
from script.image_utils import rotate_coordinates
from script.image_utils import pad_image
from script.image_utils import is_blank_image
from script.utils import get_file_name ## 获取文档名字
from script.utils import get_pair_prediction_from_moldetect
from script.utils import get_prediction_from_moldetect
from script.utils import get_prediction_from_moldetect_V2
from script.utils import merge_molecule_box
from script.utils import merge_molecule_label_box
from script.utils import get_previous_rotation_box
from script.table_utils import get_text_box_dict
from script.table_utils import get_text_box_dict_with_paddleocr
from script.table_utils import get_text_box_dict_with_easyocr
from script.table_utils import get_line_box_dict_with_easyocr
from script.table_utils import get_pytesseract_ocr_result
from script.table_utils import ocr_precessing
from script.table_utils import remove_upprintable_chars
from script.table_utils import merge_header_and_get_new_table, merge_header_and_get_new_table_v2
from script.table_utils import compress_spaces, compress_n
from script.mol_utils import remove_quation_in_molblcok
from script.mol_utils import get_candidate_concat_atom
from script.mol_utils import remove_quatation_in_alais
from script.image_utils import nms_without_confidence
from script.image_utils import remove_horizontal_and_vertical_line
from script.image_utils import crop_v2
from script.image_utils import remove_gray
from script.mol_utils import add_quotation_mark_to_mol_block, assign_e_to_unsigned_bond, add_r_in_mol, set_atom_alais
from script.expand_mol_util import expand_mol
from script.vis_utils import vis_mol
from script.html_utils import single_page_molecule_result_to_html, single_page_table_result_to_html
from script.html_utils import get_border_html
from script.mol_utils import assign_right_bond_stero_to_molblock
from script.image_utils import image_to_base64, base64_to_image
from typing import Any, Dict, ItemsView, List, Tuple, Optional
import pandas as pd
import copy
from collections import OrderedDict
from tqdm import tqdm
import ipdb
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning, message="__floordiv__ is deprecated")
warnings.filterwarnings("ignore", category=UserWarning, message="torch.meshgrid")

from script.ImageRecognize.scripts.img2mol.evaluation_ensemble import run_task
from script.ImageRecognize.scripts.img2mol.evaluation_ensemble import _expand_functional_group_v2 as _expand_functional_group
from collections import OrderedDict

from script.rxn_detection import MolDetect_rewrite ## 分子目标检测
import multiprocessing as mp
from script.ImageRecognize.scripts.img2mol.augment import SafeRotate, CropWhite, PadWhite, SaltAndPepperNoise
from script.ImageRecognize.scripts.img2table.infer import main as table_infer
import albumentations as A
from albumentations.pytorch import ToTensorV2
import time
from rdkit import Chem
from rdkit.Chem import AllChem
from rdkit.Geometry import Point3D
from transformers import TrOCRProcessor, VisionEncoderDecoderModel
from transformers import VisionEncoderDecoderConfig
from transformers import RobertaTokenizerFast, GenerationConfig
from transformers import AutoModel, AutoTokenizer
import re
from script.merge_page import merge_pages as merge_page_fn

## 表格相关
from layoutparser.elements import TextBlock, Rectangle, Layout

try:
    from doctr.models import ocr_predictor
    from doctr.models.predictor import OCRPredictor
    from doctr.io import DocumentFile
except Exception as e:
    print("`doctr` isn't installed")

## table
from img2table.tables.objects.extraction import ExtractedTable, BBox
from transformers import TrOCRProcessor
from optimum.onnxruntime import ORTModelForVision2Seq

from script.img2latex.postprocess import to_katex, latex2text, remove_last_tiny, remove_into_first_end
from script.img2latex.infer import infer_fn
from script.img2latex.model import TexTeller
from script.utils import calculate_center, calculate_distance

# from script.text_utils import split_content

from bs4 import BeautifulSoup

import xml.etree.ElementTree as ET
import fitz

try:
    from ultralytics import YOLO
except Exception as e:
    print(e)

import uuid

## 二维排序
from script.sort_box import sort_box_fn

from rdkit.Chem import PandasTools
## 关闭rdkit的日志
from rdkit import RDLogger
RDLogger.DisableLog('rdApp.*')

try:
    from script.sar_utils import process_sar as _process_sar
except Exception as e:
    print("sar is not available")
    print(e)
import collections
from rdkit.Chem import rdRGroupDecomposition
from sklearn.linear_model import Ridge

pre_table_html = "<!DOCTYPE html><html><head><title>head</title><style>table {border-collapse: collapse;width: 100%;}th, td {border: 1px solid black;padding: 8px;text-align: center;} </style></head><body><table>"
post_table_html = "</table></body></html>"

def setup_applevel_logger(logger_name = "", file_name=None): 
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO) ##对dug的过滤
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(formatter)
    # logger.handlers.clear()
    logger.addHandler(sh)
    if file_name:
        fh = logging.FileHandler(file_name)
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    return logger

color_list_1 = ['red', 'blue', 'green', 'magenta', "purple"]
color_map = {
'Text': 'red',
'Title': 'blue',
'List': 'green',
'Table': 'purple',
'Figure': 'pink',
}

def split_content(text):
    # 匹配数字部分和括号部分
    # (.*?):
    # .* 匹配任意字符（除了换行符）0次或多次。
    # ? 是一个量词，表示尽可能少地匹配（非贪婪模式），即匹配到第一个符合后续条件的字符为止。
    # 括号 () 表示这是一个捕获组，将匹配的内容提取出来。

    # (\(\w+\))$:
    # \( 和 \):
    # 匹配字面意义上的括号。
    # .*?:
    # . 匹配任意字符（除了换行符）。
    # * 表示前面的元素（任意字符）可以出现零次或多次。
    # ? 将其设置为非贪婪模式，意味着它会尽可能少地匹配字符，直到找到第一个符合后续条件的括号结束。
    # 整个模式被括号包围 ():
    # 表示这是一个捕获组，将匹配的内容提取出来。

    match = re.match(r'^(.*?)(\(.*?\))$', text)
    if match:
        return match.group(1).strip(), match.group(2)  # 返回两个部分
    return text, None  # 如果没有匹配，返回原文本和None
    
# def extract_ic50(text):
#     # 使用正则表达式提取前缀和所有的 IC50 值
#     matches = re.findall(r'(\w+|\s+)[\s:|\s,]*IC50\s*=\s*(\d+(\.\d+)?)', " "+text)
    
#     # 用于存储分组结果
#     # groups = defaultdict(list)
    
#     groups_list = []
#     for match in matches:
#         prefix = match[0]  # 提取前缀
#         ic50_value = f"IC50={match[1]} μM"  # 格式化 IC50 值
#         # groups[prefix].append(ic50_value)  # 将 IC50 值添加到对应的前缀组中
#         groups_list.append((prefix, ic50_value))

#     return groups_list  # 返回字典形式的分组结果


def is_number_or_roman_with_parentheses(s):
    # 正则表达式：允许可选的括号，纯数字或罗马数字后可选的字母，并允许'-'
    pattern = r'^\s*\(?(?:\d+|[IVXLCDM]+)([A-Za-z-]*)\)?\s*$'
    return bool(re.match(pattern, s))

def split_ic50(text):
    # 使用正则表达式提取 IC50 前后的部分
    match = re.match(r'(.*?)\s*(IC50\s*[:=]\s*\S*\s*\S*)', text)
    
    if match:
        # 返回提取的部分
        return match.group(1).strip(), match.group(2)
    else:
        return "", ""

def extract_intermediate(text):
    pattern = r'\b(?:Intermediate|intermediate|INTERMEDIATE)\s*\(?([^()]*?)\)?\s*([^\s]+)'
    matches = re.findall(pattern, text)
    matches = list(matches)
    for temp_i, match in enumerate(matches):
        matches[temp_i] = list(match)
        if matches[temp_i][-1][-1]==")":
            matches[temp_i][-1] = "(" + matches[temp_i][-1]
    return matches
    
def extract_formula(text):
    pattern = r'\b(?:formula|Formula|Formular|formular|FORMULA|FORMULAR)\s*\(?([^()]*?)\)?\s*([^\s]+)'
    matches = re.findall(pattern, text)
    matches = list(matches)
    for temp_i, match in enumerate(matches):
        matches[temp_i] = list(match)
        if matches[temp_i][-1][-1]==")":
            matches[temp_i][-1] = "(" + matches[temp_i][-1]
    return matches

def extract_compound(text):
    pattern = r'\b(?:compound|COMPOUND|Compound)\s*\(?([^()]*?)\)?\s*([^\s]+)'
    matches = re.findall(pattern, text)
    matches = list(matches)
    for temp_i, match in enumerate(matches):
        matches[temp_i] = list(match)
        if matches[temp_i][-1][-1]==")":
            matches[temp_i][-1] = "(" + matches[temp_i][-1]
    return matches

def extract_example(text):
    pattern = r'\b(?:example|EXAMPLE|Example)\s*\(?([^()]*?)\)?\s*([^\s]+)'
    matches = re.findall(pattern, text)
    matches = list(matches)
    for temp_i, match in enumerate(matches):
        matches[temp_i] = list(match)
        if matches[temp_i][-1][-1]==")":
            matches[temp_i][-1] = "(" + matches[temp_i][-1]
    return matches

def extract_shishili(text):
    pattern = r'\b(?:实施例|实例)\s*\(?([^()]*?)\)?\s*([^\s]+)'
    matches = re.findall(pattern, text)
    matches = list(matches)
    for temp_i, match in enumerate(matches):
        matches[temp_i] = list(match)
        if matches[temp_i][-1][-1]==")":
            matches[temp_i][-1] = "(" + matches[temp_i][-1]
    return matches

def extract_example_v2(text):
    if ("example" not in text) and ("EXAMPLE" not in text) and ("Example" not in text):
        return text

    pattern = r'\b(?:example|EXAMPLE|Example)\s*\(?([^()]*?)\)?\s*([^\s]+)'
    matches = re.findall(pattern, text)
    matches = list(matches)
    
    for temp_i, match in enumerate(matches):
        # 将匹配的单词加回去
        example_word = re.search(r'\b(?:example|EXAMPLE|Example)', text).group(0)
        matches[temp_i] = [example_word] + list(match)[1:]
        
        # 检查最后一个元素是否有右括号，并进行处理
        if matches[temp_i][-1][-1] == ")":
            matches[temp_i][-1] = "(" + matches[temp_i][-1]
    
    return matches[0][0] + " " + matches[0][1]

def extract_chiese_shi(text):
    pattern = r'\b(?:式|通式)\s*\(?([^()]*?)\)?\s*([^\s]+)'
    matches = re.findall(pattern, text)
    matches = list(matches)
    for temp_i, match in enumerate(matches):
        matches[temp_i] = list(match)
        if matches[temp_i][-1][-1]==")":
            matches[temp_i][-1] = "(" + matches[temp_i][-1]
    return matches

def extract_huahewu(text):
    pattern = r'\b(?:化合物)\s*\(?([^()]*?)\)?\s*([^\s]+)'
    matches = re.findall(pattern, text)
    matches = list(matches)
    for temp_i, match in enumerate(matches):
        matches[temp_i] = list(match)
        if matches[temp_i][-1][-1]==")":
            matches[temp_i][-1] = "(" + matches[temp_i][-1]
    return matches

def extract_zhongjianti(text):
    pattern = r'\b(?:中间体)\s*\(?([^()]*?)\)?\s*([^\s]+)'
    matches = re.findall(pattern, text)
    matches = list(matches)
    for temp_i, match in enumerate(matches):
        matches[temp_i] = list(match)
        if matches[temp_i][-1][-1]==")":
            matches[temp_i][-1] = "(" + matches[temp_i][-1]
    return matches

def remove_newlines_and_spaces(text):
    # 替换换行符和0个或多个空格为一个空字符串
    cleaned_text = re.sub(r'\s*\n\s*', '', text)
    return cleaned_text

def add_space_in_text_fn(text):
    if len(text) <= 12:
        try:
            # 匹配以指定关键字开头的字符串，后面跟任意字符
            pattern = r'^\s*(example|EXAMPLE|Example|中间体|化合物|compound|COMPOUND|Compound|Intermediate|intermediate|INTERMEDIATE|formula|Formula|Formular|formular|FORMULA|FORMULAR|实施例|实例|式|通式)\s*(.*)'
            
            matches = re.findall(pattern, text)
            
            if len(matches) > 0:
                # 处理匹配结果
                results = []
                for match in matches:
                    keyword = match[0]  # 保留匹配的关键字
                    additional_text = match[1]  # 获取所有后续字符
                    results.append((keyword, additional_text.strip()))  # 去掉首尾空格
                
                temp_result = list(results[0])
                return " ".join(temp_result)  # 返回结果
                
            else:
                return text  # 如果没有匹配，返回原文本
        except Exception as e:
            print(e)
            return text
    else:
        return text  # 如果文本长度超过 12，返回原文本

    



def extract_ic50_with_prefix(text):
    # 使用正则表达式提取前缀和 IC50 值
    matches = re.findall(r'([\S\s]+?)(IC50\s*[:=]\s*\d+(\.\d+)?\s*[μu]M|IC50\s*[:=]\s*\d+(\.\d+)?\s*nM)', " "+text)
    
    # 提取前缀和 IC50 值
    results = [f"{match[0].strip()} {match[1]}" for match in matches]

    for i in range(len(results)):
        results[i] = split_ic50(results[i])
    
    return results

def extract_rgroups_fn(text):
    # 使用正则表达式匹配各个字段，包括冒号
    pattern = r'([A-Za-z]\d*\s*=\s*\S+|[A-Za-z]\s*=\s*\S+|[A-Za-z]\d*\s*:\s*\S+|[A-Za-z]\s*:\s*\S+|\S+)'
    matches = re.findall(pattern, text)

    # 返回去除空字符串的结果
    return [match.strip() for match in matches if match.strip()]

def extract_rgroup(text):
    results = extract_rgroups_fn(text)
    rgroup_list = []
    index_list = []
    
    for result in results:
        if "=" in result or ":" in result:
            # 如果包含冒号或等号，进一步分割
            if ":" in result:
                index, rgroup = result.split(":", 1)
                index_list.append(index.strip())
                rgroup_list.append(rgroup.strip())
            else:
                rgroup_list.append(result)
        else:
            index_list.append(result)
    
    return ";".join(index_list), ";".join(rgroup_list)


def is_valid_numeric_string(input_string):
    # 检查字符串是否为纯数字
    if input_string.isdigit():
        # 检查长度是否超过 8 个字符
        if len(input_string) > 8:
            return False
        return True
    else:
        return True


def custom_sort_key(item):
    return (item[1], item[0])

def get_contour_precedence(box, width):
    x1, y1, x2, y2 = box
    tolerance_factor = 10
    return (((y1*3+y2) // tolerance_factor) * tolerance_factor) * width + (x1*3+x2)

def get_contour_precedence_V2(box, tolerance_factor, min_height_center=0):
    x1, y1, x2, y2 = box 
    return ((y1 + y2) //2 - min_height_center) // tolerance_factor * tolerance_factor


def get_condition(out):
    return (out=="lim" or \
            out =="F" or \
            out == "T" or \
            out == "T") or \
            ("!" in out) or \
            get_condition_v2(out) or\
            ("γ" in out) or \
            "width" in out or \
            "height" in out or \
            "box" in out or \
            "λ" in out or\
            "@cite" in out or "cite@" in out or\
            "@bibref" in out or \
            "崇" in out or \
            "⊞" in out or \
            "卯" in out or \
            "叩" in out or \
            "刀" in out or\
            "∅" in out or \
            ("}" in out and "{" not in out) or \
            "晴" in out or \
            "冗" in out or \
            out == "array" or \
            "μ \nμ" in out or \
            out == "日" or \
            out == "y > 5" or \
            out == " - 1/  1-(x-a)2/1-a2" or \
            out == "亩" or \
            "已" in out or \
            "目" in out or \
            out == "n+2/n" or \
            out == "[ NT\n \n ]" or \
            out == "1+" or \
            out == r"%s" or \
            out == "竹" or \
            "晌" in out
            

def get_condition_v2(out):
    return (out=="" or \
            "∑" in out or \
            "∏" in out or \
            "Π" in out or \
            "⊔" in out or \
            "ψ" in out or \
            "⊓" in out or \
            "⟹" in out or\
            "∫" in out or \
            "Ψ" in out or \
            "χ" in out or \
            "∪" in out or \
            "⋂" in out or \
            "↔" in out or \
            "∇" in out or \
            "ω" in out or \
            "ε" in out or \
            "∃" in out or \
            "θ" in out or \
            "Θ" in out or \
            "÷" in out or \
            "⟹" in out or \
            "⊗" in out or \
            "∞" in out or \
            "∠" in out or \
            "⋀" in out or \
            "⊠" in out or \
            "Ξ" in out or \
            "∩" in out or \
            "U.U" in out or \
            "U.J" in out or \
            "1010101010" in out or\
            "χ" in out or \
            "00000000000000000000000000000000" in out or \
            "···...····...··...·...···: ·, ··= ·......·" in out or \
            "33333333" in out or \
            "∓" in out or\
            "∓∓∓∓∓∓∓∓∓" in out or\
            "mam mam" in out or \
            "[]  -  0" in out or \
            "⊙" in out or \
            "∴" in out or \
            "∉" in out or \
            "1 ,    11" in out or \
            "1.226378 pt" in out or \
            " pt" in out or \
            (len(out)>=3 and out[-3:]=="tan") or \
            "( \n \n \n \n \n \n \n \n \n \n \n \n \n \n)" in out or \
            "mumumumumu" in out or \
            "gengengengengen" in out or \
            "c]cc0000000" in out or\
            "⟶" in out or \
            "π" in out or\
            "♯" in out or \
            "ς" in out or \
            "↑" in out or \
            "↓" in out or \
            "⊥" in out or \
            "Zo" in out or \
            "±cos" in out or \
            "Φ" in out or \
            "Sim" == out or \
            "( \n \n \n \n \n \n \n \n \n \n \n \n \n \n)" in out or \
            "mumumumumu" in out or \
            "gengengengengen" in out or \
            "c]cc0000000" in out or\
            "⟶" in out or \
            "π" in out or\
            "♯" in out or \
            "ς" in out or \
            "↑" in out or \
            "↓" in out or \
            "ormen ormen" in out or \
            "sinh sinh" in out or \
            "onononononononon" in out or \
            "tanentanen" in out or \
            "12(1,0)(1,0)" in out or \
            "( \n \n \n \n \n \n \n \n \n \n)" in out or \
            "⇌" in out or \
            "↙" in out or \
            out == "∼" or \
            out == "ΔnΔnΔnΔn" or \
            out == "62 62 62 62" or \
            "∓∓∓∓∓∓∓∓∓" in out or \
            "(1,0)(1,0)1(1,0)(1,0)1" in out or \
            "ΔΔΔ" in out or\
            "⊂" in out or \
            out == "↷" or \
            "⋂" in out or \
            "Γ" in out or \
            "×3 ×3 ×3 ×3" in out or \
            "▴" in out or \
            "⋔" in out or \
            "†" in out or \
            "weatweatweat" in out or \
            "†" in out or \
            out == "... ... ... ...\n ... ...\n ... ...\n ... ...\n ... ...\n ... ..." or \
            "0.5mm0.5mm" in out or \
            "5μ5μ5μ5μ5μ5μ5μ5μ5μ" in out or \
            "0.3cot0.3cot" in out or \
            "wherwestrestres" in out or \
            "10[0,0]10[0,0]10[0,0]" in out or \
            out == "}" or \
            "⊕" in out or \
            "dmodmodmo" in out or \
            "1/21/21/21/2" in out or \
            "μμμμμμμμμμμμμμ" in out or \
            "tiontiontion" in out or \
            "15mm15mm" in out or \
            "1m15mm1m15mm" in out or \
            "domdom" in out or \
            "γ  γ  γ" in out or \
            "..." in out or \
            "nu    lambda" in out or \
            "⊃" in out or \
            "∃" in out or \
            "η" in out or \
            "¬" in out or \
            "�" in out or \
            "⟵" in out or \
            "Σ" in out or \
            "Σ" in out or \
            "⋆" in out or \
            "CiCjHj" in out or \
            "⊺" in out \
            )

## TODO:测试
def refine_table(table, image):
    try:
        table_box = (
                    max(table.bbox.x1-5, 0),
                    max(table.bbox.y1-5, 0),
                    max(table.bbox.x2+5, image.width),
                    max(table.bbox.y2+5, image.height),
                    )
        table_image = image.crop(table_box)
        from script.image_utils import dash_line_2_border_line
        table_image = dash_line_2_border_line(table_image)
        # 将图像保存在io.BytesIO中
        table_image_io = io.BytesIO()
        table_image.save(table_image_io, format='PNG')
        table_image_io.seek(0)  # 这将让你可以从io.BytesIO对象的开始处读取数据

        ## 抽取表格
        table_img = document.Image(src=table_image_io)
        table_extracted_tables = table_img.extract_tables()
        ## 保证只有一个分子，且行数多余原来的表格
        if len(table_extracted_tables) == 1 and table_extracted_tables[0].df.shape[0]>table.df.shape[0]:
            table_extracted_tables[0].bbox.x1 = table_extracted_tables[0].bbox.x1 + max(table.bbox.x1-5, 0)
            table_extracted_tables[0].bbox.y1 = table_extracted_tables[0].bbox.y1 + max(table.bbox.y1-5, 0)
            table_extracted_tables[0].bbox.x2 = table_extracted_tables[0].bbox.x2 + max(table.bbox.x1-5, 0)
            table_extracted_tables[0].bbox.y2 = table_extracted_tables[0].bbox.y2 + max(table.bbox.y1-5, 0)
            for row in table_extracted_tables[0].content.values():
                for cell_idx, cell in enumerate(row):
                    ## 去除空的cell
                    cell.bbox.x1 += max(table.bbox.x1-5, 0)
                    cell.bbox.y1 += max(table.bbox.y1-5, 0)
                    cell.bbox.x2 += max(table.bbox.x1-5, 0)
                    cell.bbox.y2 += max(table.bbox.y1-5, 0)

            return table_extracted_tables[0]
        else:
            return table
    except:
        return table


class Parser_Processer(object):
    def __init__(self,
            device="cuda",
            model_dir = None,
            MolDetect_mol_path:str=None,
            lp_config_path:str=None,
            lp_model_path:str=None,
            with_layout_parser:bool=False,
            td_config_path:str=None,
            td_model_path:str=None,
            with_mol_detect:bool=True,
            with_table_detect:bool=True,
            debug=False,
            num_workers=1,
            padding:int = 0,
            with_two_detect_model:bool = False,
            with_trocr:bool=False,
            new_class_token:bool=True,
            with_doctr:bool=False,
            use_yolo_mol_model:bool=True,
            use_yolo_table_model:bool=True,
            use_yolo_table_model_v2:bool=True,
            use_trocr_mfr_model:bool=False,
            use_trocr_mfr_model_v2:bool=False,
            use_trocr_mfr_model_v3:bool=True,
            use_got_ocr_model:bool=True,
            use_ofa_model:bool=False,
            preload_table_and_ocr_model:bool=False
            ):
        logger_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"log/log.log")
        os.makedirs(os.path.dirname(logger_file_path), exist_ok=True)
        self.logger = setup_applevel_logger(file_name=logger_file_path)

        ## add parameters to self
        ## 添加参数
        self.device = device
        self.MolDetect_mol_path = MolDetect_mol_path
        self.lp_config_path = lp_config_path
        self.lp_model_path = lp_model_path
        self.with_layout_parser = with_layout_parser
        self.with_mol_detect = with_mol_detect
        self.with_table_detect = with_table_detect
        self.debug = debug
        self.num_workers = num_workers
        self.padding = padding
        self.with_two_detect_model = with_two_detect_model
        self.with_trocr = with_trocr
        self.new_class_token = new_class_token
        self.with_doctr = with_doctr
        self.use_yolo_mol_model = use_yolo_mol_model
        self.use_yolo_table_model = use_yolo_table_model
        self.use_yolo_table_model_v2 = use_yolo_table_model_v2
        self.use_trocr_mfr_model = use_trocr_mfr_model
        self.use_trocr_mfr_model_v2 = use_trocr_mfr_model_v2
        self.use_trocr_mfr_model_v3 = use_trocr_mfr_model_v3
        self.use_got_ocr_model = use_got_ocr_model
        self.use_ofa_model = use_ofa_model
        self.preload_table_and_ocr_model = preload_table_and_ocr_model


        if debug is True:
            self.num_workers == 1

        if model_dir is None:
            self.model_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.logger.info(f"======using default `model_dir`:{self.model_dir}======")
        else:
            self.model_dir = model_dir
            self.logger.info(f"======get `model_dir`:{self.model_dir}======")


        self.new_class_token = new_class_token
        ## 分子检测模型
        if self.with_mol_detect:
            self.moldetect_model = self.get_MolDetect_mol(MolDetect_mol_path, 
                                                        device=device, 
                                                        input_size=1000, 
                                                        new_class_token=self.new_class_token)
            ## 0312 不需要两个分子
            if with_two_detect_model:
                self.moldetect_model_2 = self.get_MolDetect_mol(os.path.join(self.model_dir, "checkpoints/MolDetect/checkpoints/0529_best_v18.ckpt"), 
                                                                device=device,
                                                                input_size=1000,
                                                                new_class_token=self.new_class_token)
            else:
                self.moldetect_model_2 = None
        else:
            self.moldetect_model = None
            self.moldetect_model_2 = None
        
        if self.use_yolo_mol_model:
            self.yolo_mol_model = self.get_yolo_mol_model(device=device)
        else:
            self.yolo_mol_model = None
        
        self.layout_augment = False
        
        if self.with_trocr is False:
            self.easy_ocrer = self.get_easyocer()
            self.trocr = None
            self.trocr_processor = None
        else:
            self.easy_ocrer = None
            self.trocr, self.trocr_processor = self.get_trocr()
        
        self.lp_config_path = lp_config_path
        self.lp_model_path = lp_model_path
        if self.with_layout_parser:
            self.layout_parser = self.get_layout_parser()
        else:
            self.layout_parser = None
        
        self.td_config_path = td_config_path
        self.td_model_path = td_model_path

        if self.with_table_detect:
            if self.preload_table_and_ocr_model:
                if self.use_yolo_table_model:
                    self.yolo_table_model = self.get_yolo_table_model(device=device)
                    self.table_detector = None
                else:
                    self.table_detector = self.get_table_detector(device=device)
                    self.yolo_table_model = None
            else:
                self.table_detector = None
                self.yolo_table_model = None
        

            if self.use_yolo_table_model_v2:
                if self.preload_table_and_ocr_model:
                    self.yolo_table_model_v2 = self.get_yolo_table_model(os.path.join(self.model_dir, "checkpoints", "yolo_table/yolo_table_best_1000k.pt"), 
                                                                     device=device)
                else:
                    self.yolo_table_model_v2 = None

            else:
                self.yolo_table_model_v2 = None
        
        else:
            self.yolo_table_model = None
            self.yolo_table_model_v2 = None
            self.table_detector = None

        self.num_workers = num_workers
        self.crop_white_fn = self.transforms_fn(padding)
        self.crop_white_fn_4_table = self.transforms_fn(padding+10)

        self.debug = debug

        self.with_doctr = with_doctr
        if self.with_doctr:
            if self.preload_table_and_ocr_model:
                self.doctr_model = self.get_doctr_model()
            else:
                self.doctr_model = None
        else:
            self.doctr_model = None
        
        if use_trocr_mfr_model:
            if self.preload_table_and_ocr_model:
                self.trocr_mfr_model, self.trocr_mfr_processor = self.get_trocr_mfr_model()
            else:
                self.trocr_mfr_model, self.trocr_mfr_processor = None, None
        else:
            self.trocr_mfr_model, self.trocr_mfr_processor = None, None
        
        if use_trocr_mfr_model_v2:
            if self.preload_table_and_ocr_model:
                self.trocr_mfr_model_v2, self.trocr_mfr_processor_v2, self.trocr_mfr_transform_v2 = self.get_trocr_mfr_model_v2()
            else:
                self.trocr_mfr_model_v2, self.trocr_mfr_processor_v2, self.trocr_mfr_transform_v2 = None, None, None,
        else:
            self.trocr_mfr_model_v2, self.trocr_mfr_processor_v2, self.trocr_mfr_transform_v2 = None, None, None,

        if self.use_trocr_mfr_model_v3:
            if self.preload_table_and_ocr_model:
                self.trocr_mfr_model_v3, self.trocr_mfr_processor_v3 = self.get_trocr_mfr_model_v3()
            else:
                self.trocr_mfr_model_v3, self.trocr_mfr_processor_v3 = None, None,
        else:
            self.trocr_mfr_model_v3, self.trocr_mfr_processor_v3 = None, None,

        if use_ofa_model:
            self.ofa_model = self.get_ofa_model()
        else:
            self.ofa_model = None
        
        if self.use_got_ocr_model:
            if self.preload_table_and_ocr_model:
                self.got_ocr_model, self.got_ocr_tokenizer = self.get_got_ocr_model()
            else:
                self.got_ocr_model, self.got_ocr_tokenizer = None, None,

        else:
            self.got_ocr_model, self.got_ocr_tokenizer = None, None,

        ## add 0331
        self.prepage = {
            "file_name":"",
            "page_idx":0,
            "image":None,
            "pre_info":{}
        }


    def get_MolDetect_mol(self, MolDetect_mol_path=None, device="cpu", input_size=1000, coref=True, new_class_token=True):
        ## 0312修改
        if (MolDetect_mol_path is None) or (os.path.exists(MolDetect_mol_path) is False):
            MolDetect_mol_path = os.path.join(self.model_dir, "checkpoints/MolDetect/checkpoints/Moldetect_0402_95.ckpt") #0529_last_v18_0611.ckpt
        moldetect_model = MolDetect_rewrite(MolDetect_mol_path, device=device, input_size=input_size, coref=coref, new_class_token=new_class_token)
        self.logger.info("======Get `moldetect` model======")
        return moldetect_model
    
    def get_layout_parser(self):
        if (self.lp_config_path is None) or (os.path.exists(self.lp_config_path) is False):
            self.lp_config_path = os.path.join(self.model_dir, "checkpoints/layoutparser/checkpoints/config/mask_rcnn_X_101_32x8d_FPN_3x_config.yaml")

        if (self.lp_model_path is None) or (os.path.exists(self.lp_model_path) is False):
            self.lp_model_path = os.path.join(self.model_dir, "checkpoints/layoutparser/checkpoints/model/mask_rcnn_X_101_32x8d_FPN_3x_model_final.pth")

        lp_model = lp.Detectron2LayoutModel(
            # config_path ='lp://PubLayNet/mask_rcnn_X_101_32x8d_FPN_3x/config', # In model catalog
            config_path = self.lp_config_path, #'lp://PubLayNet/mask_rcnn_X_101_32x8d_FPN_3x/config', # In model catalog #
            model_path = self.lp_model_path,
            device = self.device,
            label_map = {0: "Text", 1: "Title", 2: "List", 3:"Table", 4:"Figure", 5:"none"}, # In model`label_map`
            extra_config=["MODEL.ROI_HEADS.SCORE_THRESH_TEST", 0.8], # Optional
            )
        self.logger.info("======Get `layout_parser` model======")
        return lp_model

    def get_table_detector(self, device):
        if (self.td_config_path is None) or (os.path.exists(self.td_config_path) is False):
            self.td_config_path = os.path.join(self.model_dir, "checkpoints/layoutparser/checkpoints/config/faster_rcnn_R_101_FPN_3x_table.yaml")

        if (self.td_model_path is None) or (os.path.exists(self.td_model_path) is False):
            self.td_model_path = os.path.join(self.model_dir, "checkpoints/layoutparser/checkpoints/model/faster_rcnn_R_101_FPN_3x_table_model_final.pth")
        td_model = lp.Detectron2LayoutModel(
            config_path = self.td_config_path,
            model_path = self.td_model_path,
            device = self.device,
            label_map = {0: "Table"}, # In model`label_map`
            extra_config=["MODEL.ROI_HEADS.SCORE_THRESH_TEST", 0.7], # Optional
            ).to(device)
        self.logger.info("======Get `table_detector_parser` model======")
        return td_model
    
    def get_easyocer(self):
        easy_ocrer = easyocr.Reader(['en'], gpu=True) #"ch_sim"
        return easy_ocrer
    
    ## TODO change root
    def get_trocr(self):
        # processor = TrOCRProcessor.from_pretrained('microsoft/trocr-small-printed')
        # model = VisionEncoderDecoderModel.from_pretrained('microsoft/trocr-small-printed').to(self.device)
        processor = TrOCRProcessor.from_pretrained(os.path.join(self.model_dir, "checkpoints/trocr-base-stage1")) # #trocr-small-printed #trocr-base-stage1 #trocr-base-stage1
        model = VisionEncoderDecoderModel.from_pretrained(os.path.join(self.model_dir, "checkpoints/trocr-base-stage1")).to(self.device) #trocr-small-printed #trocr-base-stage1 #trocr-base-stage1
        return model, processor

    def get_trocr_result(self, image):
        """
        :param image: PIL Image.
    
        Returns:
            generated_text: the OCR'd text string.
        """
        # We can directly perform OCR on cropped images.
        pixel_values = self.trocr_processor(image, return_tensors='pt').pixel_values.to(self.device)
        generated_ids = self.trocr.generate(pixel_values)
        generated_text = self.trocr_processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
        return generated_text

    def get_trocr_mfr_model(self):
        try:
            processor = TrOCRProcessor.from_pretrained(os.path.join(self.model_dir, "checkpoints/pix2text-mfr/checkpoints"))
            model = ORTModelForVision2Seq.from_pretrained(os.path.join(self.model_dir, "checkpoints/pix2text-mfr/checkpoints"), use_cache=False)
            model = model.to(self.device)
            self.logger.info("======Get `trocr_mfr` model======")
            return model, processor
        except Exception as e:
            print(e)
            return None, None
    
    def get_trocr_mfr_result(self, image):
        images = [image]
        pixel_values = self.trocr_mfr_processor(images=images, return_tensors="pt").pixel_values.to(self.device)
        generated_ids =  self.trocr_mfr_model.generate(pixel_values)
        with torch.no_grad():
            generated_text = self.trocr_mfr_processor.batch_decode(generated_ids, skip_special_tokens=True)
        # if generated_text[0][:6] == "\\fbox ":
        #     generated_text[0] = generated_text[0][6:]
        # if generated_text[0][:7] == "\\boxed ":
        #     generated_text[0] = generated_text[0][7:]
        result = generated_text[0].lstrip(r"^ ").replace(r"\\hline ","")
        result = result.rstrip("\n")
        result = result.lstrip("\n")
        result = result.rstrip(" ")
        result = result.lstrip(" ")
        result = compress_spaces(result)
        
        return result
    
    def get_trocr_mfr_model_v3(self, model_dir:str=None):
        try:
            if model_dir is None or os.path.exists(model_dir) is False:
                model_dir = os.path.join(self.model_dir, "checkpoints/TexTeller/checkpoints")
            TexTeller_obj = TexTeller(model_dir=model_dir)
            latex_rec_model = TexTeller_obj.from_pretrained(use_onnx=True,onnx_provider="cuda").to(self.device)
            tokenizer = TexTeller_obj.get_tokenizer()
            self.logger.info("======Get `trocr_mfr_v3` model======")
            return latex_rec_model, tokenizer
        except Exception as e:
            print(e)
            return None, None
    
    def _get_trocr_mfr_result_v3(self, image, with_crop_white=True, num_beams=1, num_no_repeat=-1):
        if self.trocr_mfr_model_v3 is not None:
            result = infer_fn(self.trocr_mfr_model_v3,
                            self.trocr_mfr_processor_v3,
                            [image], 
                            self.device,
                            num_beams = num_beams,
                            num_no_repeat = num_no_repeat,
                            with_crop_white=with_crop_white)
            return result
        else:
            return "", True


    def get_trocr_mfr_result_v3(self, image, with_crop_white=True, num_beams=1, num_no_repeat=-1):
        image = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)
        out, state = self._get_trocr_mfr_result_v3(image, with_crop_white, num_beams, num_no_repeat)
        out_plain_data = latex2text(to_katex(out))

        Flag = False
        if len(out)>=100:
            Flag = True
        
        if "pt0." in out_plain_data or "0pt" in out_plain_data :
            Flag = True
        
        if Flag:
            # self.logger.info(f"predict again!!! out:{out}, out_plain_data:{out_plain_data}")
            out, state = self._get_trocr_mfr_result_v3(image, num_beams=3, num_no_repeat=3)
        
        return out, state

    
    def get_trocr_mfr_model_v2(self):
        try:
            image_processor = TrOCRProcessor.from_pretrained(os.path.join(self.model_dir, "checkpoints/pix2text-mfr_torch_1500k/checkpoints"))
            with open(os.path.join(self.model_dir, "checkpoints/pix2text-mfr_torch_1500k/checkpoints/config.json"), "r") as f:
                config_dict = json.load(f)
            config = VisionEncoderDecoderConfig(**config_dict)

            model = VisionEncoderDecoderModel(config=config)
            model.config.decoder_start_token_id = image_processor.tokenizer.cls_token_id
            model.config.pad_token_id = image_processor.tokenizer.pad_token_id

            model.config.vocab_size = model.config.decoder.vocab_size
            model.config.eos_token_id = image_processor.tokenizer.sep_token_id
            model.config.no_repeat_ngram_size = 3
            model.config.num_beams = 2

            CKPT_PATH = os.path.join(self.model_dir, "checkpoints/pix2text-mfr_torch_1500k/checkpoints/epoch=19-val_cer=0.12.ckpt")
            checkpoint = torch.load(CKPT_PATH)
            # try:
            #     model.load_state_dict(checkpoint['state_dict'])
            # except:
            new_dict = OrderedDict()
            for k,v in checkpoint['state_dict'].items():
                new_dict[k[6:]] = v
            model.load_state_dict(new_dict)

            model = model.to(self.device)
            transform_fn = self.img2latex_transform_fn()
            self.logger.info("======Get `trocr_mfr_v2` model======")
            return model, image_processor, transform_fn
        except Exception as e:
            print(e)
            return None, None, None
    
    ## TODO 一些小的符号识别不了
    def get_trocr_mfr_result_v2(self, image):
        image = image.resize((384, 384))
        image = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)
        augmented = self.trocr_mfr_transform_v2(image=image, keypoints=[])
        pixel_values = augmented['image']

        generated_ids = self.trocr_mfr_model_v2.generate(pixel_values.unsqueeze(0).to(self.device), max_length=512, eos_token_id=self.trocr_mfr_processor_v2.tokenizer.sep_token_id)
        generated_text = self.trocr_mfr_processor_v2.batch_decode(generated_ids, skip_special_tokens=True)
        # if generated_text[0][:6] == "\\fbox ":
        #     generated_text[0] = generated_text[0][6:]
        # if generated_text[0][:7] == "\\boxed ":
        #     generated_text[0] = generated_text[0][7:]
        return generated_text[0]
    
    def get_trocr_mfr_result_post_process(self, text:str=""):
        try:
            import pydetex.pipelines as pip
            out = pip.simple(text)
            return out
        except Exception as e:
            print(e)
            return text
    
    def get_doctr_model(self):
        det_arch = "db_resnet50"
        reco_arch = "master"
        assume_straight_pages = True
        straighten_pages = False
        bin_thresh = 0.3
        predictor = ocr_predictor(
            det_arch,
            reco_arch,
            pretrained=True,
            assume_straight_pages=assume_straight_pages,
            straighten_pages=straighten_pages,
            export_as_straight_boxes=straighten_pages,
            detect_orientation=not assume_straight_pages,
        ).to(self.device)
        predictor.det_predictor.model.postprocessor.bin_thresh = bin_thresh
        self.logger.info("======Get `doctr_model` model======")
        return predictor
    
    ## https://medium.com/quantrium-tech/text-extraction-using-doctr-ocr-471e417764d5
    ## 小目标检测效果不行
    def get_doctr_result(self, image):
        # Store the Image object in an I/O buffer
        # buffer = io.BytesIO()
        # image.save(buffer, format="JPEG")

        # # Reset the buffer's position to the beginning
        # buffer.seek(0)

        # # Read the image data from the buffer
        # image_data = buffer.read()

        # # Use the image_data as needed
        # # For example, you can load it back into a PIL Image object
        # doc = DocumentFile.from_images(io.BytesIO(image_data))

        # Convert the PIL image to a NumPy array
        cv2_image = np.array(image)

        # Convert the NumPy array to an OpenCV image
        cv2_image = cv2.cvtColor(cv2_image, cv2.COLOR_RGB2BGR)

        # Encode the NumPy array to a byte array using cv2.imencode()
        _, image_bytes = cv2.imencode(".jpg", cv2_image)
        image_bytes = image_bytes.tobytes()

        # Wrap the byte string in an io.BytesIO object
        doc = DocumentFile.from_images(image_bytes)
        result = self.doctr_model(doc)

        return result.render().replace(" de "," = ").rstrip("\n").rstrip("-").lstrip("-").rstrip("\n").replace("de","=")
    
    def get_ofa_model(self):
        try:
            from modelscope.pipelines import pipeline
            from modelscope.utils.constant import Tasks
            # ModelScope Library >= 0.4.7
            ocr_recognizer = pipeline(Tasks.ocr_recognition, model='damo/ofa_ocr-recognition_scene_base_zh', model_revision='v1.0.1')
            self.logger.info("======get ofa model======")
            return ocr_recognizer
        except Exception as e:
            return None
    
    def get_ofa_result(self, image):
        from modelscope.outputs import OutputKeys
        result = self.ofa_model(image)[OutputKeys.TEXT][0].replace(" ", "")
        result = result.rstrip("-")
        result = result.lstrip("-")
        return result


    def get_got_ocr_model(self, model_dir:str=None):
        try:
            if model_dir is None or os.path.exists(model_dir) is False:
                model_dir = os.path.join(self.model_dir, "checkpoints/GOT-OCR2_0/checkpoints")
            
            tokenizer = AutoTokenizer.from_pretrained(model_dir, trust_remote_code=True)
            model = AutoModel.from_pretrained(model_dir, trust_remote_code=True, low_cpu_mem_usage=True, use_safetensors=True, pad_token_id=tokenizer.eos_token_id)
            model = model.to(self.device).eval()
            self.logger.info("======Get `got_ocr` model======")
            return model, tokenizer
        except Exception as e:
            print(e)
            return None, None
    
    def get_got_ocr_result(self, image):
        if self.got_ocr_model is not None:
            ## pad_image(image) 会降低性能
            res = self.got_ocr_model.chat(self.got_ocr_tokenizer, image, ocr_type='ocr')
            res = res.replace("|","l")
            res = res.replace("（","(")
            res = res.replace("）",")")
            res = res.rstrip(".")
            res = res.rstrip(",")
            res = res.rstrip(":")
            res = res.rstrip(";")
            return res
        else:
            return ""
    
    def convert_coordinates(self, geometry, page_dim, offset_x, offset_y):
        len_x = page_dim[1]
        len_y = page_dim[0]
        (x_min, y_min) = geometry[0]
        (x_max, y_max) = geometry[1]
        x_min = math.floor(x_min * len_x)
        x_max = math.ceil(x_max * len_x)
        y_min = math.floor(y_min * len_y)
        y_max = math.ceil(y_max * len_y)
        return (x_min + offset_x,  y_min + offset_y, x_max + offset_x, y_max + offset_y)

    def get_doctr_result_V2(self, image, mol_label_box, label_box):
        # Convert the PIL image to a NumPy array
        cv2_image = np.array(image)

        # Convert the NumPy array to an OpenCV image
        cv2_image = cv2.cvtColor(cv2_image, cv2.COLOR_RGB2BGR)

        # Encode the NumPy array to a byte array using cv2.imencode()
        _, image_bytes = cv2.imencode(".jpg", cv2_image)
        image_bytes = image_bytes.tobytes()

        # Wrap the byte string in an io.BytesIO object
        doc = DocumentFile.from_images(image_bytes)
        result = self.doctr_model(doc)

        output = result.export()
        page_dim = output['pages'][0]["dimensions"]
        offset_x = mol_label_box[0]
        offset_y = mol_label_box[1]

        text_list = []
        for obj1 in output['pages'][0]["blocks"]:
            line_text_list = []
            for obj2 in obj1["lines"]:
                for obj3 in obj2["words"]:
                    converted_box = self.convert_coordinates(obj3["geometry"], page_dim, offset_x, offset_y)
                    is_add, _ = nms_without_confidence(converted_box, label_box, threshold=0.7, use_union=False)
                    if is_add is False:
                        line_text_list.append(obj3["value"])
            if len(line_text_list)>0:
                line_text = " ".join(line_text_list)
                text_list.append(line_text)
        if len(text_list)>0:
            text = "\n".join(text_list)
            return text.rstrip("\n").rstrip(" ")
        else:
            return ""
    
    def get_yolo_mol_model(self, yolo_mol_path=None, device=torch.device("cpu")):
        try:
            if (yolo_mol_path is None) or (os.path.exists(yolo_mol_path) is False):
                ## 0312修改
                yolo_mol_path = os.path.join(self.model_dir, "checkpoints", "yolo_mol/yolo11x_0320_800_last.pt")
            model = YOLO(yolo_mol_path)
            model = model.to(device)
            if model is not None:
                self.logger.info("======Get `yolo_mol_model` model======")
            return model
        except Exception as e:
            print(e)
            return None
    
    def get_yolo_table_model(self, yolo_table_path:str=None, device=torch.device("cpu")):
        try:
            if (yolo_table_path is None) or (os.path.exists(yolo_table_path) is False):
                yolo_table_path = os.path.join(self.model_dir, "checkpoints", "yolo_table/yolo_teble_best_600k.pt")
            model = YOLO(yolo_table_path)
            model = model.to(device)
            if model is not None:
                self.logger.info(f"======Get `yolo_table_model` model with model_path {yolo_table_path}======")
            return model
        except Exception as e:
            print(e)
            return None

    def transforms_fn(self, pad=0):
        trans_list = []
        trans_list.append(CropWhite(pad=pad))
        return A.Compose(trans_list, keypoint_params=A.KeypointParams(format='xy', remove_invisible=False))

    def img2latex_transform_fn(input_size=384, augment=False, rotate=False, debug=False):
        """图像转换函数

        Args:
            input_size (int, optional): 输入图像的尺寸. Defaults to 384.
            augment (bool, optional): _description_. Defaults to False.
            rotate (bool, optional): _description_. Defaults to False.
            debug (bool, optional): 是否需要debug. Defaults to False.

        Returns:
            fn : 图像转换函数
        """
        trans_list = []
        if augment and rotate:
            trans_list.append(SafeRotate(limit=90, border_mode=cv2.BORDER_CONSTANT, value=(255, 255, 255)))

        # ref:https://blog.csdn.net/HaoZiHuang/article/details/104746009
        if augment:
            # trans_list.append(CropWhite(pad=random.randint(5,30))) ##可能能work,random.randint(5,30)
            trans_list += [
                # NormalizedGridDistortion(num_steps=10, distort_limit=0.3),
                A.CropAndPad(percent=[-0.01, 0.00], keep_size=False, p=0.5),
                PadWhite(pad_ratio=0.4, p=0.2),
                A.Downscale(scale_min=0.2, scale_max=0.5, interpolation=3),
                A.Blur(),
                A.GaussNoise(),
                SaltAndPepperNoise(num_dots=50, p=0.5)## 撒盐
            ]
        else:
            # trans_list.append(CropWhite(pad=20))
            pass
        # trans_list.append(A.Resize(input_size, input_size))
        if not debug:
            mean = [0.485, 0.456, 0.406]
            std = [0.229, 0.224, 0.225]
            trans_list += [
                A.ToGray(p=1),
                A.Normalize(mean=mean, std=std),
                ToTensorV2(),
            ]
        return A.Compose(trans_list, keypoint_params=A.KeypointParams(format='xy', remove_invisible=False))


    def get_page_image_from_pdf(self, file_path="", page_idx=1, osd_detect=False):
        self.logger.info(f"Reading {page_idx} in {file_path}")
        ## 读取page
        ## 分辨率默认300
        page = convert_from_path(file_path,
                                    250,
                                    first_page = page_idx,
                                    last_page = page_idx + 1,
                                    )[0]#PIL.Image.Image
        ## 如果是专利数据，则需要额外的进行裁剪
        Is_crop = judge_patent(page)
        ## 如果是专利数据，用fitz进行打开
        if Is_crop:
            pdf_file = fitz.open(file_path)
            pages = pdf_file[page_idx-1]  # 注意：页码索引从 0 开始

            # 将页面渲染为一个图像对象 (RGBA)
            pix = pages.get_pixmap(matrix=fitz.Matrix(250/72,250/72))  # 使用更高的DPI渲染

            # 将图像对象转换为 PIL Image 对象
            page = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        ## 增加文字朝向识别
        if osd_detect:
            config="--psm 0"
            temp_image_array = self.crop_white_fn(image=np.array(page), keypoints=[])["image"]
            temp_image = Image.fromarray(temp_image_array)
            width, height = temp_image.size
            temp_image = temp_image.crop((int(width*0.1), int(height*0.1), int(width*0.9), int(height*0.9)))
            orientation_results = pytesseract.image_to_osd(np.array(temp_image), config=config ,output_type=pytesseract.Output.DICT) #lang='chi_sim' 
            self.logger.info("======osd detect======")
            self.logger.info(f"orientation_results:{orientation_results}")
            orientation = orientation_results["orientation"] ## 变为逆时针
            orientation_confidence = orientation_results["orientation_conf"]
            ## https://indiantechwarrior.medium.com/optimizing-rotation-accuracy-for-ocr-fbfb785c504b
            if orientation_confidence>=2 and orientation in [90, 180, 270]: # 180 去除180度的结果
                self.logger.info(f"oriention, {orientation_results}")
                page: Image = rotate_bound(page, orientation)
        return page
    
    def get_mode(self, iamge):
        mode = "Eng"
        config="--psm 0"
        orientation_results = pytesseract.image_to_osd(np.array(iamge), config=config ,output_type=pytesseract.Output.DICT) #lang='chi_sim' 
        if orientation_results["script_conf"]>0.75:
            if orientation_results["script"] == "Han":
                mode = "Chi"
        return mode
    
    @staticmethod
    def test_mol_reconginize(block_image_list, model_dir):
        if isinstance(block_image_list, list):
            try:
                result_df = run_task({"image_list":block_image_list, "model_dir":model_dir,
                            "weight_ensemble":False, "update_pad":False}) #"ocr":self.easy_ocrer,
            except Exception as e:
                print(e)
                import traceback
                traceback.print_exc()
            return result_df
    
    # 0211
    @staticmethod
    def get_mol_from_molblcok(molblock:str):
        ## 去除kecher中的引号
        modified_molblock, extra_alais_dict = remove_quation_in_molblcok(molblock)
        ## molblock变为分子对象
        mol = assign_right_bond_stero_to_molblock(modified_molblock)
        ## 去除alais中的引号和空格
        remove_quatation_in_alais(mol)
        set_atom_alais(mol, extra_alais_dict)
        add_r_in_mol(mol)
        molblock = Chem.MolToMolBlock(mol)
        molblock = assign_e_to_unsigned_bond(add_quotation_mark_to_mol_block(molblock))
        try:
            smiles, new_mol = _expand_functional_group(mol, {})
        except:
            smiles = ""

        return molblock, smiles

        

    
    @staticmethod
    def new_molzip(core_molblock:str, rgroup_dict:dict):

        if isinstance(rgroup_dict, dict):
            ## 去除kecher中的引号

            modified_core_molblock, extra_alais_dict = remove_quation_in_molblcok(core_molblock)
            ## 去除kecher中的引号
            # for k,v in rgroup_dict.items():
            #     rgroup_dict[k] = remove_quation_in_molblcok(v)
            
            ## molblock变为分子对象
            # core_mol = Chem.MolFromMolBlock(modified_core_molblock)
            core_mol = assign_right_bond_stero_to_molblock(modified_core_molblock)
            ## 去除alais中的引号和空格
            remove_quatation_in_alais(core_mol)
            
            set_atom_alais(core_mol, extra_alais_dict)
            ## 把R对应的位置原子序号改为"0"
            add_r_in_mol(core_mol)
            ## 原始的分子
            # original_smiles = Chem.MolToSmiles(core_mol, canonical=False)
            try:
                original_smiles, _ = _expand_functional_group(core_mol, {})
            except Exception as e:
                print(e)
                original_smiles = Chem.MolToSmiles(core_mol, canonical=False)
            # print("original_smiles", original_smiles)
            ##
            new_rgroup_dict = {}
            for k,v in rgroup_dict.items():
                try:
                    modified_core_molblock, extra_alais_dict = remove_quation_in_molblcok(v)
                    new_rgroup_dict[k] = assign_right_bond_stero_to_molblock(modified_core_molblock)#Chem.MolFromMolBlock(v)
                    ## 去除alais中的引号和空格
                    remove_quatation_in_alais(new_rgroup_dict[k])
                    set_atom_alais(new_rgroup_dict[k], extra_alais_dict)
                    add_r_in_mol(new_rgroup_dict[k])
                except:
                    ## 失败的分子用用`缩写`就行

                    ## 暂时不考虑smiles
                    # try:
                    #     temp_temp_mol = Chem.MolFrom(v)
                    #     new_rgroup_dict[k] = temp_temp_mol
                    #     remove_quatation_in_alais(new_rgroup_dict[k])
                    #     set_atom_alais(new_rgroup_dict[k], extra_alais_dict)
                    #     add_r_in_mol(new_rgroup_dict[k])
                    # except:
                    #     new_rgroup_dict[k] = v
                    new_rgroup_dict[k] = v

            
            ## 结果分子
            temp_mol = copy.deepcopy(core_mol)
            ## 设置atom的SetProp
            for atom in temp_mol.GetAtoms():
                atom.SetProp("part", "core")
            
            ## add in 0806
            for k, v in new_rgroup_dict.items():
                break
            if (len(new_rgroup_dict) == 1) and original_smiles.count("*")==1:
                ## 仅仅取出第一个元素
                for k, v in new_rgroup_dict.items():
                    break
                core_result_dict = get_candidate_concat_atom(temp_mol)
                ## 仅仅取出第一个元素
                for core_k, core_v in core_result_dict.items():
                    break

                if isinstance(new_rgroup_dict[k], Chem.rdchem.Mol):
                    print("adding single R in Molecule")
                    ## 只有一个待拼接的模块
                    atom_idx1 = core_result_dict[core_k][0] ## 默认第0个好了
                    r_result_dict = get_candidate_concat_atom(new_rgroup_dict[k])

                    if len([__ for _ in r_result_dict.values() for __ in _])==1:
                        ## 断点原子序号
                        atom_idx2 = r_result_dict["star"][0]
                        temp_mol.GetAtomWithIdx(atom_idx1).SetAtomMapNum(100)
                        new_rgroup_dict[k].GetAtomWithIdx(atom_idx2).SetAtomMapNum(100)

                        ## 设置新的原子属性
                        temp_mol.GetAtomWithIdx(atom_idx1).SetProp("part", k)
                        for atom in new_rgroup_dict[k].GetAtoms():
                            atom.SetProp("part", k)
                        
                        ## 拼接
                        combined_mol = Chem.CombineMols(temp_mol, new_rgroup_dict[k])
                        temp_mol = Chem.molzip(combined_mol)
                    else:
                        temp_flag = False
                        for atom_idx1 in core_result_dict[core_k]:
                            if len([__ for _ in r_result_dict.values() for __ in _]) == len(temp_mol.GetAtomWithIdx(atom_idx1).GetNeighbors()):
                                temp_flag = True
                                break
                        
                        if temp_flag:
                            print("adding multiple R in Molecule")
                            ## 如果有star对象, 则进行拼接
                            if "star" in r_result_dict:
                                if (len(r_result_dict["star"]) == 1) or (len(temp_mol.GetAtomWithIdx(atom_idx1).GetNeighbors()) == 1):
                                    atom_idx2 = r_result_dict["star"][0]

                                    temp_mol.GetAtomWithIdx(atom_idx1).SetAtomMapNum(100)
                                    new_rgroup_dict[k].GetAtomWithIdx(atom_idx2).SetAtomMapNum(100)

                                    ## 设置新的原子属性
                                    temp_mol.GetAtomWithIdx(atom_idx1).SetProp("part", k)
                                    for atom in new_rgroup_dict[k].GetAtoms():
                                        atom.SetProp("part", k)
                                    
                                    ## 拼接
                                    combined_mol = Chem.CombineMols(temp_mol, new_rgroup_dict[k])
                                    temp_mol = Chem.molzip(combined_mol)
                                else:
                                    from scipy.spatial.distance import cdist
                                    from scipy.optimize import linear_sum_assignment
                                    atoms_idx2 = r_result_dict["star"]
                                    atoms_idx2_coods = new_rgroup_dict[k].GetConformer().GetPositions()[:,:2][atoms_idx2]
                                    distance_matrix_1 = cdist(atoms_idx2_coods, atoms_idx2_coods, metric='euclidean')
                                    ave_distance_1 = distance_matrix_1.sum()/2/(max(len(atoms_idx2_coods)*len(atoms_idx2_coods)-1 , 1))

                                    atom_neigh_idx1 = [_.GetIdx() for _ in temp_mol.GetAtomWithIdx(atom_idx1).GetNeighbors()] 
                                    atom_neigh_idx1_coods = temp_mol.GetConformer().GetPositions()[:,:2][atom_neigh_idx1]
                                    distance_matrix_2 = cdist(atom_neigh_idx1_coods, atom_neigh_idx1_coods, metric='euclidean')
                                    ave_distance_2 = distance_matrix_2.sum()/2/(max(len(atom_neigh_idx1_coods)*len(atom_neigh_idx1_coods)-1 , 1))

                                    ## 在同一尺度进行比较
                                    atoms_idx2_coods = atoms_idx2_coods/ave_distance_1*ave_distance_2-np.mean(atoms_idx2_coods, axis=0)+np.mean(atom_neigh_idx1_coods, axis=0)

                                    cost_martix = [[np.power((np.array(a)-np.array(b)),2).sum() for a in atom_neigh_idx1_coods] for b in atoms_idx2_coods]

                                    row_ind, col_ind = linear_sum_assignment(cost_martix)

                                    temp_mol = Chem.RWMol(temp_mol)
                                    for temp_i, (x,y) in enumerate(zip(row_ind, col_ind)):
                                        atom_idx2 = atoms_idx2[x]
                                        neigh_atom_idx1 = atom_neigh_idx1[y]

                                        # temp_mol.GetAtomWithIdx(neigh_atom_idx1).SetProp("temp_token", 100-temp_i)
                                        bond = temp_mol.GetBondBetweenAtoms(atom_idx1, neigh_atom_idx1)
                                        bond_type = bond.GetBondType()
                                        atom = Chem.Atom("*")
                                        temp_mol.AddAtom(atom)
                                        temp_mol.AddBond(neigh_atom_idx1, len(temp_mol.GetAtoms())-1, bond_type)
                                        
                                        temp_mol.GetAtomWithIdx(len(temp_mol.GetAtoms())-1).SetAtomMapNum(100-temp_i)
                                        new_rgroup_dict[k].GetAtomWithIdx(atom_idx2).SetAtomMapNum(100-temp_i)
                                    
                                    for atom in new_rgroup_dict[k].GetAtoms():
                                        atom.SetProp("part", k)

                                    temp_mol.RemoveAtom(atom_idx1)
                                    
                                    combined_mol = Chem.CombineMols(temp_mol, new_rgroup_dict[k])
                                    
                                    temp_mol = Chem.molzip(combined_mol)

                            else:
                                ## 不做任何处理
                                pass

                ## TODO
                elif isinstance(new_rgroup_dict[k], str):
                    print("adding smiles in Molecule")
                    atom_idx1 = core_result_dict[core_k][0] ## 默认第0个好了
                    atom = temp_mol.GetAtomWithIdx(atom_idx1)
                    atom.SetProp("part", k)
                    ## 以alais的形式进行设置
                    atom_alias = new_rgroup_dict[k]
                    Chem.SetAtomAlias(atom, atom_alias)

            else:
                for k, v in new_rgroup_dict.items():

                    ## 获取母核分子的候选拼接原子
                    core_result_dict = get_candidate_concat_atom(temp_mol) #:Dict[str:List[int]]

                    ## 如果这个值在候选列表中
                    ## TODO 需要验证
                    if k in core_result_dict or (k=="R" and "star" in core_result_dict):
                        ## 直接把"*"赋值过去
                        if (k not in core_result_dict) and (k=="R" and "star" in core_result_dict):
                            if len(core_result_dict["star"])>1:
                                print("There are two star in table")
                                return None, None, None
                            core_result_dict["R"] = core_result_dict["star"]
                        
                        ## 分子对象
                        if isinstance(new_rgroup_dict[k], Chem.rdchem.Mol):
                            # 获取rgroup的拼接分子
                            r_result_dict = get_candidate_concat_atom(new_rgroup_dict[k]) #: Dict[str:List[int]]

                            atom_idx1 = core_result_dict[k][0] ## 默认第0个好了

                            ## 如果有star对象, 则进行拼接
                            if "star" in r_result_dict:
                                if (len(r_result_dict["star"]) == 1) or (len(temp_mol.GetAtomWithIdx(atom_idx1).GetNeighbors()) == 1):
                                    atom_idx2 = r_result_dict["star"][0]

                                    temp_mol.GetAtomWithIdx(atom_idx1).SetAtomMapNum(100)
                                    new_rgroup_dict[k].GetAtomWithIdx(atom_idx2).SetAtomMapNum(100)

                                    ## 设置新的原子属性
                                    temp_mol.GetAtomWithIdx(atom_idx1).SetProp("part", k)
                                    for atom in new_rgroup_dict[k].GetAtoms():
                                        atom.SetProp("part", k)
                                    
                                    ## 拼接
                                    combined_mol = Chem.CombineMols(temp_mol, new_rgroup_dict[k])
                                    temp_mol = Chem.molzip(combined_mol)
                                else:
                                    from scipy.spatial.distance import cdist
                                    from scipy.optimize import linear_sum_assignment
                                    atoms_idx2 = r_result_dict["star"]
                                    atoms_idx2_coods = new_rgroup_dict[k].GetConformer().GetPositions()[:,:2][atoms_idx2]
                                    distance_matrix_1 = cdist(atoms_idx2_coods, atoms_idx2_coods, metric='euclidean')
                                    ave_distance_1 = distance_matrix_1.sum()/2/(max(len(atoms_idx2_coods)*len(atoms_idx2_coods)-1 , 1))

                                    atom_neigh_idx1 = [_.GetIdx() for _ in temp_mol.GetAtomWithIdx(atom_idx1).GetNeighbors()] 
                                    atom_neigh_idx1_coods = temp_mol.GetConformer().GetPositions()[:,:2][atom_neigh_idx1]
                                    distance_matrix_2 = cdist(atom_neigh_idx1_coods, atom_neigh_idx1_coods, metric='euclidean')
                                    ave_distance_2 = distance_matrix_2.sum()/2/(max(len(atom_neigh_idx1_coods)*len(atom_neigh_idx1_coods)-1 , 1))

                                    ## 在同一尺度进行比较
                                    atoms_idx2_coods = atoms_idx2_coods/ave_distance_1*ave_distance_2-np.mean(atoms_idx2_coods, axis=0)+np.mean(atom_neigh_idx1_coods, axis=0)

                                    cost_martix = [[np.power((np.array(a)-np.array(b)),2).sum() for a in atom_neigh_idx1_coods] for b in atoms_idx2_coods]

                                    row_ind, col_ind = linear_sum_assignment(cost_martix)

                                    temp_mol = Chem.RWMol(temp_mol)
                                    for temp_i, (x,y) in enumerate(zip(row_ind, col_ind)):
                                        atom_idx2 = atoms_idx2[x]
                                        neigh_atom_idx1 = atom_neigh_idx1[y]

                                        # temp_mol.GetAtomWithIdx(neigh_atom_idx1).SetProp("temp_token", 100-temp_i)
                                        bond = temp_mol.GetBondBetweenAtoms(atom_idx1, neigh_atom_idx1)
                                        bond_type = bond.GetBondType()
                                        atom = Chem.Atom("*")
                                        temp_mol.AddAtom(atom)
                                        temp_mol.AddBond(neigh_atom_idx1, len(temp_mol.GetAtoms())-1, bond_type)
                                        
                                        temp_mol.GetAtomWithIdx(len(temp_mol.GetAtoms())-1).SetAtomMapNum(100-temp_i)
                                        new_rgroup_dict[k].GetAtomWithIdx(atom_idx2).SetAtomMapNum(100-temp_i)
                                    
                                    for atom in new_rgroup_dict[k].GetAtoms():
                                        atom.SetProp("part", k)

                                    temp_mol.RemoveAtom(atom_idx1)
                                    
                                    combined_mol = Chem.CombineMols(temp_mol, new_rgroup_dict[k])
                                    
                                    temp_mol = Chem.molzip(combined_mol)

                                
                            else:
                                ## 不做任何处理
                                pass
                            

                            
                        ## 非分子对象，直接变成alais写入
                        elif isinstance(new_rgroup_dict[k], str):
                            atom_idx1 = core_result_dict[k][0] ## 默认第0个好了
                            atom = temp_mol.GetAtomWithIdx(atom_idx1)
                            atom.SetProp("part", k)
                            ## 以alais的形式进行设置
                            atom_alias = new_rgroup_dict[k]
                            Chem.SetAtomAlias(atom, atom_alias)
                    
                    else:
                        ## 不做任何处理
                        pass
                
            ## 获取扩展后的smiles
            smiles, _ = _expand_functional_group(temp_mol, {})
            ## 将原子属性记录在字典中
            indics_dict = {}
            for atom in temp_mol.GetAtoms():
                part = atom.GetProp("part")
                if part not in indics_dict:
                    indics_dict[part] = []
                indics_dict[part].append(atom.GetIdx())
            
            ## 用rdkit默认的坐标
            AllChem.Compute2DCoords(temp_mol)
            molblock = Chem.MolToMolBlock(temp_mol)
            ## molblock 后处理
            molblock = assign_e_to_unsigned_bond(add_quotation_mark_to_mol_block(molblock))
            ## fix_bug_0730
            ## 如果smiles有空格，或者smiles和原始的smiles相等
            if "*" in smiles or smiles == original_smiles:
                return None, None, None
            else:
                return molblock, smiles, indics_dict
        
        ## 支持一个R-Group和一个断点的拼接
        elif isinstance(rgroup_dict, list):
            ## 确保列表的长度为1
            rgroup_list = rgroup_dict
            assert len(rgroup_list) == 1
            modified_core_molblock, extra_alais_dict = remove_quation_in_molblcok(core_molblock)
            core_mol = assign_right_bond_stero_to_molblock(modified_core_molblock)#Chem.MolFromMolBlock(modified_core_molblock)
            remove_quatation_in_alais(core_mol)
            set_atom_alais(new_rgroup_dict[k], extra_alais_dict)
            add_r_in_mol(core_mol)

            new_rgroup_list = []
            for rgroup in rgroup_list:
                try:
                    temp_rgroup_molblcok, extra_alais_dict = remove_quation_in_molblcok(rgroup)
                    new_rgroup_list.append(assign_right_bond_stero_to_molblock(temp_rgroup_molblcok))
                    remove_quatation_in_alais(new_rgroup_list[-1])
                    set_atom_alais(new_rgroup_list[-1], extra_alais_dict)
                    add_r_in_mol(new_rgroup_list[-1])
                except:
                    ## 失败的分子用直接用字符
                    new_rgroup_list.append(rgroup)
            
            ## 结果分子
            temp_mol = copy.deepcopy(core_mol)
            for atom in temp_mol.GetAtoms():
                atom.SetProp("part", "core")

            for i, rgroup in enumerate(new_rgroup_list):
                core_result_dict = get_candidate_concat_atom(temp_mol)

                if isinstance(rgroup, Chem.rdchem.Mol):
                    r_result_dict = get_candidate_concat_atom(rgroup)
                    atom_idx1 = core_result_dict["star"][0] ## 默认第0个好了

                    ## 如果有star对象, 则进行拼接
                    if "star" in  r_result_dict:
                        atom_idx2 = r_result_dict["star"][0]

                        temp_mol.GetAtomWithIdx(atom_idx1).SetAtomMapNum(100)
                        rgroup.GetAtomWithIdx(atom_idx2).SetAtomMapNum(100)

                        temp_mol.GetAtomWithIdx(atom_idx1).SetProp("part", f"{i}")
                        for atom in rgroup.GetAtoms():
                            atom.SetProp("part", f"{i}")

                        combined_mol = Chem.CombineMols(temp_mol, rgroup)
                        temp_mol = Chem.molzip(combined_mol)
                else:
                    if "star" in core_result_dict:
                        atom_idx1 = core_result_dict["star"][0] ## 默认第0个好了
                        atom = temp_mol.GetAtomWithIdx(atom_idx1)
                        atom.SetProp("part", f"{i}")
                        Chem.SetAtomAlias(atom, rgroup)

            
            smiles, _ = _expand_functional_group(temp_mol, {})
            indics_dict = {}
            for atom in temp_mol.GetAtoms():
                part = atom.GetProp("part")
                if part not in indics_dict:
                    indics_dict[part] = []
                indics_dict[part].append(atom.GetIdx())
            
            ## 用rdkit默认的坐标
            AllChem.Compute2DCoords(temp_mol)
            molblock = Chem.MolToMolBlock(temp_mol)
            molblock = assign_e_to_unsigned_bond(add_quotation_mark_to_mol_block(molblock))
            ## fix_bug_0730
            if "*" in smiles:
                return None, None, None
            else:
                return molblock, smiles, indics_dict
        
        else:
            raise ValueError("the type of `rgroup_dict` is invalid (not dict or list)")
    

    @staticmethod
    def process_sar(df:pd.DataFrame, 
            smiles_column:str, 
            property_columns:List[str]=[],
            log_transforms:bool=False,
            small_is_best:bool=False,
            with_cluster:bool=True,
            threshold:float=0.3,
            core_smart:str=None,
            mode:str="auto"):
    
        return _process_sar(df, 
                            smiles_column,
                            property_columns,
                            log_transforms,
                            small_is_best,
                            with_cluster,
                            threshold,
                            core_smart,
                            mode)
        

    ## 0731
    def table_ocr_v2(self, image, cell_box, mode="auto"):
        cell_image = image.crop(cell_box)
        # cell_image = ocr_precessing(cell_image)
        temp_width, temp_height = cell_image.size
        cell_image = cv2.cvtColor(np.asarray(cell_image),cv2.COLOR_RGB2BGR)
        # cell_image = remove_gray(cell_image)
        cell_image = remove_horizontal_and_vertical_line(cell_image,  horizontal_size=int(temp_width*0.5), vertical_size=int(temp_height*0.5))
        cell_image = Image.fromarray(cell_image)

        temp_mode = mode
        out = ""
        if temp_mode == "Chi":
            if (out == "") and self.ofa_model is not None:
                out = self.get_ofa_result(cell_image)
                print("ofa_model", out)
                return out
        else:
            pass

        return out
    
    def border_table_2_html(self, extract_table, table_image):
        import ipdb
        ipdb.set_trace()

    
    def table_html_with_ocr(self, table_html, table_image):
        soup = BeautifulSoup(table_html, 'html.parser')
        table = soup.find('table')
        rows = table.find_all('tr')
        html_string = pre_table_html
        for i, row in enumerate(rows):
            temp_row_html = "<tr>"
            cells = row.find_all('td')
            for j, cell in enumerate(cells):
                cell_string = cell.string
                boxes = [round(float(_.split(":")[-1]), 2) for _ in cell_string.split(",")]
                cell_image = table_image.crop(boxes)
                temp_width, temp_height = cell_image.size
                cell_image = cv2.cvtColor(np.asarray(cell_image),cv2.COLOR_RGB2BGR)
                cell_image = remove_horizontal_and_vertical_line(cell_image,  horizontal_size=int(temp_width*0.5), vertical_size=int(temp_height*0.5))
                cell_image = Image.fromarray(cell_image)

                out = self.get_ofa_result(cell_image)
                print("OFA",out)
                colspan = cell.get('colspan', 1)
                rowspan = cell.get('rowspan', 1)
                temp_row_html = temp_row_html + f'<td colspan="{colspan}" rowspan="{rowspan}">{out}</td>'
            
            temp_row_html += "</tr>"
            html_string += temp_row_html
        
        html_string += post_table_html
        return html_string
    
    def moldect_with_test_augment(self,
                                image: Image = None, 
                                img_path: str = "" , 
                                moldetect_model = None,
                                offset_x: int = 0,
                                offset_y: int = 0, 
                                usr_tta: bool = True,
                                coref: bool = True,
                                use_ocr: bool = False,
                                with_padding = False,
                                dubug: bool = False,
                                ) -> list:
        """_summary_

        Args:
            image (Image, optional): 图片. Defaults to None.
            img_path (str, optional): 图片路径. Defaults to "".
            moldetect_model (_type_, optional): model of moldetect. Defaults to None.
            offset_x (int, optional): offset of x. Defaults to 0.
            offset_y (int, optional): offset of y. Defaults to 0.
            usr_tta (bool, optional): 是否使用tta. Defaults to True.
            coref (bool, optional): 是否将标签和图像进行一起预测. Defaults to True.
            use_ocr (bool, optional): 是否检测ocr. Defaults to False.
            dubug (bool, optional): 是否需要检测ocr. Defaults to False.

        Returns:
            list: _description_
        """
        if image is None:
            image = read_image(img_path)
        
        padding = 0
        ## 不推荐使用padding
        if with_padding is True:
            width, height = image.size
            padding = int(0.1 * min(width, height))
            # 创建一个新的图像对象，宽度与原图像相同，高度为填充后的高度
            padded_image = Image.new(image.mode, (width+2*padding, height+2*padding), color=(255, 255, 255))
            # 将原图像粘贴到新图像中，保持原有位置不变
            padded_image.paste(image, (padding, padding))
            
            image = padded_image
        
        if usr_tta is True:
            angle_list = [0, 1, -1] #[0, 1, -2.5, -1, 2.5,]
        else:
            angle_list = [0]
        
        pair_result_dict: dict = {}
        single_result_dict: dict = {}
        for angle in angle_list:
            ## 默认情况下，该方法按照逆时针方向对图像进行旋转。
            rotated_image = image.rotate(angle) #对rotation的图片进行操作
            predictions = moldetect_model.predict_image(rotated_image, coref=coref, ocr=use_ocr)
            pair_result_dict[angle] = get_pair_prediction_from_moldetect(rotated_image, predictions)
            single_result_dict[angle] = get_prediction_from_moldetect(rotated_image, predictions)
        
        single_result_list=[]
        ## 中心坐标
        center_x, center_y = image.size[0]//2, image.size[1]//2
        for angle, results in single_result_dict.items():
            for result in results:
                mol_box = result["mol_box"]
                mol_box = get_previous_rotation_box(mol_box, angle, center_x,center_y)
                
                mol_box: tuple[int, tuple[int]] = ( max(mol_box[0], 0), 
                                                    max(mol_box[1], 0), 
                                                    min(mol_box[2], image.size[0]),
                                                    min(mol_box[3], image.size[1]))
            
                if mol_box[2]<=mol_box[0] or mol_box[3]<=mol_box[1]:
                    mol_box = None
                
                if (mol_box is not None):
                    single_result_list.append({
                        "mol_box": mol_box,
                    })
        
        ## 一个结果
        last_single_result_list = merge_molecule_box(image, single_result_list)
        
        pair_result_list = []
        for angle, results in pair_result_dict.items():
            for result in results:
                mol_box = result["mol_box"]
                mol_box = get_previous_rotation_box(mol_box, angle, center_x, center_y)
                
                mol_box: tuple[int, tuple[int]] = ( max(mol_box[0], 0), 
                                                    max(mol_box[1], 0), 
                                                    min(mol_box[2], image.size[0]),
                                                    min(mol_box[3], image.size[1]))
            
                if mol_box[2]<=mol_box[0] or mol_box[3]<=mol_box[1]:
                    mol_box = None
                
                label_box = result["label_box"]
                label_box = get_previous_rotation_box(label_box, angle, center_x, center_y)
                
                label_box: tuple[int, tuple[int]] = ( max(label_box[0], 0), 
                                                    max(label_box[1], 0), 
                                                    min(label_box[2], image.size[0]),
                                                    min(label_box[3], image.size[1]))
            
                if label_box[2]<=label_box[0] or label_box[3]<=label_box[1]:
                    label_box = None
                    
                if (mol_box is not None) and (label_box is not None):
                    pair_result_list.append({
                        "mol_box": mol_box,
                        "label_box" : label_box,
                    })
                elif (mol_box is not None) and (label_box is None):
                    pair_result_list.append({
                        "mol_box": mol_box,
                    })
                ## 当mol_box为None时,单独的label_box没有什么意义
                # elif (mol_box is None) and (label_box is not None):
                #     pair_result_list.append({
                #         "label_box": label_box,
                #     })
                
        last_pair_result_list = merge_molecule_label_box(image, pair_result_list)
        last_result = merge_molecule_box(image, last_single_result_list + last_pair_result_list)
        
        if len(last_result)>0:
            ## expand
            bboxes = []
            for box_dict in last_result:
                box = box_dict["mol_box"]
                x1, y1, x2, y2 = box
                box = math.floor(x1), math.floor(y1), math.ceil(x2), math.ceil(y2)
                bboxes.append(box)
            
            img = cv2.cvtColor(np.asarray(image),cv2.COLOR_RGB2BGR)
            height, width, _ = img.shape
            img = remove_horizontal_and_vertical_line(img,  horizontal_size=int(width*0.5), vertical_size=int(height*0.5))
            new_bboxes = expand_mol(img, bboxes)
            for _ in range(len(last_result)):
                old_box = last_result[_]["mol_box"]
                new_box = new_bboxes[_]
                # if (old_box[0]>new_box[0]) and (old_box[1]>new_box[1]) and (old_box[2]<new_box[2]) and (old_box[3]<new_box[3]):
                #     last_result[_]["mol_box"] = new_bboxes[_]
                last_result[_]["mol_box"] = new_bboxes[_]
            last_result = merge_molecule_box(image, last_result)
        
        ## 把offset加入到box中
        for box_dict in last_result:
            mol_box = box_dict.get("mol_box") if "mol_box" in box_dict else None
            if mol_box is not None:
                mol_box = (
                        mol_box[0] + offset_x - padding, mol_box[1] + offset_y - padding,
                        mol_box[2] + offset_x - padding, mol_box[3] + offset_y - padding
                        )
                box_dict["mol_box"] = mol_box
            
            label_boxes = box_dict.get("label_box") if "label_box" in box_dict else []
            new_label_boxes = []
            if len(label_boxes) > 0:
                for label_box in label_boxes:
                    new_label_boxes.append(
                        (
                        label_box[0] + offset_x - padding, label_box[1] + offset_y - padding,
                        label_box[2] + offset_x - padding, label_box[3] + offset_y - padding
                        )
                    )
                box_dict["label_box"] = new_label_boxes
        return last_result

    ## add 0606
    def get_layout_prediction_v2(self, page:Image, page_idx:int=0, with_tta:bool=False, padding:int=10, debug:bool=False, add_extra_pad:bool=True):
        layout = self.layout_parser.detect(page)
        table_figure_blocks = lp.Layout([b for b in layout if (b.type=="Table") or (b.type=="Figure")]) # "Figure"
        ## TODO 需要优化
        temp_box_list = []

        for block_idx, b in enumerate(table_figure_blocks):
            temp_block_box = (b.block.x_1, b.block.y_1, b.block.x_2, b.block.y_2,)
            temp_image = page.crop(temp_block_box)

            if add_extra_pad is False:
                ##页码, 序号, 角度，图片，x_offset, y_offset, 类型
                temp_box_list.append((page_idx, 
                                      block_idx, 
                                      0, 
                                      temp_image, 
                                      temp_block_box[0], 
                                      temp_block_box[1], 
                                      b.type))
            else:
                # 创建一个新的正方形图像
                new_width = int(temp_image.width * 2.0)
                new_height = int(temp_image.height * 2.0)
                new_img = Image.new('RGB', (new_width, new_height), (255, 255, 255)) # 白色背景

                # 将原图居中粘贴到新图像上
                left = (new_width - temp_image.width) // 2
                top = (new_height - temp_image.height) // 2
                new_img.paste(temp_image, (left, top))
                temp_box_list.append((page_idx, 
                                      block_idx, 
                                      0, 
                                      new_img, 
                                      temp_block_box[0] - int(temp_image.width * 0.5), 
                                      temp_block_box[1]- int(temp_image.height * 0.5), 
                                      b.type))
        return temp_box_list
    
    def get_layout_prediction(self, page:Image, page_idx:int=0, with_tta:bool=False, padding:int=10, debug:bool=False):
        # layout_parser = self.get_layout_parser()
        layout = self.layout_parser.detect(page)
        ## 先对图片中的表格和图片进行摘取
        table_figure_blocks = lp.Layout([b for b in layout if (b.type=="Table") or (b.type=="Figure")]) # "Figure"
        ## 对图片中的表格和图片进行遍历
        block_image_list = []
        self.logger.info(f"{len(table_figure_blocks)} layout in page_{page_idx}")
        for block_idx, block in enumerate(table_figure_blocks):
            
            if block.type =="Table":
                temp_padding: int = padding * 2
            else:
                temp_padding = padding
            ## 索引从1开始
            block_idx = block_idx + 1
            ## 获取block_image的坐标
            x_1 = block.block.x_1 - temp_padding
            x_1 = max(x_1, 0)##不能小于0
            x_2 = block.block.x_2 + temp_padding
            x_2 = min(x_2, page.size[0])##不能大于page.size[0]
            y_1 = block.block.y_1 - temp_padding
            y_1 = max(y_1, 0)##不能小于0
            y_2 = block.block.y_2 + temp_padding
            y_2 = min(y_2, page.size[1])##不能大于page.size[1]
            block_box = (x_1, y_1, x_2, y_2)

            if y_2 > y_1 and x_2 > x_1:
                ## 截取局部的图片
                block_image = page.crop(block_box)
                if with_tta is True:
                    for angle in [-1, 0, 1]:
                        block_image_list.append([(page_idx, block_idx, angle, block_image.rotate(angle), x_1, y_1, block.type)])
                else:
                    block_image_list.append([(page_idx, block_idx, 0, block_image, x_1, y_1, block.type)])

        """
        block_image_list:List[List] = [page_idx, block_idx, angle, block_image, x_1, y_1, block的类型]
        block_idx 从 1 开始
        """
        return block_image_list

    # def prediction_from_image(self,
    #                         image:Image=None,## 增加一个Image的接口
    #                         file_path:str=None,
    #                         page_idx:int=None,
    #                         box:Tuple[int,float]=None,
    #                         ):
        
    #     if image is None:
    #         self.logger.info(f"======reading image from pdf with page_idx {page_idx}======")
    #         image:Image = self.get_page_image_from_pdf(file_path, page_idx)
    #     width, height = image.size
    #     self.logger.info(f"======Checking Box======")
    #     box = (max(0, box[0]), max(0, box[1]), min(width, box[2]), min(height, box[3]))
    #     if box[0]>box[2]:
    #         self.logger.error(f"======box[0]({box[0]}) greater than box[2]({box[2]})======")
    #         raise Exception(f"======box[0]({box[0]}) greater than box[2]({box[2]})======")
    #     if box[1]>box[3]:
    #         self.logger.error(f"======box[0]({box[1]}) greater than box[2]({box[3]})======")
    #         raise Exception(f"======box[0]({box[1]}) greater than box[2]({box[3]})======")
        
    #     self.logger.info(f"======crop Box======")
    #     image = image.crop(box)


    def get_prediction_with_angle(self,
                                single_predictions:Dict,
                                angle:float=0,
                                ):
        
        ## 不对angle为0结果精心操作
        if angle == 0:
            return 
        
        center_x, center_y = 0.5, 0.5
        ## operation in-place
        for results in single_predictions["bboxes"]:
            box = results["bbox"]
            box = get_previous_rotation_box(box, angle, center_x, center_y)
            box = ( max(box[0], 0.0), 
                    max(box[1], 0.0), 
                    min(box[2], 1.0),
                    min(box[3], 1.0))

            if box[2]<=box[0] or box[3]<=box[1]:
                box = (0, 0, 0, 0)

    def filter_unreasonable_mol(self, image:Image=None, total_result:List[Dict]=[])->List:
        if len(total_result) == 0:
            return total_result
        else:
            new_total_result = []
            for box_dict in total_result:
                box = box_dict["mol_box"]
                x1, y1, x2, y2 = box
                box = math.floor(x1), math.floor(y1), math.ceil(x2), math.ceil(y2)
                if box[3] - box[1]<=20 or box[2] - box[0]<=20:
                    continue
                else:
                    pass
                    if image is not None:
                        temp_image = image.crop(box)
                        temp_image_array = np.array(temp_image)
                        if np.sum(temp_image_array<225)==0:
                            continue

                        temp_image = temp_image.convert("L")
                        temp_image_array = np.array(temp_image)
                        threhold, binary_image = cv2.threshold(temp_image_array, 127, 255, cv2.THRESH_BINARY)
                        inverted_image = cv2.bitwise_not(binary_image)
                        inverted_image = inverted_image//255

                        ratio = (inverted_image.sum())/(inverted_image.shape[0]*inverted_image.shape[1])
                        # print(f"ratio:{ratio}")

                        if ratio>=0.10:
                            continue
                    
                    new_total_result.append(box_dict)

            return new_total_result
    
    ## TODO 
    ## probelm
    def expand_mol_fn(self, image, total_result):
        ## 不大建议使用
        self.logger.info("====== begin expand mol ======")
        bboxes:List[Tuple] = [box_dict["mol_box"] for box_dict in total_result]

        img = cv2.cvtColor(np.asarray(image),cv2.COLOR_RGB2BGR)
        
        ## 更新
        new_bboxes = expand_mol(img, bboxes)
        for _ in range(len(total_result)):
            
            ## TODO 可以加nms过滤

            is_add, __ = nms_without_confidence(total_result[_]["mol_box"], new_bboxes[_], threshold=0.5)
            if is_add is False:
                total_result[_]["mol_box"] = new_bboxes[_]
            else:
                ## 通过二值化像素看看能不能合并
                temp_image = image.crop(new_bboxes[_]).convert("L")
                temp_image_array = np.array(temp_image)
                threhold, binary_image = cv2.threshold(temp_image_array, 127, 255, cv2.THRESH_BINARY)
                inverted_image = cv2.bitwise_not(binary_image)
                inverted_image = inverted_image//255
                x_start = math.floor(max(new_bboxes[_][0]-total_result[_]["mol_box"][0], 0))
                y_start = math.floor(max(new_bboxes[_][1]-total_result[_]["mol_box"][1], 0))

                x_end = math.ceil(min(total_result[_]["mol_box"][2] -total_result[_]["mol_box"][0] , inverted_image.shape[1]))
                y_end = math.ceil(min(total_result[_]["mol_box"][3] -total_result[_]["mol_box"][1] , inverted_image.shape[0]))

                ratio = (inverted_image.sum() - (inverted_image[y_start:y_end, x_start:x_end]).sum())/(inverted_image.shape[0]*inverted_image.shape[1] - (y_end-y_start)*(x_end-x_start))

                ## 说明是分子
                ## 0.03其实也可以
                if ratio<=0.05:
                    total_result[_]["mol_box"] = new_bboxes[_]
                # old_box = total_result[_]["mol_box"]
                # new_box = new_bboxes[_]
                # ## 只考虑更大的box
                # if (old_box[0]>new_box[0]) and (old_box[1]>new_box[1]) and (old_box[2]<new_box[2]) and (old_box[3]<new_box[3]):
                #     total_result[_]["mol_box"] = new_bboxes[_]
        
        total_result = merge_molecule_box(image, total_result)
        self.logger.info("====== end expand mol ======")
    
    def get_left_top_mol(self, total_result_dict:Dict={}):
        for page_idx, total_result in total_result_dict.items():
            if len(total_result)>1:
                left_top_id = None
                left_top_distance = np.inf
                for block_idx, box_dict in enumerate(total_result):
                    mol_box = box_dict.get('mol_box', None)
                    if mol_box is not None:
                        temp_left_top_distance = mol_box[0]**2 + mol_box[1]**2
                        if temp_left_top_distance < left_top_distance:
                            left_top_id = block_idx
                
                total_result_dict[page_idx] = [total_result[left_top_id]]
    
    ## TODO 每个都需要1s
    def adjust_image_and_mode(self, large_label_image, label_image, mode):
        start = time.time()
        temp_mode = mode
        angle_list = [0, Image.ROTATE_90, Image.ROTATE_270] #先不考虑180
        if temp_mode == "auto":
            chi_df_list = []
            max_chi_idx = None
            for chi_idx, angle in enumerate(angle_list):
                if angle == 0:
                    chi_df = pytesseract.image_to_data(large_label_image, output_type=pytesseract.Output.DATAFRAME, lang='chi_sim+eng')
                else:
                    chi_df = pytesseract.image_to_data(large_label_image.transpose(angle), output_type=pytesseract.Output.DATAFRAME, lang='chi_sim+eng')

                chi_df = chi_df[chi_df["conf"]!=-1]
                chi_df_list.append(chi_df)
                if max_chi_idx is None:
                    max_chi_idx = chi_idx
                else:
                    chi_df_confidence = chi_df["conf"].mean()
                    if max_chi_idx != 0:
                        if chi_df_list[max_chi_idx]["conf"].mean()<chi_df_confidence:
                            max_chi_idx = chi_idx
                    else:
                        if chi_df_list[max_chi_idx]["conf"].mean()<chi_df_confidence-10 and chi_df_confidence>5:
                            max_chi_idx = chi_idx


            # chi_df_confidence = chi_df["conf"].mean()
            chi_df_out = "\n".join(chi_df_list[max_chi_idx]["text"].astype(str))

            eng_df_list = []
            max_eng_idx = None
            for eng_idx, angle in enumerate(angle_list):
                if angle == 0:
                    eng_df = pytesseract.image_to_data(large_label_image, output_type=pytesseract.Output.DATAFRAME, lang='eng')
                else:
                    eng_df = pytesseract.image_to_data(large_label_image.transpose(angle), output_type=pytesseract.Output.DATAFRAME, lang='eng')

                eng_df = eng_df[eng_df["conf"]!=-1]
                eng_df_list.append(eng_df)

                if max_eng_idx is None:
                    max_eng_idx = eng_idx
                else:
                    eng_df_confidence = eng_df["conf"].mean()
                    if max_eng_idx != 0:
                        if eng_df_list[max_eng_idx]["conf"].mean()<eng_df_confidence:
                            max_eng_idx = eng_idx
                    else:
                        if eng_df_list[max_eng_idx]["conf"].mean()<eng_df_confidence-10 and eng_df_confidence>=75:
                            max_eng_idx = eng_idx

            # eng_df_confidence = eng_df["conf"].mean()
            eng_df_out = "\n".join(eng_df_list[max_eng_idx]["text"].astype(str))

            if eng_df_out == chi_df_out:
                # out =  pytesseract.image_to_string(large_label_image, output_type=pytesseract.Output.STRING, lang='eng')
                temp_mode = "Eng"
                angle = angle_list[max_eng_idx]
            else:
                if chi_df_list[max_chi_idx]["conf"].mean()>=75 and \
                    chi_df_list[max_chi_idx]["conf"].mean()>eng_df_list[max_eng_idx]["conf"].mean()+10:
                    angle = angle_list[max_chi_idx]
                    temp_mode = "Chi"
                else:
                    angle = angle_list[max_eng_idx]
                    temp_mode = "Eng"
        
        elif temp_mode == "Eng":
            eng_df_list = []
            max_eng_idx = None
            for eng_idx, angle in enumerate(angle_list):
                if angle == 0:
                    eng_df = pytesseract.image_to_data(large_label_image, output_type=pytesseract.Output.DATAFRAME, lang='eng')
                else:
                    eng_df = pytesseract.image_to_data(large_label_image.transpose(angle), output_type=pytesseract.Output.DATAFRAME, lang='eng')
                    
                eng_df = eng_df[eng_df["conf"]!=-1]
                eng_df_list.append(eng_df)

                if max_eng_idx is None:
                    max_eng_idx = eng_idx
                else:
                    eng_df_confidence = eng_df["conf"].mean()
                    if max_eng_idx != 0:
                        if eng_df_list[max_eng_idx]["conf"].mean()<eng_df_confidence:
                            max_eng_idx = eng_idx
                    else:
                        if eng_df_list[max_eng_idx]["conf"].mean()<eng_df_confidence-10 and eng_df_confidence>75:
                            max_eng_idx = eng_idx

            angle = angle_list[max_eng_idx]
        
        elif temp_mode == "Chi":
            chi_df_list = []
            max_chi_idx = None
            for chi_idx, angle in enumerate(angle_list):
                if angle == 0:
                    chi_df = pytesseract.image_to_data(large_label_image, output_type=pytesseract.Output.DATAFRAME, lang='chi_sim+eng')
                else:
                    eng_df = pytesseract.image_to_data(large_label_image.transpose(angle), output_type=pytesseract.Output.DATAFRAME, lang='chi_sim+eng')
                chi_df = chi_df[chi_df["conf"]!=-1]
                chi_df_list.append(chi_df)
                if max_chi_idx is None:
                    max_chi_idx = chi_idx
                else:
                    chi_df_confidence = chi_df["conf"].mean()
                    if max_chi_idx != 0:
                        if chi_df_list[max_chi_idx]["conf"].mean()<chi_df_confidence:
                            max_chi_idx = chi_idx
                    else:
                        if chi_df_list[max_chi_idx]["conf"].mean()<chi_df_confidence-10 and chi_df_confidence>75:
                            max_chi_idx = chi_idx
            angle = angle_list[max_chi_idx]
        
        # if temp_mode == "Chi":
        #     import ipdb
        #     ipdb.set_trace()
        if angle != 0:
            label_image = label_image.rotate(angle)
            print("angle",angle)
        print(f"mode+osd:{time.time()-start:.3f}")
        return label_image, temp_mode
    
    def read_image(self, image):
        """读取或者校验PIL.PngImagePlugin.PngImageFile图像

        Args:
            image (PIL.PngImagePlugin.PngImageFile or str): _description_

        Returns:
            image: PIL.PngImagePlugin.PngImageFile
        """
         
        if isinstance(image, PIL.PngImagePlugin.PngImageFile):
            pass
        else:
            if isinstance(image, str) and os.path.exists(image):
                image = Image.open(image).convert("RGB")
            else:
                self.logger.error("`the type of image` is not in [`PIL.PngImagePlugin.PngImageFile`, `str`]")
                raise ValueError("`the type of image` is not in [`PIL.PngImagePlugin.PngImageFile`, `str`]")
        return image
    
    def test_tesseract(self, image):
        """测试tesseract

        Args:
            image (PIL.PngImagePlugin.PngImageFile or str): 图像或者路径
        
        Returns:
            result (str): 常规文本，
        """
        image = self.read_image(image)
        config='-l eng --oem 3 --psm 6 --dpi 72' #300 # -c tessedit_char_whitelist="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789().calmg* " +lat
        result = remove_upprintable_chars(pytesseract.image_to_string(image, config=config)).replace("\n\n", "\n")
        return result
    
    def test_docTR(self, image):
        """测试docTR

        Args:
            image (PIL.PngImagePlugin.PngImageFile or str): 图像或者路径
        
        Returns:
            result (str): 常规文本，
        """
        image = self.read_image(image)
        if self.doctr_model is None:
            self.doctr_model = self.get_doctr_model()
        result = self.get_doctr_result(image)
        return result

    def test_easyocr(self, image):
        """测试easyOCR

        Args:
            image (PIL.PngImagePlugin.PngImageFile or str): 图像或者路径
        
        Returns:
            result (str): 常规文本，
        """
        image = self.read_image(image)
        if self.easy_ocrer is None:
            self.easy_ocrer = self.get_easyocer()
        result_dict = get_line_box_dict_with_easyocr(image, self.easy_ocrer)
        result_value_list = [_ for _ in result_dict.values()]
        result = "\n".join(result_value_list)

        return result
        

    def test_latex_ocr(self, image):
        """测试latexOCR

        Args:
            image (PIL.PngImagePlugin.PngImageFile or str): 图像或者路径

        Returns:
            string_out (str): 常规文本，
            latex_out (str): latex文本
        """
        image = self.read_image(image)
        out, latex_out = self.advanced_ocr(image)
        string_out = compress_n(latex2text(to_katex(latex_out)).replace("⋮", ""))
        return string_out, latex_out

    def got_error(self, text):
        if "!" in text:
            return True
        if "#" in text:
            return True
        return False
    



    ## OCR的测试入口
    def advanced_ocr(self, 
                     label_image:Image, 
                     large_label_image:Image=None,
                     mol_label_image:Image=None,
                     mol_label_box:List=[],
                     temp_mode:str="Eng",
                     label:str="idx", 
                     label_box:List=[], 
                     large_label_box:list=[],
                     use_doctr:bool=False,
                     debug=False):
        debug = False
        if debug:
            start = time.time()
        text_dict_with_easyocr = {}
        out = ""
        latex_out = ""
        if True: #label == "idx"

            if self.use_got_ocr_model:
                if self.got_ocr_model is None:
                    self.got_ocr_model, self.got_ocr_tokenizer = self.get_got_ocr_model()
                    self.logger.info("======load `got_ocr_model` from local=====")
            
            if self.use_trocr_mfr_model_v3:
                if self.trocr_mfr_model_v3 is None:
                    self.trocr_mfr_model_v3, self.trocr_mfr_processor_v3 = self.get_trocr_mfr_model_v3()
                    self.logger.info("======load `trocr_mfr_model_v3` from local=====")
            
            if (out == "") and self.got_ocr_model is not None:
                out = self.get_got_ocr_result(label_image)
                if "中 " in out:
                    temp_image = Image.fromarray(self.crop_white_fn(image=np.array(label_image),keypoints=[])["image"])
                    temp_new_image = Image.new(size=(temp_image.width*2, temp_image.height*2),mode=temp_image.mode)
                    temp_new_image.paste(temp_image, (temp_image.width//2, temp_image.height//2))
                    out = self.get_got_ocr_result(temp_new_image)
                print("got ocr:\n",out)

                ## 增加矫正
                # if (not re.search(r'[a-zA-Z0-9]', out)) or (is_valid_numeric_string(out)) or ("!" in out):
                #     out = self.get_got_ocr_result(large_label_image)
                # else:
                #     latex_out = out

                
                if ((not re.search(r'[a-zA-Z0-9]', out)) or (not is_valid_numeric_string(out)) or ("!" in out)) and (self.trocr_mfr_model_v3 is not None) and (temp_mode=="Eng"):
                    out, state = self.get_trocr_mfr_result_v3(label_image)
                    debug = True
                    if debug:
                        print("trocr_mfr_v3_latex:", out)
                        print("trocr_mfr_v3:", latex2text(to_katex(out)))
                
                    condition = False
                    condition = get_condition(latex2text(to_katex(out)))
                    if (condition) and (self.trocr_mfr_model_v3 is not None):
                        out, state = self.get_trocr_mfr_result_v3(label_image, with_crop_white=False)
                       
                    
                    condition = get_condition(latex2text(to_katex(out)))
                    if condition:
                        out = ""
                        latex_out = out
                    else:
                        out = compress_n(latex2text(remove_last_tiny(to_katex(out))).replace("⋮", ""))

                else:
                    out = out.replace("M","µM")
                    ## GOT OCR
                    if out == "(0) = 1 +":
                        out = ""
                    out = out.replace("M","µM")
                    out = out.replace("中 间 体 ", "中间体")
                    out = out.replace("- ","")
                    out = out.replace("-\n","-")
                    out = out.rstrip(",")
                    latex_out = out

            else:
                pass
                # state = True
                # if (out == "") and (self.trocr_mfr_model_v3 is not None) and (temp_mode=="Eng"):
                #     out, state = self.get_trocr_mfr_result_v3(label_image)
                #     debug = True
                #     if debug:
                #         print("trocr_mfr_v3_latex:", out)
                #         print("trocr_mfr_v3:", latex2text(to_katex(out)))
                #     debug = False

                # # # 0802
                # condition = False
                # condition = get_condition(latex2text(to_katex(out)))
                # if (condition) and (self.trocr_mfr_model_v3 is not None):
                #     out, state = self.get_trocr_mfr_result_v3(label_image, with_crop_white=False)
                #     out = latex2text(to_katex(out))
            
                # # # 0715
                # condition = False
                # condition = get_condition(latex2text(to_katex(out)))
                # if (condition) and (self.trocr_mfr_model is not None) and (state is True):
                #     latex_code = self.get_trocr_mfr_result(label_image)
                #     if "χ" in out:
                #         out = ""
                #         state = False
                #     out = latex2text(to_katex(latex_code))
                #     out = remove_upprintable_chars(out)
                #     out = out.rstrip(" \n ")
                #     out = out.lstrip(" \n ")
                #     out = out.rstrip(" \n")
                #     out = out.lstrip(" \n")
                #     out = out.rstrip("\n ")
                #     out = out.lstrip("\n ")
                #     out = out.rstrip("\n")
                #     out = out.lstrip("\n")
                #     out = out.rstrip(" ")
                #     out = out.lstrip(" ")
                #     out = compress_spaces(out)
                #     # debug = True
                #     if debug:
                #         print("trocr_mfr_latex:", latex_code)
                #         print("trocr_mfr:", out)
                #     if "χ" in out:
                #         out = ""
                #         state = False
                #     if "∂φχχ" in out:
                #         out = ""
                #         state = False
                    
                #     if "33333333" in out:
                #         out = ""
                #         state = False
                    
                    
                # if get_condition_v2(out):
                #     out = ""
                #     state = False

            out = remove_upprintable_chars(out)
        debug = False
        if debug:
            print(f"ocr:{time.time()-start:.3f}")
        return out, latex_out

    def image_ocr(self, 
                  image:Image, 
                  mol_box:list, 
                  label_box_list:list, 
                  block_image_array:np.array, 
                  padding:int, 
                  mode:str, 
                  label="idx", 
                  osd=False,
                  remove_label=False,
                  debug=False):
        
        label_string_list = []
        label_latex_string_list = []
        
        
        ## TODO 做加法
        for label_box in label_box_list:
            ## must be int
            label_box = math.floor(label_box[0]), math.floor(label_box[1]), math.ceil(label_box[2]), math.ceil(label_box[3])
            out = ""

            ## 去除空白
            if (label_box[0] >= label_box[2]) or (label_box[1] >= label_box[3]):
                label_string_list.append(out)
                continue

            # self.logger.info("======get label form label_image======")
            try:
                label_image = image.crop(label_box)
            except Exception as e:
                print(e)
                print(label_box)
                continue

            ## 屏蔽文字
            ## TODO 加额外条件
            if remove_label:
                if (mol_box[2]-label_box[0])*(label_box[2]-mol_box[0])>0 and (mol_box[3]-label_box[1])*(label_box[3]-mol_box[1])>0:
                    label_result = self.crop_white_fn(image=np.array(cv2.cvtColor(np.array(label_image), cv2.COLOR_RGB2BGR)), 
                                                        keypoints=[(0,0), (label_image.width, label_image.height)])
                    cover_label_box = (
                                    label_box[0]-label_result["keypoints"][0][0], 
                                    label_box[1]-label_result["keypoints"][0][1],
                                    label_box[0]-label_result["keypoints"][0][0] + label_result["image"].shape[0],
                                    label_box[1]-label_result["keypoints"][0][1] + label_result["image"].shape[1],
                                    )
                    temp_array = block_image_array[int(cover_label_box[1]-mol_box[1]):int(cover_label_box[3]-mol_box[1]),
                                    int(cover_label_box[0]-mol_box[0]):int(cover_label_box[2]-mol_box[0]),
                                    :]
                    if np.prod(temp_array.shape[:2])/np.prod(label_image.size)>=0.1:
                        block_image_array[int(cover_label_box[1]-mol_box[1]):int(cover_label_box[3]-mol_box[1]),
                                        int(cover_label_box[0]-mol_box[0]):int(cover_label_box[2]-mol_box[0]),
                                        :] = 255

            # label_image = ocr_precessing(label_image)
            # label_image = Image.fromarray(label_image).convert('RGB')

            text_dict = {}
            text_dict_with_easyocr={}

            large_label_box = (
                max( label_box[0] - padding, 0),
                max( label_box[1] - padding, 0),
                min( label_box[2] + padding, image.size[0]),
                min( label_box[3] + padding, image.size[1]),
            )
            try:
                # large_label_image =  Image.fromarray(ocr_precessing(image.crop(large_label_box))).convert('RGB')
                large_label_image = image.crop(large_label_box)
            except:
                large_label_image =  Image.fromarray(ocr_precessing(image.crop(label_box))).convert('RGB')
            
            try:
                mol_label_box = (
                    min( label_box[0] , mol_box[0]),
                    min( label_box[1] , mol_box[1]),
                    max( label_box[2] , mol_box[2]),
                    max( label_box[3] , mol_box[3]),
                )
                mol_label_image =  Image.fromarray(ocr_precessing(image.crop(mol_label_box))).convert('RGB')
            except:
                mol_label_box = label_box
                mol_label_image = None

            ## 强制temp_mode="Eng"
            temp_mode = "Eng"

            # label_image, temp_mode = self.adjust_image_and_mode(large_label_image, label_image, mode)
            
            out, latex_out = self.advanced_ocr(label_image, 
                                    large_label_image, 
                                    mol_label_image, 
                                    mol_label_box, 
                                    temp_mode, 
                                    label, 
                                    label_box, 
                                    large_label_box, 
                                    debug)
            # out = self.get_trocr_result(label_image)
            # if "\\begin{" in out:
            if out in ["CH3", "HCI", "HCl", "is", "TFA calt", "HCI salt", "Me", "HCl盐", "TFA盐", "TFA"]:
                label_string_list.append("")
            else:
                label_string_list.append(out)
            label_latex_string_list.append(latex_out)

            # else:

            #     ## 解决跨行问题
            #     if self.easy_ocrer is None:
            #         self.easy_ocrer = self.get_easyocer()

            #     temp_dict = get_text_box_dict_with_easyocr(label_image, self.easy_ocrer)
            #     if len(temp_dict)>1:
            #         import ipdb
            #         ipdb.set_trace()
            #         heights = []
            #         for box, content in temp_dict.items():
            #             heights.append(box[3]-box[1])
            #
            #         average_height = np.mean(heights)
            #         get_line_box_dict_with_easyocr(image, self.easy_ocrer, average_height)
            #     else:
            #         ## 只有一个元素
            #         for box, content in temp_dict.items():
            #             label_string_list.append(content)
        
        return label_string_list, label_latex_string_list
                

    def get_mol_image_and_with_label_ocr(self, 
                                        image:Image,
                                        total_result:list=[],
                                        with_molscribe=True, 
                                        mode="Eng", 
                                        start_offset=0,
                                        with_ocr=False,
                                        padding=10,
                                        debug=False):
        
        ## TODO mode_list:
        block_image_list = []
        
        ## 先用easy_ocr进行识别
        remove_box_ids = []
        for block_idx, box_dict in enumerate(total_result):
            mol_box = box_dict.get('mol_box', None)
            if mol_box is not None:
                if start_offset !=0:
                    if (mol_box[1]+mol_box[3])/2<start_offset:
                        remove_box_ids.append(block_idx)
                        continue
                    
                
                if with_molscribe:
                    block_image = image.crop(mol_box)
                    block_image_array = cv2.cvtColor(np.array(block_image), cv2.COLOR_RGB2BGR)
                    ## crop_white
                    # block_image_array = self.crop_white_fn(image=block_image_array, keypoints=[])["image"]
                    height, width, _ = block_image_array.shape
                    block_image_array = remove_horizontal_and_vertical_line(block_image_array, horizontal_size=int(width*0.5), vertical_size=int(height*0.5))
                    block_image_list.append(block_image_array)
            
            if debug:
                start = time.time()
            label_box_list = box_dict.get('label_box_list', [])
            if with_ocr:
                label_string_list, label_latex_string_list = self.image_ocr(image, 
                                                                            mol_box, 
                                                                            label_box_list, 
                                                                            block_image_array, 
                                                                            padding, 
                                                                            mode, 
                                                                            label="idx")
            else:
                label_string_list, label_latex_string_list = [""]*len(label_box_list), [""]*len(label_box_list)

            ## 去重
            for temp_i in range(len(label_string_list)):
                if len(label_string_list[temp_i].split("\n"))>1:
                    label_string_list[temp_i]  = "\n".join(list(set(label_string_list[temp_i].split(" \n "))))
                    label_string_list[temp_i]  = "\n".join(list(set(label_string_list[temp_i].split(" \n"))))
                    label_string_list[temp_i]  = "\n".join(list(set(label_string_list[temp_i].split("\n "))))
                    label_string_list[temp_i]  = "\n".join(list(set(label_string_list[temp_i].split("\n"))))
            
            ## 过滤掉trans A
            temp_label_box_list = []
            temp_label_string_list = []
            temp_label_latex_string_list = []
            for temp_i in range(len(label_string_list)):
                if label_string_list[temp_i] in ["trans", "trans A", "trans B", "cis", "cis racemic", "trans racemic", "E and Z"]:
                    self.logger.info(f"filter {label_string_list[temp_i]}")
                elif label_string_list[temp_i].startswith("mixture of"):
                    self.logger.info(f"filter {label_string_list[temp_i]}")
                else:
                    temp_label_box_list.append(label_box_list[temp_i])
                    temp_label_string_list.append(label_string_list[temp_i])
                    temp_label_latex_string_list.append(label_latex_string_list[temp_i])
            
            if len(label_box_list) != len(temp_label_box_list):
                label_box_list = temp_label_box_list
                label_string_list = temp_label_string_list
                label_latex_string_list = temp_label_latex_string_list


            # print(1, label_string_list)
            ## IC50 提取
            temp_label_box_list = []
            temp_label_string_list = []
            temp_label_latex_string_list = []
            extra_text_box_list = []
            extra_text_string_list = []
            extra_text_latex_string_list = []

            ## TODO  最好写成列表的形式
            for temp_i in range(len(label_string_list)):
                label_string = label_string_list[temp_i]
                temp_prefix_list = []
                temp_ic50_list = []
                for temp_label_string in label_string.split("\n"):
                    temp_result = extract_ic50_with_prefix(temp_label_string)
                    ## 保持原状
                    if len(temp_result)==0:
                        temp_prefix_list.append(temp_label_string)
                    else:
                        for prefix, ic50_value in temp_result:
                            prefix = prefix.lstrip(" ")
                            prefix = prefix.rstrip(" ") 
                            prefix = prefix.rstrip(",")
                            prefix = prefix.rstrip(".")
                            if len(prefix)>0:
                                temp_prefix_list.append(prefix)
                            
                            ## 超过两行,保留前面的序号
                            if len(prefix)>0 and len(label_string.split("\n"))>1:
                                temp_ic50_list.append(prefix+";"+ic50_value)
                            else:
                                temp_ic50_list.append(ic50_value)

                if len(temp_prefix_list)>0:
                    last_prefix = "\n".join(temp_prefix_list)
                    temp_label_box_list.append(label_box_list[temp_i])
                    temp_label_string_list.append(last_prefix)
                    temp_label_latex_string_list.append(label_latex_string_list[temp_i])
                
                if len(temp_ic50_list)>0:
                    last_ic50_value = "\n".join(temp_ic50_list)
                    extra_text_box_list.append(label_box_list[temp_i])
                    extra_text_string_list.append(last_ic50_value)
                    extra_text_latex_string_list.append(label_latex_string_list[temp_i])
            
            box_dict['label_box_list'] = temp_label_box_list
            label_string_list = temp_label_string_list
            label_latex_string_list = temp_label_latex_string_list
            box_dict["label_string"] = label_string_list
            box_dict["label_latex_string"] = label_latex_string_list

            # print(2, label_string_list)

            ## 去除·的合成·和·的制备·
            for temp_i in range(len(box_dict["label_string"])):
                if box_dict["label_string"][temp_i].endswith("的制备"):
                    box_dict["label_string"][temp_i] = box_dict["label_string"][temp_i][:-3]
                if box_dict["label_string"][temp_i].endswith("的制备："):
                    box_dict["label_string"][temp_i] = box_dict["label_string"][temp_i][:-4]
                if box_dict["label_string"][temp_i].endswith("的制备:"):
                    box_dict["label_string"][temp_i] = box_dict["label_string"][temp_i][:-4]
                if box_dict["label_string"][temp_i].endswith("的合成"):
                    box_dict["label_string"][temp_i] = box_dict["label_string"][temp_i][:-3]
                if box_dict["label_string"][temp_i].endswith("的合成："):
                    box_dict["label_string"][temp_i] = box_dict["label_string"][temp_i][:-4]
                if box_dict["label_string"][temp_i].endswith("的合成:"):
                    box_dict["label_string"][temp_i] = box_dict["label_string"][temp_i][:-4]

            ## 去除example中冗余的部分
            for temp_i in range(len(box_dict["label_string"])):
                if len(box_dict["label_string"][temp_i])<=16:
                    temp_result = extract_example_v2(box_dict["label_string"][temp_i])
                    box_dict["label_string"][temp_i] = temp_result   

            ## rgroup 抽取
            ## TODO 请加回来
            # temp_label_box_list = []
            # temp_label_string_list = []
            # temp_label_latex_string_list = []
            extra_rgroup_box_list = []
            extra_rgroup_string_list = []
            extra_rgroup_latex_string_list = []

            ## formular 进行处理
            temp_label_box_list = []
            temp_label_string_list = []
            temp_label_latex_string_list = []
            for temp_i in range(len(box_dict["label_string"])):
                if len(box_dict["label_string"][temp_i]) <= 12 and \
                    ("formular " in box_dict["label_string"][temp_i].lower()) or \
                    (" formular" in box_dict["label_string"][temp_i].lower()) or \
                    ("formula " in box_dict["label_string"][temp_i].lower()) or \
                    (" formula" in box_dict["label_string"][temp_i].lower()) or \
                    ("formula(" in box_dict["label_string"][temp_i].lower()) or \
                    ("formular(" in box_dict["label_string"][temp_i].lower()):
                    try:
                        extract_formula_result = extract_formula(box_dict["label_string"][temp_i])[0][1]
                        if len(box_dict["label_string"]) == 1:
                            temp_label_string_list.append(extract_formula_result)
                            temp_label_box_list.append(box_dict["label_box_list"][temp_i])
                            temp_label_latex_string_list.append(box_dict["label_latex_string"][temp_i])
                        else:
                            ## 去除重复的
                            if extract_formula_result in box_dict["label_string"]:
                                ## 先用空白占位吧，方便可视化
                                temp_label_string_list.append("")
                                temp_label_box_list.append(box_dict["label_box_list"][temp_i])
                                temp_label_latex_string_list.append(box_dict["label_latex_string"][temp_i])
                            else:
                                temp_label_string_list.append(extract_formula_result)
                                temp_label_box_list.append(box_dict["label_box_list"][temp_i])
                                temp_label_latex_string_list.append(box_dict["label_latex_string"][temp_i])
                    except Exception as e:
                        print(e)
                        temp_label_string_list.append(box_dict["label_string"][temp_i])
                        temp_label_box_list.append(box_dict["label_box_list"][temp_i])
                        temp_label_latex_string_list.append(box_dict["label_latex_string"][temp_i])

                else:
                    temp_label_string_list.append(box_dict["label_string"][temp_i])
                    temp_label_box_list.append(box_dict["label_box_list"][temp_i])
                    temp_label_latex_string_list.append(box_dict["label_latex_string"][temp_i])

            box_dict['label_box_list'] = temp_label_box_list
            box_dict["label_string"] = temp_label_string_list
            box_dict["label_latex_string"] = temp_label_latex_string_list
            label_box_list = temp_label_box_list
            label_string_list = temp_label_string_list
            label_latex_string_list = temp_label_latex_string_list

            ## 这边加一个过滤条件把
            ## 检查一下example 和 compound/intermediate是否同时存在
            ## 有些化学反应会把example作为标签，
            ## 为了保证召回率
            example_flag = False
            compound_flag = False
            pure_number_flag = False
            example_index_list = []
            compound_index_list = []
            for temp_i in range(len(box_dict["label_string"])):
                if "example" in box_dict["label_string"][temp_i].lower():
                    try:
                        example = extract_example(box_dict["label_string"][temp_i])[0][1]
                        if example in box_dict["label_string"] or "(" + example + ")" in box_dict["label_string"]:
                            for temp_j in range(len(box_dict["label_string"])):
                                if box_dict["label_string"][temp_j] == example or box_dict["label_string"][temp_j] == "(" + example + ")":
                                    example_index_list.append(temp_j)
                            example_flag = True
                        else:
                            example_flag = True
                            example_index_list.append(temp_i)
                    except Exception as e:
                        print(e)
                
                elif "实施例" in box_dict["label_string"][temp_i] or "实例" in box_dict["label_string"][temp_i]:
                    try:
                        shishili = extract_shishili(box_dict["label_string"][temp_i])[0][1]
                        if shishili in box_dict["label_string"] or "(" + shishili + ")" in box_dict["label_string"]:
                            for temp_j in range(len(box_dict["label_string"])):
                                if box_dict["label_string"][temp_j] == shishili or box_dict["label_string"][temp_j] == "(" + shishili + ")":
                                    example_index_list.append(temp_j)
                            example_flag = True
                        else:
                            example_flag = True
                            example_index_list.append(temp_i)
                    except Exception as e:
                        print(e)
                
                elif "compound" in box_dict["label_string"][temp_i].lower():
                    try:
                        compound = extract_compound(box_dict["label_string"][temp_i])[0][1]
                        if compound in box_dict["label_string"] or "(" + compound + ")" in box_dict["label_string"]:
                            for temp_j in range(len(box_dict["label_string"])):
                                if box_dict["label_string"][temp_j] == compound or box_dict["label_string"][temp_j] == "(" + compound + ")":
                                    compound_index_list.append(temp_j)
                            compound_flag = True
                        else:
                            compound_flag = True
                            compound_index_list.append(temp_i)
                    except Exception as e:
                        print(e)
                
                elif "化合物" in box_dict["label_string"][temp_i].lower():
                    try:
                        compound =  extract_huahewu(box_dict["label_string"][temp_i])[0][1]
                        if compound in box_dict["label_string"] or "(" + compound + ")" in box_dict["label_string"]:
                            for temp_j in range(len(box_dict["label_string"])):
                                if box_dict["label_string"][temp_j] == compound or box_dict["label_string"][temp_j] == "(" + compound + ")":
                                    compound_index_list.append(temp_j)
                            compound_flag = True
                        else:
                            compound_flag = True
                            compound_index_list.append(temp_i)
                    except Exception as e:
                        print(e)
                
                elif "intermediate" in box_dict["label_string"][temp_i].lower():
                    try:
                        intermediate = extract_intermediate(box_dict["label_string"][temp_i])[0][1]
                        if intermediate in box_dict["label_string"] or "(" + intermediate + ")" in box_dict["label_string"]:
                            for temp_j in range(len(box_dict["label_string"])):
                                if box_dict["label_string"][temp_j] == intermediate or box_dict["label_string"][temp_j] == "(" + intermediate + ")":
                                    compound_index_list.append(temp_j)
                            compound_flag = True
                        else:
                            compound_flag = True
                            compound_index_list.append(temp_i)
                    except Exception as e:
                        print(e)
                
                elif "中间体" in box_dict["label_string"][temp_i].lower():
                    try:
                        intermediate = extract_zhongjianti(box_dict["label_string"][temp_i])[0][1]
                        if intermediate in box_dict["label_string"] or "(" + intermediate + ")" in box_dict["label_string"]:
                            for temp_j in range(len(box_dict["label_string"])):
                                if box_dict["label_string"][temp_j] == intermediate or box_dict["label_string"][temp_j] == "(" + intermediate + ")":
                                    compound_index_list.append(temp_j)
                            compound_flag = True
                        else:
                            compound_flag = True
                            compound_index_list.append(temp_i)
                    except Exception as e:
                        print(e)

                elif is_number_or_roman_with_parentheses(box_dict["label_string"][temp_i]):
                    pure_number_flag = True
            
            if example_flag is True and (compound_flag is True or pure_number_flag is True):
                temp_label_box_list = []
                temp_label_string_list = []
                temp_label_latex_string_list = []
                for temp_i in range(len(box_dict["label_string"])):
                    if temp_i not in example_index_list:
                        temp_label_string_list.append(box_dict["label_string"][temp_i])
                        temp_label_box_list.append(box_dict["label_box_list"][temp_i])
                        temp_label_latex_string_list.append(box_dict["label_latex_string"][temp_i])
                box_dict['label_box_list'] = temp_label_box_list
                box_dict["label_string"] = temp_label_string_list
                box_dict["label_latex_string"] = temp_label_latex_string_list
                label_box_list = temp_label_box_list
                label_string_list = temp_label_string_list
                label_latex_string_list = temp_label_latex_string_list
            
            if compound_flag is True and pure_number_flag is True:
                temp_label_box_list = []
                temp_label_string_list = []
                temp_label_latex_string_list = []
                for temp_i in range(len(box_dict["label_string"])):
                    if temp_i not in compound_index_list:
                        temp_label_string_list.append(box_dict["label_string"][temp_i])
                        temp_label_box_list.append(box_dict["label_box_list"][temp_i])
                        temp_label_latex_string_list.append(box_dict["label_latex_string"][temp_i])
                box_dict['label_box_list'] = temp_label_box_list
                box_dict["label_string"] = temp_label_string_list
                box_dict["label_latex_string"] = temp_label_latex_string_list
                label_box_list = temp_label_box_list
                label_string_list = temp_label_string_list
                label_latex_string_list = temp_label_latex_string_list
            
            ## 去除"\n",重复的
            for temp_i in range(len(box_dict["label_string"])):
                if len(box_dict["label_string"][temp_i].split("\n"))>1:
                    box_dict["label_string"][temp_i]  = "\n".join(list(set(box_dict["label_string"][temp_i].split(" \n "))))
                    box_dict["label_string"][temp_i]  = "\n".join(list(set(box_dict["label_string"][temp_i].split(" \n"))))
                    box_dict["label_string"][temp_i]  = "\n".join(list(set(box_dict["label_string"][temp_i].split("\n "))))
                    box_dict["label_string"][temp_i]  = "\n".join(list(set(box_dict["label_string"][temp_i].split("\n"))))
            
            temp_label_box_list = []
            temp_label_string_list = []
            temp_label_latex_string_list = []
            ## 处理括号42(W4275) ——> 42, (W4275) ——>42, W4275
            for temp_i in range(len(label_string_list)):
                label_string = label_string_list[temp_i]

                temp_split_list = []
                ## 改成列表的形式
                for temp_label_string in label_string.split("\n"):
                    split_text = split_content(label_string)

                    if split_text[1] == None:
                        temp_split_list.append(temp_label_string)
                    else:
                        ## 原始字符串，先不保留了
                        # temp_split_list.append(temp_label_string) ## 保留原始的
                        if split_text[0]!="":
                            temp_split_list.append(split_text[0])
                        
                        temp_split_list.append(split_text[1][1:-1])
                
                for split_text in temp_split_list:
                    temp_label_box_list.append(label_box_list[temp_i])
                    temp_label_string_list.append(split_text)
                    temp_label_latex_string_list.append(label_latex_string_list[temp_i])

            box_dict['label_box_list'] = temp_label_box_list
            label_string_list = temp_label_string_list
            label_latex_string_list = temp_label_latex_string_list

            box_dict["label_string"] = label_string_list
            box_dict["label_latex_string"] = label_latex_string_list
            # print(3, box_dict["label_string"])
            if debug:
                print(f"1, {time.time()-start:.3f}")
            
            ## 去除step
            for temp_i in range(len(box_dict["label_string"])):
                if len(box_dict["label_string"][temp_i]) <= 8 and \
                    ("step " in box_dict["label_string"][temp_i].lower()) or \
                    (" step" in box_dict["label_string"][temp_i].lower()):
                    box_dict["label_string"][temp_i] = ""
            
            ## 去重
            temp_label_box_list = []
            temp_label_string_list = []
            temp_label_latex_string_list = []
            for temp_i in range(len(box_dict["label_string"])):
                if box_dict["label_string"][temp_i] not in temp_label_string_list:
                    temp_label_string_list.append(box_dict["label_string"][temp_i])
                    temp_label_box_list.append(box_dict["label_box_list"][temp_i])
                    temp_label_latex_string_list.append(box_dict["label_latex_string"][temp_i])
            if len(temp_label_string_list)<len(box_dict["label_string"]):
                box_dict['label_box_list'] = temp_label_box_list
                label_string_list = temp_label_string_list
                label_latex_string_list = temp_label_latex_string_list
                box_dict["label_string"] = label_string_list
                box_dict["label_latex_string"] = label_latex_string_list

            
            if debug:
                start = time.time()
            text_box_list = box_dict.get('text_box_list', [])
            if with_ocr:
                text_string_list, text_latex_string_list = self.image_ocr(image, mol_box, text_box_list, block_image_array, padding, mode, label="text")
            else:
                text_string_list, text_latex_string_list = [""]*len(text_box_list), [""]*len(text_box_list)

            box_dict["text_string"] = text_string_list
            box_dict["text_latex_string"] = text_latex_string_list
            if debug:
                print(f"2, {time.time()-start}")
            
            if "text_box_list" not in box_dict:
                box_dict["text_box_list"] = []
            if len(extra_text_string_list)>0:
                for temp_i in range(len(extra_text_string_list)):
                    extra_text_string = extra_text_string_list[temp_i]
                    if extra_text_string not in box_dict["text_string"]:
                        box_dict["text_string"].append(extra_text_string)
                        box_dict["text_box_list"].append(extra_text_box_list[temp_i])
                        box_dict["text_latex_string"].append(extra_text_latex_string_list[temp_i])
            

            ## 过滤掉trans A
            temp_text_box_list = []
            temp_text_string_list = []
            temp_text_latex_string_list = []
            for temp_i in range(len(box_dict["text_string"])):
                if box_dict["text_string"][temp_i] in ["trans", "trans A", "trans B", "cis", "cis racemic", "trans racemic", "E and Z"]:
                    self.logger.info(f'filter {box_dict["text_string"][temp_i]}')
                # elif box_dict["text_string"][temp_i].startswith("mixture of"):
                #     self.logger.info(f'filter {box_dict["text_string"][temp_i]}')
                else:
                    temp_text_box_list.append(box_dict["text_box_list"][temp_i])
                    temp_text_string_list.append(box_dict["text_string"][temp_i])
                    temp_text_latex_string_list.append(box_dict["text_latex_string"][temp_i])
            
            if len(box_dict["text_string"]) != len(temp_text_string_list):
                text_box_list = temp_text_box_list
                text_string_list = temp_text_string_list
                text_latex_string_list = temp_text_latex_string_list
                box_dict["text_box_list"] = temp_text_box_list
                box_dict["text_string"] = temp_text_string_list
                box_dict["text_latex_string"] = temp_text_latex_string_list

            
            if debug:
                start = time.time()
            rgroup_box_list = box_dict.get('rgroup_box_list', [])
            rgroup_string_list, rgroup_latex_string_list = [""] * len(rgroup_box_list), [""] * len(rgroup_box_list)
            # rgroup_string_list, rgroup_latex_string_list = self.image_ocr(image, mol_box, rgroup_box_list, block_image_array, padding, mode, label="rgroup")
            box_dict["rgroup_string"] = rgroup_string_list
            box_dict["rgroup_latex_string"] = rgroup_latex_string_list
            if debug:
                print(f"2, {time.time()-start}")
            
            if "rgroup_box_list" not in box_dict:
                box_dict["rgroup_box_list"] = []
            if len(extra_rgroup_string_list)>0:
                for temp_i in range(len(extra_rgroup_string_list)):
                    extra_rgroup_string = extra_rgroup_string_list[temp_i]
                    if extra_rgroup_string not in box_dict["rgroup_string"]:
                        box_dict["rgroup_string"].append(extra_rgroup_string)
                        box_dict["rgroup_box_list"].append(extra_rgroup_box_list[temp_i])
                        box_dict["rgroup_latex_string"].append(extra_rgroup_latex_string_list[temp_i])
            
            if debug:
                start = time.time()
            iupac_box_list = box_dict.get('iupac_box_list', [])
            iupac_string_list, iupac_latex_string_list = [""] * len(iupac_box_list), [""] * len(iupac_box_list)
            # iupac_string_list, iupac_latex_string_list = self.image_ocr(image, mol_box, iupac_box_list, block_image_array, padding, mode, label="iupac")
            # box_dict["iupac_string"] = iupac_string_list
            # ## TODO add post-process
            # for temp_ in box_dict["iupac_string"]:
            #     temp_ = temp_.replace("\n ", "")
            #     temp_ = temp_.replace("–", "-")
            #     # 去除非字母和数字前后的空格
            #     temp_ = re.sub(r'(?<=\W)\s+|\s+(?=\W)', '', temp_)

            box_dict["iupac_string"] = iupac_string_list
            box_dict["iupac_latex_string"] = iupac_latex_string_list
            # print(box_dict["iupac_latex_string"])
            # print(box_dict["iupac_string"])
            if debug:
                print(f"2, {time.time()-start}")
            
        return block_image_list

    def table_with_ocr(self, image, table, total_result, temp_mode="auto", debug=False):
        text_dict = {}
        text_dict_with_easyocr = {}

        if self.use_got_ocr_model:
            if self.got_ocr_model is None:
                self.got_ocr_model, self.got_ocr_tokenizer = self.get_got_ocr_model()
                self.logger.info("======load `got_ocr_model` from local=====")
        
        if self.use_trocr_mfr_model_v3:
            if self.trocr_mfr_model_v3 is None:
                self.trocr_mfr_model_v3, self.trocr_mfr_processor_v3 = self.get_trocr_mfr_model_v3()
                self.logger.info("======load `trocr_mfr_model_v3` from local=====")
        
        ## 把box变大
        table_box = (
                    max(table.bbox.x1-10, 0), 
                    max(table.bbox.y1-10, 0),
                    min(table.bbox.x2+10, image.width),
                    min(table.bbox.y2+10, image.height),
                    )
        
        table_image = image.crop(table_box)

        temp_mode_i = "Eng"
                
        # 0730
        text_dict_with_mfr = OrderedDict({})
        
        count = 0
        ## 记录每一行的结果
        every_count_list = []
        cell_box_dict = {}
        for row in table.content.values():
            every_count = 0
            for cell_idx, cell in enumerate(row):
                ## 去除空的cell
                cell_box = (cell.bbox.x1, 
                            cell.bbox.y1, 
                            cell.bbox.x2, 
                            cell.bbox.y2)
                
                cell.value = ""

                ## 过滤掉
                if (cell_box[0] >= cell_box[2]) or (cell_box[1] >= cell_box[3]):
                    continue
                # cell_box = (max(cell.bbox.x1-0, 0), 
                #             max(cell.bbox.y1-5, 0),
                #             min(cell.bbox.x2+0, image.width),
                #             min(cell.bbox.y2+5, image.height))
                
                mol_Flag = False
                iou_with_mol_list = []
                x1, y1, x2, y2 = cell_box
                for block_idx, box_dict in enumerate(total_result):
                    mol_box = box_dict.get("mol_box")
                    x3, y3, x4, y4 = mol_box
                    
                    left = max(x1, x3)
                    top = max(y1, y3)
                    right = min(x2, x4)
                    bottom = min(y2, y4)
                    
                    # 计算交集面积
                    intersection = max(0, right - left) * max(0, bottom - top)
                    iou_with_mol = intersection/((x4-x3+1)*(y4-y3+1))
                    iou_with_mol_list.append(iou_with_mol)
                
                temp_a = np.array(iou_with_mol_list)
                ## 降序排列，优先考虑大的
                for temp_idx in np.argsort(-temp_a):
                    if temp_a[temp_idx]>=0.4:
                        ## 选择交集>0.5的结果
                        total_result[temp_idx]["table_state"] = "in_table"
                        cell.value = total_result[temp_idx]
                        mol_Flag = True
                        ## 把表格中的索引添加到表格中
                        # if cell_idx == 1:
                        #     previous_cell = row[cell_idx-1]
                        #     previous_cell_value = previous_cell.value
                        #     ## 如果不是字典
                        #     if (isinstance(previous_cell_value, dict) is False) and (previous_cell_value not in total_result[temp_idx]["label_string"]):
                        #         pre_box = (previous_cell.bbox.x1, previous_cell.bbox.y1, previous_cell.bbox.x2, previous_cell.bbox.y2)
                        #         pre_image = image.crop(pre_box)
                        #         pre_image_array = cv2.cvtColor(np.asarray(pre_image),cv2.COLOR_RGB2BGR)
                        #         pre_image_result = self.crop_white_fn(image = pre_image_array, keypoints=[[0,0], [pre_image.width, pre_image.height]])
                        #         crop_pre_image = Image.fromarray(pre_image_result["image"])
                        #         new_pre_box = (previous_cell.bbox.x1 - pre_image_result["keypoints"][0][0],
                        #                        previous_cell.bbox.y1 - pre_image_result["keypoints"][0][1],
                        #                        previous_cell.bbox.x1 - pre_image_result["keypoints"][0][0] + crop_pre_image.size[0],
                        #                        previous_cell.bbox.y1 - pre_image_result["keypoints"][0][1] + crop_pre_image.size[1])
                        #         is_add = True
                        #         for label_idx, label_box in enumerate(total_result[temp_idx]["label_box_list"]):
                        #             is_add, _ = nms_without_confidence(new_pre_box, label_box, threshold=0.1, use_union=False)
                        #             if is_add is False:
                        #                 if _ != label_box:
                        #                     new_image = image.crop(_)
                        #                     out = self.get_got_ocr_result(new_image)
                        #                     if out == "":
                        #                         out, state = self.get_trocr_mfr_result_v3(new_image)
                        #                     out_plain_data = latex2text(to_katex(out))
                        #                     total_result[temp_idx]["label_box_list"][label_idx] = _
                        #                     total_result[temp_idx]["label_string"][label_idx] = out_plain_data
                        #                     total_result[temp_idx]["label_latex_string"][label_idx] = out
                        #                 break
                        #
                        #         if is_add:
                        #             total_result[temp_idx]["label_box_list"].append(new_pre_box)
                        #             total_result[temp_idx]["label_string"].append(previous_cell_value)
                        #             total_result[temp_idx]["label_latex_string"].append(previous_cell_value)

                        count = count + 1
                        every_count = every_count + 1
                        break
            
                ## TODO 不考虑没有识别出来的分子
                # if mol_Flag is False:
                #     cell_predictions = self.moldetect_model.predict_image(cell_image, coref=use_coref, ocr=use_ocr)
                #     if len(cell_predictions["bboxes"])>0:
                #         import ipdb
                #         ipdb.set_trace()
                #
                #         temp_result = get_prediction_from_moldetect_V2(cell_predictions)
                #         block_image_list = self.get_mol_image_and_with_label_ocr(cell_image, temp_result, with_molscribe)
                #         result = run_task({"image_list":block_image_list, "model_dir":self.model_dir}) #"ocr":self.easy_ocrer,
                #         for _, box_dict in enumerate(total_result):
                #             mol_box = box_dict.get('mol_box', None)
                #             box_dict["post_SMILES"] = result.loc[_, "graph_SMILES"]
                #             try:
                #                 box_dict["Cano_SMILES"] = Chem.MolToSmiles(Chem.MolFromSmiles(box_dict["post_SMILES"]))
                #             except Exception as e:
                #                 self.logger.info(f"{e}")
                #                 box_dict["Cano_SMILES"] = box_dict["post_SMILES"]
                #
                #             box_dict["post_molblock"] = result.loc[_, "molblock"]
                #
                #             box_dict["mol_box"] = (mol_box[0] + cell.bbox.x1, mol_box[1] + cell.bbox.y1, \
                #                                    mol_box[2] + cell.bbox.x1, mol_box[3] + cell.bbox.y1)
                #
                #             label_box_list = box_dict.get('label_box', [])
                #             for label_box in label_box_list:
                #                 label_box = (label_box[0] + cell.bbox.x1, label_box[1] + cell.bbox.y1, \
                #                             label_box[2] + cell.bbox.x1, label_box[3] + cell.bbox.y1)
                #         mol_Flag = True
                
                if mol_Flag is False:
                    out = ""
                    cell_image = image.crop(cell_box)
                    # cell_image = ocr_precessing(cell_image)
                    temp_width, temp_height = cell_image.size
                    cell_image = cv2.cvtColor(np.asarray(cell_image),cv2.COLOR_RGB2BGR)
                    # cell_image = remove_gray(cell_image)
                    cell_image = remove_horizontal_and_vertical_line(cell_image,  horizontal_size=int(temp_width*0.5), vertical_size=int(temp_height*0.5))
                    cell_image = Image.fromarray(cell_image)
                    
                    # 0614
                    # if out == "" and self.trocr is not None:
                    #     out = self.get_trocr_result(Image.fromarray(cell_image).convert('RGB'))
                    #     if debug:
                    #         print("trocr:", out)

                    # 0729 only for table
                    if (out == "") and self.ofa_model is not None:
                        out = self.get_ofa_result(cell_image)
                        print("ofa_model", out)
                    
                    ## 0320 先注释吧
                    # if (out == "") and self.got_ocr_model is not None:
                    #     out = self.get_got_ocr_result(cell_image)
                    
                    ## 只有非空白图片才能识别
                    if True: #is_blank_image(cell_image) is False
                        state = True
                        for local_box, value in text_dict_with_mfr.items():
                            temp_local_box = copy.deepcopy(
                                                (local_box[0], local_box[1],
                                                local_box[2], local_box[3])
                            )
                            is_add, _ = nms_without_confidence(cell_box, temp_local_box, threshold=0.2, use_union=False)
                            if is_add is False:
                                if out != "":
                                    out = out + "\n" + value
                                else:
                                    out = value
                                state = False

                        # print("trocr_mfr_v3_dict:", out)
                        # 0715
                        latex_code = ""
                        if (out == "") and (self.trocr_mfr_model_v3 is not None):
                            latex_code, state = self.get_trocr_mfr_result_v3(cell_image, with_crop_white=False)
                            out = latex2text(to_katex(latex_code))
                            if out == "t":
                                out = "+"
                            
                            if debug:
                                print("trocr_mfr_v3_latex:", latex_code)
                                print("trocr_mfr_v3:", latex2text(to_katex(latex_code)))
                                latex_code1, state = self.get_trocr_mfr_result_v3(cell_image, with_crop_white=True)
                                print("trocr_mfr_v3_1_latex:", latex_code1)
                                out1 = latex2text(to_katex(latex_code1))
                                print("trocr_mfr_v3_1:", out1)
                        
                        # # 0807
                        if self.trocr_mfr_model_v3 is not None:
                            condition = False
                            condition = get_condition(out)
                            if (condition or "\\frac" in latex_code) and (self.trocr_mfr_model_v3 is not None) and (state is False):
                                latex_code, state = self.get_trocr_mfr_result_v3(cell_image, with_crop_white=True)
                                out = latex2text(to_katex(latex_code))
                                if out == "t":
                                    out = "+"
                                if debug:
                                    print("trocr_mfr_v3_2_latex:", latex_code)
                                    print("trocr_mfr_v3_2:", out)

                        if self.trocr_mfr_model is not None:
                            condition = False
                            condition = get_condition(out)
                            if (condition) and (self.trocr_mfr_model is not None) and (state is True):
                                latex_code = self.get_trocr_mfr_result(cell_image)
                                out = latex2text(to_katex(latex_code))
                                out = remove_upprintable_chars(out)
                                out = out.rstrip(" \n ")
                                out = out.lstrip(" \n ")
                                out = out.rstrip(" \n")
                                out = out.lstrip(" \n")
                                out = out.rstrip("\n ")
                                out = out.lstrip("\n ")
                                out = out.rstrip("\n")
                                out = out.lstrip("\n")
                                out = out.rstrip(" ")
                                out = out.lstrip(" ")
                                out = compress_spaces(out)
                                if debug:
                                    print("trocr_mfr_latex:", latex_code)
                                    print("trocr_mfr:", out)
                                if "χ" in out:
                                    out = ""
                                    state = False
                                if "∂" in out:
                                    out = ""
                                    state = False
                                if "∂φχχ" in out:
                                    out = ""
                                    state = False
                                if "33333333" in out:
                                    out = ""
                                    state = False
                                if "∓∓∓∓∓∓∓∓∓" in out:
                                    out = ""
                                    state = False
                                
                                if " mam mam" in out:
                                    out = ""
                                    state = False
                                
                                if out == "t":
                                    out = "+"
                                    state = False
                            
                            if get_condition_v2(out):
                                out = ""
                                state = False

                        if (out == ""):
                            if state is False:
                                if self.got_ocr_model is not None:
                                    out = self.get_got_ocr_result(cell_image)
                                    if "中 间" in out:
                                        temp_image = Image.fromarray(self.crop_white_fn(image=np.array(cell_image),keypoints=[])["image"])
                                        temp_new_image = Image.new(size=(temp_image.width*2, temp_image.height*2),mode=temp_image.mode)
                                        temp_new_image.paste(temp_image, (temp_image.width//2, temp_image.height//2))
                                        out = self.get_got_ocr_result(temp_new_image)

                                    if out == "(0) = 1 +":
                                        out = ""
                                    out = out.replace("M","µM")
                                    out = out.replace("中 间 体 ", "中间体")
                                    out = out.replace("- ","")
                                    out = out.replace("-\n","-")
                                    out = out.rstrip(",")
                        else:
                            if (get_condition(out)):
                                if self.got_ocr_model is not None:
                                    out = self.get_got_ocr_result(cell_image)
                                    if "中 间" in out:
                                        temp_image = Image.fromarray(self.crop_white_fn(image=np.array(cell_image),keypoints=[])["image"])
                                        temp_new_image = Image.new(size=(temp_image.width*2, temp_image.height*2),mode=temp_image.mode)
                                        temp_new_image.paste(temp_image, (temp_image.width//2, temp_image.height//2))
                                        out = self.get_got_ocr_result(temp_new_image)

                                    if out == "(0) = 1 +":
                                        out = ""
                                    out = out.replace("M","µM")
                                    out = out.replace("中 间 体 ", "中间体")
                                    out = out.replace("- ","")
                                    out = out.replace("-\n","-")
                                    out = out.rstrip(",")
                    
                    if out in ["(107,108)"]:
                        out = "-"

                    # print(out)
                    out = remove_upprintable_chars(out)
                    out = out.replace("⋮", "")
                    # print(out)
                    cell.value = add_space_in_text_fn(compress_n(out))
                    # print(cell.value)

            every_count_list.append(every_count)

    def prediction_from_page(self,
                                file_path:str="",
                                page_idx_list: List[int]=[0],
                                box: Tuple[int]=None,
                                with_tta:bool=False,
                                with_layout_parser=False,
                                use_coref:bool = True,
                                use_ocr:bool=False,
                                offset_x:int = 0,
                                offset_y:int=0,
                                debug:bool = False,
                                with_molscribe:bool=True,
                                with_table:bool=False,
                                with_ocr:bool=False,
                                with_html:bool=False,
                                batch_size:int=1, ## 暂时这样吧
                                return_realative_coordinates:bool=True,
                                quick_prediction:bool=False,
                                osd_detect:bool=False,
                                return_table_html:bool=False,
                                ):
        ## 读取文件
        file_extension = os.path.splitext(file_path)[1].lower()

        ## 文件校验
        if len(page_idx_list) == 0:
            self.logger.error("the length of `page_idx_list` less than 1")
            raise Exception("the length of `page_idx_list` less than 1")

        if os.path.exists(file_path) is False:
            self.logger.error("the file_path doesn't exists")
            raise Exception("the file_path doesn't exists")

        self.logger.info(f"file extention: {file_extension}") 
        if file_extension == ".pdf":

            ## 防止把直接把索引加入
            with open(file_path, 'rb') as pdf_file:
                pdf_reader = PyPDF2.PdfReader(pdf_file)
                num_pages = len(pdf_reader.pages)
                self.logger.info(f'The number of pages in PDF is {num_pages}')
            
            page_idx_list = [page_idx for page_idx in page_idx_list if page_idx>0 and page_idx<=num_pages]
            if len(page_idx_list) == 0:
                self.logger.error("no `page_idx` in `pdf`")
                raise Exception("no `page_idx` in `pdf`")
            
            elif len(page_idx_list) == 1:
                page_idx = page_idx_list[0]
                page:Image = self.get_page_image_from_pdf(file_path, page_idx, osd_detect)

                if box is not None:
                    flag_relative_box = True

                    ## 先转化成列表，方便in-place修改
                    box = list(box)
                    assert len(box) == 4
                    width, height = page.size
                    ## 归一化坐标
                    for _ in range(len(box)):
                        if box[_] < 0:
                            box[_] = 0
                        if box[_] > 1:
                            flag_relative_box = False
                            break
                    
                    if flag_relative_box:
                        self.logger.info("======passing relative coordinates======")
                        box = [box[0]*width, box[1]*height, box[2]*width, box[3]*height]
                    else:
                        self.logger.info("======passing absolute coordinates======")

                    box[0] = max(box[0], 0)
                    box[1] = max(box[1], 0)
                    box[2] = min(box[2], width)
                    box[3] = min(box[3], height)
                    assert box[2]>box[0] and box[3]>box[1]

                    try:
                        self.logger.info("use crop v2")
                        ## 用空白填充其他部分
                        page = crop_v2(page, box)
                        offset_x = 0
                        offset_y = 0
                    except Exception as e:
                        self.logger.info("use crop v1")
                        page = page.crop(box)
                        offset_x = box[0]
                        offset_y = box[1]

                    yield self._prediction_from_pdf(
                                    image=page,
                                    page_idx_list=[page_idx],
                                    with_tta=with_tta,
                                    with_layout_parser=with_layout_parser,
                                    use_coref = use_coref,
                                    use_ocr=use_ocr,
                                    offset_x = offset_x,
                                    offset_y = offset_y,
                                    debug = debug,
                                    with_molscribe=with_molscribe,
                                    with_table=with_table,
                                    with_ocr=with_ocr,
                                    with_html=with_html,
                                    return_realative_coordinates = return_realative_coordinates,
                                    quick_prediction = quick_prediction,
                                    osd_detect = False,
                                    box = box,
                                    return_table_html = return_table_html
                                    )
                else:
                    temp_page_list = [page_idx]
                    result = self._prediction_from_pdf(
                                file_path = file_path,
                                page_idx_list=temp_page_list,
                                with_tta=with_tta,
                                with_layout_parser=with_layout_parser,
                                use_coref = use_coref,
                                use_ocr=use_ocr,
                                offset_x = offset_x,
                                offset_y = offset_y,
                                debug = debug,
                                with_molscribe=with_molscribe,
                                with_table=with_table,
                                with_ocr=with_ocr,
                                with_html=with_html,
                                return_realative_coordinates = return_realative_coordinates,
                                quick_prediction = quick_prediction,
                                osd_detect = osd_detect,
                                box = box,
                                return_table_html = return_table_html
                                )
                    

            else:
                for _ in range(0, len(page_idx_list), batch_size):
                    ## fixed bug
                    temp_page_list = page_idx_list[_: _+batch_size]
                    result = self._prediction_from_pdf(
                                file_path = file_path,
                                page_idx_list=temp_page_list,
                                with_tta=with_tta,
                                with_layout_parser=with_layout_parser,
                                use_coref = use_coref,
                                use_ocr=use_ocr,
                                offset_x = offset_x,
                                offset_y = offset_y,
                                debug = debug,
                                with_molscribe=with_molscribe,
                                with_table=with_table,
                                with_ocr=with_ocr,
                                with_html=with_html,
                                return_realative_coordinates = return_realative_coordinates,
                                quick_prediction = quick_prediction,
                                osd_detect = osd_detect,
                                box = box,
                                return_table_html = return_table_html
                                )
                    # if with_html is False and with_table is False:
                    #     for k,v in result.items():
                    #         yield {k:v}
                    # else:
                    #     yield result
                    self.logger.info(f"======return {temp_page_list}======")
                    if with_html:
                        ## 一批一批返回
                        if with_table:
                            yield result
                        else:
                            yield result
                    else:
                        ## 一页一页返回
                        if with_table:
                            mol_results, table_results = result
                            for page_idx in temp_page_list:
                                if page_idx in mol_results:
                                    mol_result = mol_results[page_idx]
                                else:
                                    mol_result = []
                                
                                if page_idx in table_results:
                                    table_result = table_results[page_idx]
                                else:
                                    table_result = []
                                
                                yield ({page_idx:mol_result},
                                    {page_idx:table_result})
                        else:
                            mol_results = result
                            for page_idx in temp_page_list:
                                if page_idx in mol_results:
                                    mol_result = mol_results[page_idx]
                                else:
                                    mol_result = []
                                
                                yield ({page_idx:mol_result}, {page_idx:[]})

        elif file_extension in [".bmp", ".png", ".jpg", ".jpeg", ".jpe", ".gif", ".tiff", ".tif", ".ico", ".webp", ".jp2", ".pbm", ".pgm",  ".ppm"]:
            page:Image = Image.open(file_path)
            page = page.convert("RGB")
            if osd_detect:
                config="--psm 0"
                temp_image_array = self.crop_white_fn(image=np.array(page), keypoints=[])["image"]
                temp_image = Image.fromarray(temp_image_array)
                width, height = temp_image.size
                orientation_results = pytesseract.image_to_osd(np.array(temp_image), config=config ,output_type=pytesseract.Output.DICT) #lang='chi_sim' 
                self.logger.info("======osd detect======")
                self.logger.info(f"orientation_results:{orientation_results}")
                orientation = orientation_results["orientation"] ## 变为逆时针
                orientation_confidence = orientation_results["orientation_conf"]
                ## https://indiantechwarrior.medium.com/optimizing-rotation-accuracy-for-ocr-fbfb785c504b
                if orientation_confidence>=2 and orientation in [90, 180, 270]: # 180 去除180度的结果
                    self.logger.info(f"oriention, {orientation_results}")
                    page: Image = rotate_bound(page, orientation)

            if box is not None:
                assert len(box) == 4
                width, height = page.size 
                box[0] = max(box[0], 0)
                box[1] = max(box[1], 0)
                box[2] = min(box[2], width)
                box[3] = min(box[3], height)
                assert box[2]>box[0] and box[3]>box[1]

                try:
                    self.logger.info("use crop v2")
                    page = crop_v2(page, box)
                    offset_x = 0
                    offset_y = 0
                except Exception as e:
                    self.logger.info("use crop v1")
                    page = page.crop(box)
                    offset_x = box[0]
                    offset_y = box[1]

            yield self._prediction_from_pdf(
                            image = page,
                            page_idx_list = page_idx_list,
                            with_tta = with_tta,
                            with_layout_parser = with_layout_parser,
                            use_coref = use_coref,
                            use_ocr = use_ocr,
                            offset_x = offset_x,
                            offset_y = offset_y,
                            debug = debug,
                            with_molscribe = with_molscribe,
                            with_table = with_table,
                            with_html = with_html,
                            return_realative_coordinates = return_realative_coordinates,
                            quick_prediction = quick_prediction,
                            osd_detect = osd_detect,
                            box = box,
                            return_table_html = return_table_html
                            )
            

        else:
            self.logger.error("the file_extension of file is invalid")
            raise Exception("the file_extension of file is invalid")
    
    def get_mol_detection(self, 
                        image_list, 
                        page_idx_list, 
                        use_coref=True, 
                        use_ocr=False, 
                        with_table=False, 
                        with_expand_mol=False, 
                        quick_prediction=False,
                        merged_offset_list = [],
                        start_offset_list = [],
                        extra_ori_image_list = [],
                        extra_ori_idx_list = [],):
        
        if len(merged_offset_list) == 0:
            merged_offset_list = [0] * len(image_list)
        
        if len(start_offset_list) == 0:
            start_offset_list = [0] * len(image_list)
        
        if len(extra_ori_image_list)>0:
            new_image_list = image_list + extra_ori_image_list
        else:
            new_image_list = image_list
        
        ## 预定义的全局预测
        global_result_dict_list = []

        ## 获取全局的预测
        global_predictions = self.moldetect_model.predict_images_V4(new_image_list, coref=use_coref, ocr=use_ocr, yolo_mol_model=self.yolo_mol_model)
        global_result_dict_list = [get_prediction_from_moldetect_V2(global_predictions[i]) for i in range(len(new_image_list))]
        global_result_dict_list_1 = global_result_dict_list[:len(global_result_dict_list)-len(extra_ori_image_list)]
        for i, result_dict_list in enumerate(global_result_dict_list_1):
            
            remove_box_ids = []
            for box_id, box_dict in enumerate(result_dict_list):
                mol_box = box_dict.get('mol_box', None)
                if mol_box is None:
                    remove_box_ids.append(box_id)
                else:
                    if start_offset_list[i]>0:
                        if mol_box[1] > start_offset_list[i]:
                            pass
                        else:
                            remove_box_ids.append(box_id)


            if len(remove_box_ids)>0:
                self.logger.info(f"remove {remove_box_ids} in page:{page_idx_list[i]}")
                global_result_dict_list_1[i] = [result_dict_list[_] for _ in range(len(result_dict_list)) if _ not in remove_box_ids]

        if len(extra_ori_image_list)>0:
            global_result_dict_list_2 = global_result_dict_list[len(global_result_dict_list)-len(extra_ori_image_list):]
            ## 合并结果
            ## 直接列表表达式进行操作
            for temp_i, i in enumerate(extra_ori_idx_list):
                if start_offset_list[i]>0:
                    result_dict_list = global_result_dict_list_2[temp_i]
                    height = image_list[i].height
                    ori_height =  extra_ori_image_list[temp_i].height
                    new_result_dict_list = []
                    for box_id, box_dict in enumerate(result_dict_list):
                        # ori_box_dict = copy.deepcopy(box_dict)
                        if "mol_box" in box_dict:
                            box_dict["mol_box"] = (
                                                    box_dict["mol_box"][0],
                                                    height - (ori_height - box_dict["mol_box"][1]),
                                                    box_dict["mol_box"][2],
                                                    height - (ori_height - box_dict["mol_box"][3]),
                                                   )
                            if "label_box_list" in box_dict:
                                for _ in range(len(box_dict["label_box_list"])):
                                    box_dict["label_box_list"][_] = (
                                                                        box_dict["label_box_list"][_][0],
                                                                        height - (ori_height - box_dict["label_box_list"][_][1]),
                                                                        box_dict["label_box_list"][_][2],
                                                                        height - (ori_height - box_dict["label_box_list"][_][3]),
                                                                        )
                            if "text_box_list" in box_dict:
                                for _ in range(len(box_dict["text_box_list"])):
                                    box_dict["text_box_list"][_] = (
                                                                        box_dict["text_box_list"][_][0],
                                                                        height - (ori_height - box_dict["text_box_list"][_][1]),
                                                                        box_dict["text_box_list"][_][2],
                                                                        height - (ori_height - box_dict["text_box_list"][_][3])
                                                                        )
                            
                            if "rgroup_box_list" in box_dict:
                                for _ in range(len(box_dict["rgroup_box_list"])):
                                    box_dict["rgroup_box_list"][_] = (
                                                                        box_dict["rgroup_box_list"][_][0],
                                                                        height - (ori_height - box_dict["rgroup_box_list"][_][1]),
                                                                        box_dict["rgroup_box_list"][_][2],
                                                                        height - (ori_height - box_dict["rgroup_box_list"][_][3])
                                                                        )
                            
                            if "iupac_box_list" in box_dict:
                                for _ in range(len(box_dict["iupac_box_list"])):
                                    box_dict["iupac_box_list"][_] = (
                                                                        box_dict["iupac_box_list"][_][0],
                                                                        height - (ori_height - box_dict["iupac_box_list"][_][1]),
                                                                        box_dict["iupac_box_list"][_][2],
                                                                        height - (ori_height - box_dict["iupac_box_list"][_][3])
                                                                        )
                            new_result_dict_list.append(box_dict)
                            
                    global_result_dict_list_1[i].extend(new_result_dict_list)
                else:
                    global_result_dict_list_1[i].extend(global_result_dict_list_2[temp_i])
                self.logger.info(f"add original prediction in page:{page_idx_list[i]}")
        
        global_result_dict_list = global_result_dict_list_1
        
        
        # self.filter_unreasonable_mol: remove
        if with_expand_mol is False:
            total_result_dict = OrderedDict({ page_idx_list[i]: self.filter_unreasonable_mol(image_list[i], merge_molecule_box(image_list[i], global_result_dict_list[i])) for i in range(len(image_list))})
        else:
            ## 先进行过滤
            total_result_dict = OrderedDict({ page_idx_list[i]: self.filter_unreasonable_mol(image_list[i], global_result_dict_list[i]) for i in range(len(image_list))})
            ## 再合并
            [self.expand_mol_fn(image_list[i], total_result_dict[page_idx_list[i]]) for i in range(len(image_list))]
            ## 多进程有点问题
            # if self.num_workers <= 1:
            #     [self.expand_mol_fn(image_list[i], total_result_dict[page_idx_list[i]]) for i in range(len(image_list))]
            # else:
            #     with mp.Pool(min(self.num_workers*2, len(page_idx_list))) as p:
            #         p.starmap(self.expand_mol_fn, zip(image_list, 
            #                                             [total_result_dict[page_idx_list[i]] for i in range(len(image_list))]
            #                                             ), chunksize=128)
        """
        total_result:List[Dict] = [{'mol_box': (117, 1067, 317, 1281), 'label_box': [(311, 1233, 342, 1265)]}]
        total_result_dict[page_idx] = [{'mol_box': (117, 1067, 317, 1281), 'label_box': [(311, 1233, 342, 1265)]}]
        """

        if quick_prediction and with_table is False:
            # self.logger.info("======start getting left top mol======")
            self.get_left_top_mol(total_result_dict)
            # self.logger.info("======finished getting left top mol======")
        
        return total_result_dict

    def get_image_list(self, image, file_path, page_idx_list, debug=False, osd_detect=False):
        if image is not None:
            self.logger.info(f"======prediction image with page_idx:{page_idx_list[0]}======")
            image_list = [image]
        else:
            if (file_path is None) or (os.path.exists(file_path) is False):
                self.logger.error("The path of `file_path` of pdf doesn't exist")
                raise Exception("The path of `file_path` of pdf doesn't exist")

            with open(file_path, 'rb') as pdf_file:
                pdf_reader = PyPDF2.PdfReader(pdf_file)
                num_pages = len(pdf_reader.pages)
                self.logger.info(f'The number of pages in PDF is {num_pages}')
                
            if page_idx_list is None:
                if debug is False:
                    self.logger.error("There is no page_idx in the input")
                    raise Exception("There is no page_idx in the input")
                else:
                    page_idx_list = list(range(1, num_pages+1))
            else:
                page_idx_list = [page_idx for page_idx in page_idx_list if page_idx>0 and page_idx<=num_pages]
            
            if len(page_idx_list) == 0:
                self.logger.error("======The length of `page_idx_list` is equal to zero======")
                raise Exception("======The length of `page_idx_list` is equal to zero======")

            self.logger.info(f"The length of `page_idx_list`:{len(page_idx_list)}")
            
            self.logger.info("======Prediction from pdf=======")
            self.logger.info("======Get page from pdf======")
            
            ## pytesseract 朝向识别对多进程不大友好
            ## 单进程
            image_list = [self.get_page_image_from_pdf(file_path, page_idx_list[i], osd_detect) for i in range(len(page_idx_list))]
        return image_list
    
    def single_page_table_detection(self, image):
        extracted_tables = []
        tables_layout = []

        # 将图像保存在io.BytesIO中
        image_io = io.BytesIO()
        image.save(image_io, format='PNG')
        image_io.seek(0)  # 这将让你可以从io.BytesIO对象的开始处读取数据

        ## 抽取表格
        img = document.Image(src=image_io)

        ## TODO 合并box
        try:
            extracted_tables = img.extract_tables()
            for temp_table in extracted_tables:
                setattr(temp_table, "proba", 1.0)
        except Exception as e:
            print(e)
        

        ## TODO 实线表和三线表的问题(表格检测的问题)
        if self.table_detector is not None:
            layout = self.table_detector.detect(image)
            tables_layout = [b for b in layout if b.type=="Table"]
        else:
            if self.yolo_table_model is not None:
                yolo_table_result = self.yolo_table_model.predict(
                    source=[image],  # Input image(s) as a list of PIL Image objects
                    imgsz=1024,  # Image size (height, width) in pixels
                    augment=True,  # Apply data augmentation (e.g., flip, rotate, etc.) to the input image
                    save=False  # Save the output image with bounding boxes
                )
                table_boxes = yolo_table_result[0].boxes.xyxy.detach().cpu().numpy()
                table_probs = yolo_table_result[0].boxes.conf.detach().cpu().numpy()
                for _ in range(len(table_boxes)):
                    temp_table_box = table_boxes[_]
                    temp_table_prob = table_probs[_]
                    ## 增加阈值
                    # if temp_table_prob>=0.3:
                    temp_block = TextBlock(block=Rectangle(x_1=temp_table_box[0], 
                                                            y_1=temp_table_box[1], 
                                                            x_2=temp_table_box[2], 
                                                            y_2=temp_table_box[3]),
                                            type="Table",
                                            score=temp_table_prob)
                    tables_layout.append(temp_block)

            if self.yolo_table_model_v2 is not None:
                yolo_table_result = self.yolo_table_model_v2.predict(
                    source=[image],  # Input image(s) as a list of PIL Image objects
                    imgsz=1024,  # Image size (height, width) in pixels
                    augment=False,  # Apply data augmentation (e.g., flip, rotate, etc.) to the input image
                    save=False  # Save the output image with bounding boxes
                )
                table_boxes = yolo_table_result[0].boxes.xyxy.detach().cpu().numpy()
                table_probs = yolo_table_result[0].boxes.conf.detach().cpu().numpy()
                for _ in range(len(table_boxes)):
                    temp_table_box = table_boxes[_]
                    temp_table_prob = table_probs[_]
                    # if temp_table_prob>=0.3:
                    temp_block = TextBlock(block=Rectangle(x_1=temp_table_box[0], 
                                                            y_1=temp_table_box[1], 
                                                            x_2=temp_table_box[2], 
                                                            y_2=temp_table_box[3]),
                                            type="Table",
                                            score=temp_table_prob)
                    tables_layout.append(temp_block)

        return extracted_tables, tables_layout
    
    def remove_duplicate_in_table_detection(self, extracted_tables, tables_layout):
        ## 去除重复的extracted_tables
        if len(extracted_tables)>1:
            # self.logger.info("remove repition border table in `extracted_tables`")
            # self.logger.info(f"len(extracted_tables):{len(extracted_tables)}")
            temp_extracted_tables = []
            for extracted_table_1 in extracted_tables:
                temp_box1 = (extracted_table_1.bbox.x1, extracted_table_1.bbox.y1, 
                            extracted_table_1.bbox.x2, extracted_table_1.bbox.y2)
                is_add = True
                for temp_i, extracted_table_2 in enumerate(temp_extracted_tables):
                    temp_box2 = (extracted_table_2.bbox.x1, extracted_table_2.bbox.y1, 
                                extracted_table_2.bbox.x2, extracted_table_2.bbox.y2)
                    is_add, _ = nms_without_confidence(temp_box1, temp_box2, threshold=0.8, use_union=False)

                    if is_add is False:
                        if (temp_box2[3]-temp_box2[1])*(temp_box2[2]-temp_box2[0])<(temp_box1[3]-temp_box1[1])*(temp_box1[2]-temp_box1[0]):
                            temp_extracted_tables[temp_i] = extracted_table_1
                        break
                
                if is_add:
                    temp_extracted_tables.append(extracted_table_1)
            
            extracted_tables = temp_extracted_tables
            # self.logger.info("after removing repition border table in `extracted_tables`")
            # self.logger.info(f"len(extracted_tables):{len(extracted_tables)}")
        
        ## NMS 去重
        if len(tables_layout)>1:
            temp_tables_layout = []
            for table_layout1 in tables_layout:
                temp_box1 = (table_layout1.block.x_1,
                            table_layout1.block.y_1,
                            table_layout1.block.x_2,
                            table_layout1.block.y_2)
                is_add = True
                for temp_i, table_layout2 in enumerate(temp_tables_layout):
                    temp_box2 = (table_layout2.block.x_1,
                                table_layout2.block.y_1,
                                table_layout2.block.x_2,
                                table_layout2.block.y_2)
                    is_add, _ = nms_without_confidence(temp_box1, temp_box2, threshold=0.65, use_union=True)

                    if is_add is False:
                        if table_layout1.score > table_layout2.score:
                            temp_tables_layout[temp_i] = table_layout1
                        break
                
                if is_add:
                    temp_tables_layout.append(table_layout1)
            
            tables_layout = temp_tables_layout

        ## remove border table in tables_layout
        ## NMS 去重, 有点问题
        if len(tables_layout)>=1:
            # self.logger.info("remove border table in `tables_layout`")
            # self.logger.info(f"len(tables_layout):{len(tables_layout)}")
            temp_tables_layout = []
            for table_layout in tables_layout:
                temp_box1 = (table_layout.block.x_1,
                            table_layout.block.y_1,
                            table_layout.block.x_2,
                            table_layout.block.y_2)
                is_add = True
                for extracted_table in extracted_tables:
                    temp_box2 = (extracted_table.bbox.x1, extracted_table.bbox.y1, extracted_table.bbox.x2, extracted_table.bbox.y2)
                    is_add, _ = nms_without_confidence(temp_box1, temp_box2, threshold=0.65, use_union=True)
                    if is_add is False:
                        print(table_layout)
                        print(extracted_table)
                        break
                if is_add:
                    temp_tables_layout.append(table_layout)
            tables_layout = temp_tables_layout
            # self.logger.info("after removint border table in `tables_layout`")
            # self.logger.info(f"len(tables_layout):{len(tables_layout)}")
        
        ## 去除包含的框
        if len(tables_layout)>1:
            tables_layout_box_list = []
            for temp_table_idx in range(len(tables_layout)):
                ## 把conf加入进来
                tables_layout_box_list.append(((tables_layout[temp_table_idx].block.x_1,
                                            tables_layout[temp_table_idx].block.y_1,
                                            tables_layout[temp_table_idx].block.x_2, 
                                            tables_layout[temp_table_idx].block.y_2,), tables_layout[temp_table_idx].score, temp_table_idx)) 
            
            sorted_tables_layout_box_list = sorted(tables_layout_box_list, key=lambda x: (x[0][2]-x[0][0])*(x[0][3]-x[0][1]))
            new_tables_layout_box_list = []
            for temp_idx, (layout_box, layout_score, layout_box_idx) in enumerate(sorted_tables_layout_box_list):
                x1, y1, x2, y2 = layout_box
                box1_area = (x2 - x1 + 1) * (y2 - y1 + 1)
                # 计算交集面积
                
                token = True
                for (label_box_2, layout_score_2, layout_box_2_idx, temp_2_token) in new_tables_layout_box_list:
                    x3, y3, x4, y4 = label_box_2
                    box2_area = (x4 - x3 + 1) * (y4 - y3 + 1)
                    left = max(x1, x3)
                    top = max(y1, y3)
                    right = min(x2, x4)
                    bottom = min(y2, y4)
                    
                    # 计算交集面积
                    intersection = max(0, right - left + 1) * max(0, bottom - top+1)

                    ## 交集>=0.8,并且概率更小
                    if intersection/min(box1_area, box2_area)>=0.8:
                        if layout_score_2 > layout_score:
                            token = False
                            break
                new_tables_layout_box_list.append((layout_box, layout_score, layout_box_idx, token))

            temp_tables_layout = []
            for (label_box_2, layout_score_2, layout_box_2_idx, temp_2_token) in new_tables_layout_box_list:
                if temp_2_token is True:
                    temp_tables_layout.append(tables_layout[layout_box_2_idx])
            tables_layout = temp_tables_layout
        
        self.logger.info(f"======= extract {len(extracted_tables)} border table =======")
    
    
    
    def _prediction_from_pdf(self,
                            image:Image=None,
                            file_path:str=None,
                            page_idx_list:List[int]=[0],
                            with_tta:bool=False,
                            with_layout_parser:bool=False,
                            use_coref:bool = True,
                            use_ocr:bool=False,
                            offset_x:int = 0,
                            offset_y:int=0,
                            debug:bool = False,
                            with_molscribe:bool=True,
                            with_table:bool=False,
                            with_ocr:bool=False,
                            with_html:bool=False,
                            with_expand_mol:bool=False,
                            return_realative_coordinates:bool=True,
                            quick_prediction:bool=False,
                            mode:str="auto",
                            osd_detect:bool=False,
                            box:list=[],## 仅仅在quick_prediction场景下有用,
                            return_table_html:bool=False
                            ):
        
        add_prefix = False
        if file_path == self.prepage["file_name"]:
            if self.prepage["page_idx"] + 1 in page_idx_list:
                add_prefix = True
        self.logger.info(f"======add_prefix:{add_prefix}======")

        self.logger.info(f"======with_table:{with_table}======")

        all_start = time.time()
        ##如果传入的是图片
        if image is not None:
            self.logger.info(f"======prediction image with page_idx:{page_idx_list[0]}======")
            image_list = [image]
            merged_image_list = image_list
            extra_ori_image_list = []
            extra_ori_idx_list = []
            merged_offset_list = [0] * len(image_list)
            start_offset_list = [0] * len(image_list)
        else:
            if (file_path is None) or (os.path.exists(file_path) is False):
                self.logger.error("The path of `file_path` of pdf doesn't exist")
                raise Exception("The path of `file_path` of pdf doesn't exist")

            with open(file_path, 'rb') as pdf_file:
                pdf_reader = PyPDF2.PdfReader(pdf_file)
                num_pages = len(pdf_reader.pages)
                self.logger.info(f'The number of pages in PDF is {num_pages}')
                
            if page_idx_list is None:
                if debug is False:
                    self.logger.error("There is no page_idx in the input")
                    raise Exception("There is no page_idx in the input")
                else:
                    page_idx_list = list(range(1, num_pages+1))
            else:
                page_idx_list = [page_idx for page_idx in page_idx_list if page_idx>0 and page_idx<=num_pages]
            
            if len(page_idx_list) == 0:
                self.logger.error("======The length of `page_idx_list` is equal to zero======")
                raise Exception("======The length of `page_idx_list` is equal to zero======")

            self.logger.info(f"The length of `page_idx_list`:{len(page_idx_list)}")
            
            self.logger.info("======Prediction from pdf=======")
            self.logger.info("======Get page from pdf======")
            
            ## pytesseract 朝向识别对多进程不大友好
            ## 单进程
            image_list = [self.get_page_image_from_pdf(file_path, page_idx_list[i], osd_detect) for i in range(len(page_idx_list))]
            merged_image_list = []
            merged_offset_list = []
            start_offset_list = []
            extra_ori_image_list = []
            extra_ori_idx_list = []
            for i in range(len(page_idx_list)):
                ori_image = image_list[i]
                if quick_prediction is False: # 
                    ori_image_result = self.yolo_mol_model.predict(
                        source=[ori_image],  # Input image(s) as a list of PIL Image objects
                        imgsz=800,  # Image size (height, width) in pixels
                        augment=False,  # Apply data augmentation (e.g., flip, rotate, etc.) to the input image
                        save=False,  # Save the output image with bounding boxes
                        conf=0.3, ## TODO
                    )

                    ## 增加判断条件
                    bbox = ori_image_result[0].boxes.xyxy
                    bbox_cls = ori_image_result[0].boxes.cls
                    bbox_conf = ori_image_result[0].boxes.conf
                    if (bbox_cls==0).sum()>0:
                        mol_bboxes = bbox[bbox_cls==0]
                        
                        add_prefix_image = False
                        if (bbox_cls!=0).sum()==0:
                            add_prefix_image = True
                        else:
                            other_bboxes = bbox[bbox_cls!=0]
                            top_mol_bbox = mol_bboxes[torch.argmin(mol_bboxes[:, 1]+mol_bboxes[:, 3])]
                            top_other_bbox = other_bboxes[torch.argmin(other_bboxes[:, 1]+other_bboxes[:, 3])]
                            if top_mol_bbox[1]+top_mol_bbox[3]<top_other_bbox[1]+top_other_bbox[3]:
                                add_prefix_image = True
                            else:
                                add_prefix_image = False

                        if add_prefix_image:
                            if i == 0:
                                if add_prefix:
                                    pre_image = self.prepage["image"]
                                
                                    merged_page, merged_offset_y, start_offset = merge_page_fn(pre_image, ori_image)
                                    self.logger.info(f"merged page in {page_idx_list[i]-1, page_idx_list[i]} and offset:{merged_offset_y}")
                                    merged_image_list.append(merged_page)
                                    merged_offset_list.append(merged_offset_y)
                                    start_offset_list.append(start_offset)

                                    extra_ori_image_list.append(ori_image)
                                    extra_ori_idx_list.append(i)

                                else:
                                    merged_image_list.append(ori_image)
                                    merged_offset_list.append(0)
                                    start_offset_list.append(0)

                            else:
                                if page_idx_list[i-1] in page_idx_list:
                                    merged_page, merged_offset_y, start_offset = merge_page_fn(pre_image, ori_image)
                                    self.logger.info(f"merged page in {page_idx_list[i]-1, page_idx_list[i]} and offset:{merged_offset_y}")
                                    merged_image_list.append(merged_page)
                                    merged_offset_list.append(merged_offset_y)
                                    start_offset_list.append(start_offset)

                                    extra_ori_image_list.append(ori_image)
                                    extra_ori_idx_list.append(i)
                        else:
                            merged_image_list.append(ori_image)
                            merged_offset_list.append(0)
                            start_offset_list.append(0)
                        
                    else:
                        merged_image_list.append(ori_image)
                        merged_offset_list.append(0)
                        start_offset_list.append(0)
                    
                    pre_image = ori_image

                else:
                    merged_image_list.append(ori_image)
                    merged_offset_list.append(0)
                    start_offset_list.append(0)

            ## TODO has some problems
            # if self.num_workers <= 1:
            #     image_list = [self.get_page_image_from_pdf(file_path, page_idx_list[i]) for i in range(len(page_idx_list))]
            # else:
            #     with mp.Pool(min(self.num_workers, max(len(page_idx_list), 1))) as p:
            #         image_list = p.starmap(self.get_page_image_from_pdf, zip([file_path]*len(page_idx_list), page_idx_list), chunksize=128)
        
        # self.logger.info("======Get mode list======")
        # too slow
        # if mode == "auto":
        #     mode_list = [self.get_mode(image_list[i]) for i in range(len(image_list))]
        # else:
        #     mode_list = [mode] * len(image_list)
        mode_list = ["auto"] * len(image_list)

        self.logger.info("======Get detection prediction======")
        start = time.time()
        total_result_dict = self.get_mol_detection(merged_image_list, 
                                                page_idx_list, 
                                                use_coref = use_coref, 
                                                use_ocr = use_ocr, 
                                                with_table = with_table, 
                                                with_expand_mol = with_expand_mol, 
                                                quick_prediction = quick_prediction,
                                                merged_offset_list = merged_offset_list,
                                                start_offset_list = start_offset_list,
                                                extra_ori_image_list = extra_ori_image_list,
                                                extra_ori_idx_list = extra_ori_idx_list,
                                                )
        self.logger.info(f"moldetect consumed:{time.time()-start:.3f}")
        self.logger.info("=========================")


        self.logger.info("======get ocr result======")
        start = time.time()
        ## 目前没必要改成多进程
        ## 修改

        block_image_list_list = [self.get_mol_image_and_with_label_ocr(merged_image_list[i], 
                                                                        total_result_dict[page_idx_list[i]], 
                                                                        with_molscribe,
                                                                        mode_list[i],
                                                                        start_offset_list[i],
                                                                        with_ocr=with_ocr) 
                                                                        for i in range(len(start_offset_list))]

        ## 去除
        for i, (page_idx_list[i], total_result) in enumerate(total_result_dict.items()):
            if start_offset_list[i] > 0:
                remove_box_ids = []
                for box_id, box_dict in enumerate(total_result):
                    mol_box = box_dict.get('mol_box', None)
                    if mol_box is not None:
                        ## 中心位置>start_offset_list[i]
                        if (mol_box[1]+mol_box[3])/2 > start_offset_list[i]:
                            box_dict["mol_box"] = (
                                box_dict["mol_box"][0], 
                                box_dict["mol_box"][1] - merged_offset_list[i], 
                                box_dict["mol_box"][2], 
                                box_dict["mol_box"][3] - merged_offset_list[i],
                            )

                            ## 新增变量是否跨ye
                            if "label_box_list" in box_dict:
                                box_dict["label_box_page_list"] = []
                                for label_id in range(len(box_dict["label_box_list"])):
                                    if box_dict["label_box_list"][label_id][3] <= start_offset_list[i]:
                                        box_dict["label_box_page_list"].append(page_idx_list[i]-1)
                                    else:
                                        box_dict["label_box_page_list"].append(page_idx_list[i])

                                    box_dict["label_box_list"][label_id] = (
                                        box_dict["label_box_list"][label_id][0],
                                        box_dict["label_box_list"][label_id][1] - merged_offset_list[i],
                                        box_dict["label_box_list"][label_id][2],
                                        box_dict["label_box_list"][label_id][3] - merged_offset_list[i],
                                    )
                            if "text_box_list" in box_dict:
                                box_dict["text_box_page_list"] = []
                                for text_id in range(len(box_dict["text_box_list"])):
                                    if box_dict["text_box_list"][text_id][3] <= start_offset_list[i]:
                                        box_dict["text_box_page_list"].append(page_idx_list[i]-1)
                                    else:
                                        box_dict["text_box_page_list"].append(page_idx_list[i])

                                    box_dict["text_box_list"][text_id] = (
                                        box_dict["text_box_list"][text_id][0],
                                        box_dict["text_box_list"][text_id][1] - merged_offset_list[i],
                                        box_dict["text_box_list"][text_id][2],
                                        box_dict["text_box_list"][text_id][3] - merged_offset_list[i],
                                    )

                            if "rgroup_box_list" in box_dict:
                                box_dict["rgroup_box_page_list"] = []
                                for rgroup_id in range(len(box_dict["rgroup_box_list"])):
                                    if box_dict["rgroup_box_list"][rgroup_id][3] <= start_offset_list[i]:
                                        box_dict["rgroup_box_page_list"].append(page_idx_list[i]-1)
                                    else:
                                        box_dict["rgroup_box_page_list"].append(page_idx_list[i])

                                    box_dict["rgroup_box_list"][rgroup_id] = (
                                        box_dict["rgroup_box_list"][rgroup_id][0],
                                        box_dict["rgroup_box_list"][rgroup_id][1] - merged_offset_list[i],
                                        box_dict["rgroup_box_list"][rgroup_id][2],
                                        box_dict["rgroup_box_list"][rgroup_id][3] - merged_offset_list[i],
                                    )
                            
                            if "iupac_box_list" in box_dict:
                                box_dict["iupac_box_page_list"] = []
                                for iupac_id in range(len(box_dict["iupac_box_list"])):
                                    if box_dict["iupac_box_list"][iupac_id][3] <= start_offset_list[i]:
                                        box_dict["iupac_box_page_list"].append(page_idx_list[i]-1)
                                    else:
                                        box_dict["iupac_box_page_list"].append(page_idx_list[i])

                                    box_dict["iupac_box_list"][iupac_id] = (
                                        box_dict["iupac_box_list"][iupac_id][0],
                                        box_dict["iupac_box_list"][iupac_id][1] - merged_offset_list[i],
                                        box_dict["iupac_box_list"][iupac_id][2],
                                        box_dict["iupac_box_list"][iupac_id][3] - merged_offset_list[i],
                                    )
                        else:
                            remove_box_ids.append(box_id)
                    else:
                        pass
                if len(remove_box_ids)>0:
                    self.logger.info(f"remove {remove_box_ids} in page:{page_idx_list[i]}")
                    total_result_dict[page_idx_list[i]] = [total_result[_] for _ in range(len(total_result)) if _ not in remove_box_ids]



        ## 腐蚀操作，待评测
        # kernel = np.ones((3, 3), dtype=np.uint8)
        # block_image_list = [cv2.erode(element, kernel, iterations=1) for sublist in block_image_list_list for element in sublist]
        # block_image_list = [cv2.medianBlur(element, 3) for sublist in block_image_list_list for element in sublist]
        block_image_list = [element for sublist in block_image_list_list for element in sublist]
        self.logger.info(f"ocr consumed:{time.time()-start:.3f}")
        self.logger.info("=========================")
        # self.logger.info("======finnished ocr result======")

        if with_molscribe:
            if len(block_image_list)>0:
                self.logger.info("========img2mol========")
                self.logger.info(f"========extract {len(block_image_list)} mol========")

                ## 快速预测模式
                if quick_prediction:
                    result_df = run_task({"image_list":block_image_list, "model_dir":self.model_dir,
                                        "weight_ensemble":False, "update_pad":False}) #"ocr":self.easy_ocrer,
                else:
                    result_df = run_task({"image_list":block_image_list, "model_dir":self.model_dir,
                                        "weight_ensemble":False, "update_pad":False}) #"ocr":self.easy_ocrer,
                
                j = 0
                for i, (page_idx, total_result) in enumerate(total_result_dict.items()):
                    image = image_list[i]
                    for block_idx, box_dict in enumerate(total_result):
                        mol_box = box_dict.get('mol_box', None)
                        if mol_box is not None:

                            ## 以temp_mol2为标准
                            # temp_mol_1 = Chem.MolFromMolBlock(result_df.loc[j, "post_molblock"])
                            try:
                                temp_mol_1 = assign_right_bond_stero_to_molblock(result_df.loc[j, "post_molblock"])
                            except Exception as e:
                                print(e)
                            if False:
                                try:
                                    temp_mol_1_copy = copy.deepcopy(temp_mol_1)
                                    Chem.Kekulize(temp_mol_1_copy)
                                except:
                                    temp_mol_1_copy = None
                            else:
                                temp_mol_1_copy = None
                            

                            # temp_mol_2 = Chem.MolFromMolBlock(result_df.loc[j, "molblock"])
                            temp_mol_2 = assign_right_bond_stero_to_molblock(result_df.loc[j, "molblock"])

                            if False:
                                try:
                                    temp_mol_2_copy = copy.deepcopy(temp_mol_2)
                                    Chem.Kekulize(temp_mol_2_copy)
                                except:
                                    temp_mol_2_copy = None
                            else:
                                temp_mol_2_copy = None

                            
                            if temp_mol_2 is not None:
                                if temp_mol_2_copy is not None:
                                    box_dict["post_molblock"] = result_df.loc[j, "molblock"]
                                    box_dict["post_SMILES"] = result_df.loc[j, "graph_SMILES"]
                                else:
                                    if temp_mol_1_copy is not None:
                                        box_dict["post_SMILES"] = result_df.loc[j, "post_SMILES"]
                                        box_dict["post_molblock"] = result_df.loc[j, "post_molblock"]
                                    else:
                                        ## 如果全为None，则按照原来返回
                                        box_dict["post_molblock"] = result_df.loc[j, "molblock"]
                                        box_dict["post_SMILES"] = result_df.loc[j, "graph_SMILES"]
                                    
                            else:
                                if temp_mol_1 is not None:
                                    box_dict["post_SMILES"] = result_df.loc[j, "post_SMILES"]
                                    box_dict["post_molblock"] = result_df.loc[j, "post_molblock"]
                                else:
                                    box_dict["post_molblock"] = result_df.loc[j, "molblock"]
                                    box_dict["post_SMILES"] = result_df.loc[j, "graph_SMILES"]

                            try:
                                box_dict["Cano_SMILES"] = Chem.MolToSmiles(Chem.MolFromSmiles(box_dict["post_SMILES"]))
                            except Exception as e:
                                self.logger.info(f'{box_dict["post_SMILES"]} can\'t be canoicalized')
                                box_dict["Cano_SMILES"] = box_dict["post_SMILES"]
                            
                            verified_mol = Chem.MolFromMolBlock(box_dict["post_molblock"])
                            if verified_mol is None:
                                box_dict["state"] = "failure"
                            else:
                                box_dict["state"] = "success"
                            
                            j = j + 1
                
                ## 新增过滤
                for i, (page_idx, total_result) in enumerate(total_result_dict.items()):
                    new_new_total_result = []
                    count = 0
                    for block_idx, box_dict in enumerate(total_result):
                        post_SMILES = box_dict["Cano_SMILES"]
                        ## 12C
                        ## 过滤掉特别复杂的分子
                        if (post_SMILES.count("%"))>=10 or \
                        ("CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC" in post_SMILES) or\
                        (post_SMILES in ["[CH2-][CH2-]", "[CH2+][CH2+]", "[O-][O-]", "[CH2+]", "[H]", "[CH]C", "[CH]O", "*", "[CH]1CCO1", "[O-]", "C12[CH]34C5C13O245", "[CH]1C2[CH]C1[CH]2", "[W]"]):
                            self.logger.info(f"filter post_SMILES:{post_SMILES}")
                            count += 1
                        else:
                            new_new_total_result.append(box_dict)
                    if count > 0:
                        self.logger.info(f"filter {count} mol in page:{page_idx}")
                        self.logger.info(f"previous length: {len(total_result)}, post length:{len(new_new_total_result)}")
                        total_result_dict[page_idx] = new_new_total_result
                
                self.logger.info(f"img2mol consumed:{time.time()-start:.3f}")
                self.logger.info("=========================")
                # self.logger.info("======finished img2mol======")
        
        ## double check
        for i in range(len(page_idx_list)):
            page_idx = page_idx_list[i]
            total_result = total_result_dict.get(page_idx)
            for block_idx, box_dict in enumerate(total_result):
                box_dict["assigned_idx"] = f"{page_idx}_{block_idx}"
        
        total_table_result_dict = {}
        if with_table:
            self.logger.info("======start img2table=====")
            start = time.time()
            for i in range(len(page_idx_list)):
                page_idx = page_idx_list[i]
                image = image_list[i]

                table_result = []
                temp_mode = mode_list[i]
                tables_layout = []
                extracted_tables = []
                
                total_result = total_result_dict.get(page_idx)

                if quick_prediction is False:

                    if True:
                        # 将图像保存在io.BytesIO中
                        image_io = io.BytesIO()
                        image.save(image_io, format='PNG')
                        image_io.seek(0)  # 这将让你可以从io.BytesIO对象的开始处读取数据

                        ## 抽取表格
                        img = document.Image(src=image_io)

                        ## TODO 合并box
                        try:
                            extracted_tables = img.extract_tables()
                            for temp_table in extracted_tables:
                                setattr(temp_table, "proba", 1.0)
                        except Exception as e:
                            print(e)
                    
                    ## 初始化表格检测模型
                    ## 检查模型
                    if self.with_table_detect:
                        if self.use_yolo_table_model:
                            if self.yolo_table_model is None:
                                self.yolo_table_model = self.get_yolo_table_model(device=self.device)
                                self.logger.info("======init `yolo_table_model` model from local")
                        else:
                            if self.table_detector is None:
                                self.table_detector = self.get_table_detector(device=self.device)
                                self.logger.info("======init `table_detector` model from local")
                        
                        if self.use_yolo_table_model_v2:
                            if self.yolo_table_model_v2 is None:
                                self.yolo_table_model_v2 = self.get_yolo_table_model(os.path.join(self.model_dir, "checkpoints", "yolo_table/yolo_table_best_1000k.pt"), 
                                                                                device=self.device)
                                self.logger.info("======init `yolo_table_model_v2` model from local")

                    ## TODO 实线表和三线表的问题
                    if self.table_detector is not None:
                        layout = self.table_detector.detect(image)
                        tables_layout = [b for b in layout if b.type=="Table"]
                    else:
                        if self.yolo_table_model is not None:
                            yolo_table_result = self.yolo_table_model.predict(
                                source=[image],  # Input image(s) as a list of PIL Image objects
                                imgsz=1024,  # Image size (height, width) in pixels
                                augment=True,  # Apply data augmentation (e.g., flip, rotate, etc.) to the input image
                                save=False,  # Save the output image with bounding boxes
                                conf=0.4,
                            )
                            table_boxes = yolo_table_result[0].boxes.xyxy.detach().cpu().numpy()
                            table_probs = yolo_table_result[0].boxes.conf.detach().cpu().numpy()
                            for _ in range(len(table_boxes)):
                                temp_table_box = table_boxes[_]
                                temp_table_prob = table_probs[_]
                                ## 增加阈值
                                if temp_table_prob>=0.3:
                                    temp_block = TextBlock(block=Rectangle(x_1=temp_table_box[0], 
                                                                            y_1=temp_table_box[1], 
                                                                            x_2=temp_table_box[2], 
                                                                            y_2=temp_table_box[3]),
                                                            type="Table",
                                                            score=temp_table_prob)
                                    tables_layout.append(temp_block)
                        
                        if self.yolo_table_model_v2 is not None:
                            yolo_table_result = self.yolo_table_model_v2.predict(
                                source=[image],  # Input image(s) as a list of PIL Image objects
                                imgsz=1024,  # Image size (height, width) in pixels
                                augment=False,  # Apply data augmentation (e.g., flip, rotate, etc.) to the input image
                                save=False  # Save the output image with bounding boxes
                            )
                            table_boxes = yolo_table_result[0].boxes.xyxy.detach().cpu().numpy()
                            table_probs = yolo_table_result[0].boxes.conf.detach().cpu().numpy()
                            for _ in range(len(table_boxes)):
                                temp_table_box = table_boxes[_]
                                temp_table_prob = table_probs[_]
                                if temp_table_prob>=0.3:
                                    temp_block = TextBlock(block=Rectangle(x_1=temp_table_box[0], 
                                                                            y_1=temp_table_box[1], 
                                                                            x_2=temp_table_box[2], 
                                                                            y_2=temp_table_box[3]),
                                                            type="Table",
                                                            score=temp_table_prob)
                                    tables_layout.append(temp_block)
                        
                ## 不走检测路线
                else:
                    if True:
                        # 将图像保存在io.BytesIO中
                        image_io = io.BytesIO()
                        image.save(image_io, format='PNG')
                        image_io.seek(0)  # 这将让你可以从io.BytesIO对象的开始处读取数据

                        ## 抽取表格
                        img = document.Image(src=image_io)
                        ## TODO 合并box
                        try:
                            extracted_tables = img.extract_tables()
                        except Exception as e:
                            print(e)
                    
                    temp_block = TextBlock(block=Rectangle(x_1=box[0], 
                                                            y_1=box[1], 
                                                            x_2=box[2], 
                                                            y_2=box[3]),
                                                        type="Table",
                                                        score=1.0)
                    tables_layout.append(temp_block)

                
                ## 去除重复的extracted_tables
                if len(extracted_tables)>1:
                    # self.logger.info("remove repition border table in `extracted_tables`")
                    # self.logger.info(f"len(extracted_tables):{len(extracted_tables)}")
                    temp_extracted_tables = []
                    for extracted_table_1 in extracted_tables:
                        temp_box1 = (extracted_table_1.bbox.x1, extracted_table_1.bbox.y1, 
                                    extracted_table_1.bbox.x2, extracted_table_1.bbox.y2)
                        is_add = True
                        for temp_i, extracted_table_2 in enumerate(temp_extracted_tables):
                            temp_box2 = (extracted_table_2.bbox.x1, extracted_table_2.bbox.y1, 
                                        extracted_table_2.bbox.x2, extracted_table_2.bbox.y2)
                            is_add, _ = nms_without_confidence(temp_box1, temp_box2, threshold=0.8, use_union=False)

                            if is_add is False:
                                if (temp_box2[3]-temp_box2[1])*(temp_box2[2]-temp_box2[0])<(temp_box1[3]-temp_box1[1])*(temp_box1[2]-temp_box1[0]):
                                    temp_extracted_tables[temp_i] = extracted_table_1
                                break
                        
                        if is_add:
                            temp_extracted_tables.append(extracted_table_1)
                    
                    extracted_tables = temp_extracted_tables
                    # self.logger.info("after removing repition border table in `extracted_tables`")
                    # self.logger.info(f"len(extracted_tables):{len(extracted_tables)}")
                
                ## NMS 去重
                if len(tables_layout)>1:
                    temp_tables_layout = []
                    for table_layout1 in tables_layout:
                        temp_box1 = (table_layout1.block.x_1,
                                    table_layout1.block.y_1,
                                    table_layout1.block.x_2,
                                    table_layout1.block.y_2)
                        is_add = True
                        for temp_i, table_layout2 in enumerate(temp_tables_layout):
                            temp_box2 = (table_layout2.block.x_1,
                                        table_layout2.block.y_1,
                                        table_layout2.block.x_2,
                                        table_layout2.block.y_2)
                            is_add, _ = nms_without_confidence(temp_box1, temp_box2, threshold=0.65, use_union=True)

                            if is_add is False:
                                if table_layout1.score > table_layout2.score:
                                    temp_tables_layout[temp_i] = table_layout1
                                break
                        
                        if is_add:
                            temp_tables_layout.append(table_layout1)
                    
                    tables_layout = temp_tables_layout

                ## remove border table in tables_layout
                ## NMS 去重, 有点问题
                if len(tables_layout)>=1:
                    # self.logger.info("remove border table in `tables_layout`")
                    # self.logger.info(f"len(tables_layout):{len(tables_layout)}")
                    temp_tables_layout = []
                    for table_layout in tables_layout:
                        temp_box1 = (table_layout.block.x_1,
                                    table_layout.block.y_1,
                                    table_layout.block.x_2,
                                    table_layout.block.y_2)
                        is_add = True
                        for extracted_table in extracted_tables:
                            temp_box2 = (extracted_table.bbox.x1, extracted_table.bbox.y1, extracted_table.bbox.x2, extracted_table.bbox.y2)
                            is_add, _ = nms_without_confidence(temp_box1, temp_box2, threshold=0.65, use_union=True)
                            if is_add is False:
                                print(table_layout)
                                print(extracted_table)
                                break
                        if is_add:
                            temp_tables_layout.append(table_layout)
                    tables_layout = temp_tables_layout
                    # self.logger.info("after removint border table in `tables_layout`")
                    # self.logger.info(f"len(tables_layout):{len(tables_layout)}")
                
                ## 去除包含的框
                if len(tables_layout)>1:
                    tables_layout_box_list = []
                    for temp_table_idx in range(len(tables_layout)):
                        ## 把conf加入进来
                        tables_layout_box_list.append(((tables_layout[temp_table_idx].block.x_1,
                                                    tables_layout[temp_table_idx].block.y_1,
                                                    tables_layout[temp_table_idx].block.x_2, 
                                                    tables_layout[temp_table_idx].block.y_2,), tables_layout[temp_table_idx].score, temp_table_idx)) 
                    
                    sorted_tables_layout_box_list = sorted(tables_layout_box_list, key=lambda x: (x[0][2]-x[0][0])*(x[0][3]-x[0][1]))
                    new_tables_layout_box_list = []
                    for temp_idx, (layout_box, layout_score, layout_box_idx) in enumerate(sorted_tables_layout_box_list):
                        x1, y1, x2, y2 = layout_box
                        box1_area = (x2 - x1 + 1) * (y2 - y1 + 1)
                        # 计算交集面积
                        
                        token = True
                        for (label_box_2, layout_score_2, layout_box_2_idx, temp_2_token) in new_tables_layout_box_list:
                            x3, y3, x4, y4 = label_box_2
                            box2_area = (x4 - x3 + 1) * (y4 - y3 + 1)
                            left = max(x1, x3)
                            top = max(y1, y3)
                            right = min(x2, x4)
                            bottom = min(y2, y4)
                            
                            # 计算交集面积
                            intersection = max(0, right - left + 1) * max(0, bottom - top+1)

                            ## 交集>=0.8,并且概率更小
                            if intersection/min(box1_area, box2_area)>=0.8:
                                if layout_score_2 > layout_score:
                                    token = False
                                    break
                        new_tables_layout_box_list.append((layout_box, layout_score, layout_box_idx, token))

                    temp_tables_layout = []
                    for (label_box_2, layout_score_2, layout_box_2_idx, temp_2_token) in new_tables_layout_box_list:
                        if temp_2_token is True:
                            temp_tables_layout.append(tables_layout[layout_box_2_idx])
                    tables_layout = temp_tables_layout
                
                self.logger.info(f"======= extract {len(extracted_tables)} border table =======")
                # table_idx = 0
                for table in extracted_tables:
                    table = refine_table(table, image)
                    setattr(table, "type", "border_table")
                    try:
                        self.table_with_ocr(image, table, total_result, temp_mode=temp_mode)
                        table_result.append(table)
                    except Exception as e:
                        print(e)
                        pass
                self.logger.info("=======finished extract border table =======")

                # table_image_list = []
                self.logger.info(f"======= extract {len(tables_layout)} borderless table =======")
                for temp_table_idx in range(len(tables_layout)):
                    table_layout = tables_layout[temp_table_idx]
                    ## 5 pad
                    table_box = (
                                max(table_layout.block.x_1 - 12, 0),
                                max(table_layout.block.y_1 - 5, 0),
                                min(table_layout.block.x_2 + 12, image.width),
                                min(table_layout.block.y_2 + 5, image.height),
                                )
                    table_image = image.crop(table_box)
                    # table_image_array = cv2.cvtColor(np.array(table_image), cv2.COLOR_RGB2BGR)
                    # table_image_array_with_white = self.crop_white_fn_4_table(image=table_image_array, keypoints=[])["image"]
                    # table_image_list.append(table_image_array)
                    table_config = {
                        "image_list":[table_image],
                        "model_dir":os.path.join(self.model_dir, "checkpoints"),
                        "box_list":[table_box],
                        "return_table_html":return_table_html
                    }
                    ## 默认保留第1个
                    table = table_infer(table_config)
                    if return_table_html is False:
                        if table is not None:
                            setattr(table, "type", "borderless_table")
                            setattr(table, "proba", table_layout.score)
                            self.table_with_ocr(image, table, total_result, temp_mode=temp_mode)
                            table_result.append(table)
                    else:
                        new_table_html = self.table_html_with_ocr(table, image)
                        
                self.logger.info(f"=======finished extract {len(table_result)} borderless table =======")
                total_table_result_dict[page_idx] = table_result

                if len(total_table_result_dict[page_idx])>1:
                    ## 先从上到下，再从左到右
                    width_list = []
                    width_center_list = []
                    height_list = []
                    height_center_list = []
                    for x in total_table_result_dict[page_idx]:
                        width_list.append(x.bbox.x2 - x.bbox.x1)
                        height_list.append(x.bbox.y2 - x.bbox.y1)
                        width_center_list.append((x.bbox.x2))
                        height_center_list.append((x.bbox.y1))
                    width_tolerant = 30 #int(np.mean(width_center_list)//7*5.5)
                    min_width_center = np.min(width_center_list)
                    height_tolerant = 30 #int(np.mean(height_center_list)//7*5.5)
                    min_height_center = np.min(height_center_list)
                    total_table_result_dict[page_idx] = [temp for temp in sorted(total_table_result_dict[page_idx], key=lambda x: (
                                                                                                        ## 原来是左y方向的量化误差的
                                                                                                        get_contour_precedence_V2((x.bbox.y1, x.bbox.x1, x.bbox.y2, x.bbox.x2), width_tolerant, min_width_center),
                                                                                                        get_contour_precedence_V2((x.bbox.x1, x.bbox.y1, x.bbox.x2, x.bbox.y2), height_tolerant, min_height_center), ##量化误差为10
                                                                                                        ))]

            self.logger.info(f"img2table consumed:{time.time()-start:.3f}")
            self.logger.info("=========================")
            # self.logger.info("======finised img2table=====")
        
        mol_html = ""
        table_html = ""
        mol_csv = pd.DataFrame()

        ## sort by up to down
        # total_result_dict = OrderedDict({page_idx:[temp for temp in sorted(total_result, key=lambda x: get_contour_precedence(x['mol_box'], image_list[_].width))] for _, (page_idx, total_result) in enumerate(total_result_dict.items())})
        new_total_result_dict = OrderedDict({})
        for _, (page_idx, total_result) in enumerate(total_result_dict.items()):
            if len(total_result)>0:
                heights_list = []
                height_center_list = []
                for x in total_result:
                    heights_list.append(x["mol_box"][3] - x["mol_box"][1])
                    height_center_list.append((x["mol_box"][3] + x["mol_box"][1])//2)
                tolerant = int(np.mean(heights_list)//7*5.5)
                min_height_center = np.min(height_center_list)
                ## 先从左到右， 再从上到下
                new_total_result_dict[page_idx] = [temp for temp in sorted(total_result, key=lambda x: (
                                                                                                        get_contour_precedence_V2(x['mol_box'], tolerant, min_height_center),
                                                                                                        (x['mol_box'][0]+x['mol_box'][2])//2,
                                                                                                        ))]

                ## 先按照高度从小到大及
                # new_total_result_dict[page_idx] = [temp for temp in sorted(total_result, key=lambda x: ((x['mol_box'][3]-x['mol_box'][1]),
                #                                                                                         ))]
                # temp_block_idx_list_list = []
                # for idx, box_dict in enumerate(new_total_result_dict[page_idx]):
                #     if_add = True
                #     min_dist_list = []
                #     box1 = box_dict["mol_box"]
                #     for temp_block_idx_list in temp_block_idx_list_list:
                #         temp_min_list = []
                #         ## 基本逻辑是在y方向上都有交集
                #         for temp_block_idx in temp_block_idx_list:
                #             box2 = new_total_result_dict[page_idx][temp_block_idx]["mol_box"]
                
                
                # 在这里过滤分子
                new_new_total_result = []
                for box_dict in new_total_result_dict[page_idx]:
                    post_SMILES = box_dict["Cano_SMILES"]
                    ## 12C
                    ## 过滤掉特别复杂的分子
                    if (post_SMILES.count("%"))>=10 or (post_SMILES=="[O-]") or ("CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC" in post_SMILES) or (post_SMILES=="[CH2-][CH2-]"):
                        pass
                    else:
                        new_new_total_result.append(box_dict)
                new_total_result_dict[page_idx] = new_new_total_result

            else:
                new_total_result_dict[page_idx] = []

        total_result_dict = new_total_result_dict
        
        if offset_x!=0 or offset_y!=0:
            if len(total_result_dict)>1:
                self.logger.error("the box mode only support in single prediction")
                raise Exception("the box mode only support in single prediction")
            self.logger.info("adding `offset_x` and `offset_y` into result")
            for i, (page_idx, total_result) in enumerate(total_result_dict.items()):
                for block_idx, box_dict in enumerate(total_result):
                    mol_box = box_dict.get('mol_box', None)
                    if mol_box is not None:
                        mol_box = mol_box[0] + offset_x, mol_box[1] + offset_y, mol_box[2] + offset_x, mol_box[3] + offset_y
                    label_box = box_dict.get('label_box', None)
                    if isinstance(label_box, list):
                        for temp_label_box in label_box:
                            temp_label_box = temp_label_box[0] + offset_x, temp_label_box[1] + offset_y, temp_label_box[2] + offset_x, temp_label_box[3] + offset_y
                    elif isinstance(label_box, Tuple):
                        label_box = label_box[0] + offset_x, label_box[1] + offset_y, label_box[2] + offset_x, label_box[3] + offset_y
        
        ## add extra label_box

        for i, (page_idx, total_result) in enumerate(total_result_dict.items()):
            image = image_list[page_idx_list.index(page_idx)]
            for block_idx, box_dict in enumerate(total_result):
                
                ## 依次添加引号和矫正构型
                box_dict["post_molblock"] = assign_e_to_unsigned_bond(add_quotation_mark_to_mol_block(box_dict["post_molblock"]))

                temp_mol_box = box_dict["mol_box"]
                temp_mol_image = image.crop(temp_mol_box)
                box_dict["mol_png_base64"] = image_to_base64(temp_mol_image)

                ## 把名字换换回来
                if "label_box_list" in box_dict:
                    box_dict["label_box"] = box_dict.pop("label_box_list")
                else:
                    box_dict["label_box"] = []
                
                if "label_box_page_list" not in box_dict:
                    box_dict["label_box_page_list"] = [page_idx] * len(box_dict["label_box"])
                
                if "label_string" in box_dict:
                    # ## 新增去重
                    box_dict["label_string"] = box_dict.pop("label_string")
                    ## 不应该再这边去重
                    # box_dict["label_string"] = list(set(box_dict["label_string"]))
                else:
                    box_dict["label_string"] = []
                
                ## add 0724
                if "label_latex_string" in box_dict:
                    box_dict["label_latex_string"] = box_dict.pop("label_latex_string")
                    # ## 新增去重
                    # box_dict["label_latex_string"] = list(set(box_dict["label_latex_string"]))
                else:
                    box_dict["label_latex_string"] = []
                
                if "text_box_list" in box_dict:
                    box_dict["text_box"] = box_dict.pop("text_box_list")
                else:
                    box_dict["text_box"] = []
                
                if "text_box_page_list" not in box_dict:
                    box_dict["text_box_page_list"] = [page_idx] * len(box_dict["text_box"])
                
                if "text_string" in box_dict:
                    box_dict["text_string"] = box_dict.pop("text_string")
                else:
                    box_dict["text_string"] = []
                
                ## add 0724
                if "text_latex_string" in box_dict:
                    box_dict["text_latex_string"] = box_dict.pop("text_latex_string")
                else:
                    box_dict["text_latex_string"] = []
                
                if "rgroup_box_list" in box_dict:
                    box_dict["rgroup_box"] = box_dict.pop("rgroup_box_list")
                else:
                    box_dict["rgroup_box"] = []
                
                if "rgroup_box_page_list" not in box_dict:
                    box_dict["rgroup_box_page_list"] = [page_idx] * len(box_dict["rgroup_box"])
                
                if "rgroup_string" in box_dict:
                    box_dict["rgroup_string"] = box_dict.pop("rgroup_string")
                else:
                    box_dict["rgroup_string"] = []
                
                ## add 0113
                if "rgroup_latex_string" in box_dict:
                    box_dict["rgroup_latex_string"] = box_dict.pop("rgroup_latex_string")
                else:
                    box_dict["rgroup_latex_string"] = []
                
                ## add 0113
                if "iupac_box_list" in box_dict:
                    box_dict["iupac_box"] = box_dict.pop("iupac_box_list")
                else:
                    box_dict["iupac_box"] = []
                
                if "iupac_box_page_list" not in box_dict:
                    box_dict["iupac_box_page_list"] = [page_idx] * len(box_dict["iupac_box"])
                
                if "iupac_string" in box_dict:
                    box_dict["iupac_string"] = box_dict.pop("iupac_string")
                else:
                    box_dict["iupac_string"] = []
                
                ## add 0113
                if "iupac_latex_string" in box_dict:
                    box_dict["iupac_latex_string"] = box_dict.pop("iupac_latex_string")
                else:
                    box_dict["iupac_latex_string"] = []
                
                if "table_state" not in box_dict:
                    box_dict["table_state"] = "out_table"
                
                if "table_uuid" not in box_dict:
                    box_dict["table_uuid"] = None

            ## 去除预测错误的label
            ## 0327
            for block_idx_i in range(len(total_result)):
                box_dict_i = total_result[block_idx_i]
                for block_idx_j in range(len(total_result)):
                    if block_idx_j == block_idx_i:
                        continue
                    box_dict_j = total_result[block_idx_j]
                    remove_ids = []
                    if len(box_dict_i["label_string"])>1:
                        for box_dict_i_string_id, box_dict_i_string in enumerate(box_dict_i["label_string"]):
                            if box_dict_i_string == "":
                                continue 
                            if box_dict_i_string in box_dict_j["label_string"]:
                                ## 如果
                                if len(box_dict_j["label_string"]) == 1:
                                    remove_ids.append(box_dict_i_string_id)
                                else:
                                    ## TODO
                                    ## 存在多个
                                    pass
                    
                    if len(remove_ids)>0:
                        temp_label_box = []
                        temp_label_string = []
                        temp_label_latex_string = []
                        for temp_id in range(len(box_dict_i["label_string"])):
                            if temp_id not in remove_ids:
                                temp_label_box.append(box_dict_i["label_box"][temp_id])
                                temp_label_string.append(box_dict_i["label_string"][temp_id])
                                temp_label_latex_string.append(box_dict_i["label_latex_string"][temp_id])
                        
                        box_dict_i["label_box"] = temp_label_box
                        box_dict_i["label_string"] = temp_label_string
                        box_dict_i["label_latex_string"] = temp_label_latex_string

            ## TODO 写道标签处理中
            ## 去除错误的label
            ## 检查intermediate
            for block_idx_i in range(len(total_result)):
                box_dict_i = total_result[block_idx_i]
                remove_ids = []
                intermediate_ids = []
                intermediate_string_list = []
                for temp_id, temp_string in enumerate(box_dict_i["label_string"]):
                    if ("intermediate" in temp_string) or ("Intermediate" in temp_string) or ("INTERMEDIATE" in temp_string):
                        try:
                            post_fix = extract_intermediate(temp_string)[0][1]
                            if len(intermediate_string_list) == 0:
                                intermediate_string_list.append(post_fix)
                                intermediate_ids.append(temp_id)
                            else:
                                if post_fix not in intermediate_string_list:
                                    ## 选择第0个
                                    intermediate_box1 = box_dict_i["label_box"][intermediate_ids[0]]
                                    intermediate_box2 = box_dict_i["label_box"][temp_id]
                                    temp_mol_box = box_dict_i["mol_box"]
                                    # 计算中心点
                                    center1 = calculate_center(intermediate_box1)
                                    center2 = calculate_center(intermediate_box2)
                                    center3 = calculate_center(temp_mol_box)

                                    # 计算距离
                                    distance1 = calculate_distance(center1, center3)
                                    distance2 = calculate_distance(center2, center3)
                                    if distance2<distance1:
                                        remove_ids.extend(intermediate_ids)
                                        intermediate_ids = [temp_id]
                                        intermediate_string_list = [post_fix]
                                    elif distance2==distance1:
                                        if len(intermediate_ids)>1:
                                            remove_ids.append(temp_id)
                                        else:
                                            remove_ids.extend(intermediate_ids)
                                            intermediate_ids = [temp_id]
                                            intermediate_string_list = [post_fix]
                                    else:
                                        remove_ids.append(temp_id)

                        except Exception as e:
                            pass

                if len(remove_ids)>0:
                    temp_label_box = []
                    temp_label_string = []
                    temp_label_latex_string = []
                    for temp_id in range(len(box_dict_i["label_string"])):
                        if temp_id not in remove_ids:
                            temp_label_box.append(box_dict_i["label_box"][temp_id])
                            temp_label_string.append(box_dict_i["label_string"][temp_id])
                            temp_label_latex_string.append(box_dict_i["label_latex_string"][temp_id])
                        else:
                            self.logger.info(f"remove {box_dict_i['label_string'][temp_id]}")
                    
                    box_dict_i["label_box"] = temp_label_box
                    box_dict_i["label_string"] = temp_label_string
                    box_dict_i["label_latex_string"] = temp_label_latex_string

            ## 检查intermediate
            for block_idx_i in range(len(total_result)):
                box_dict_i = total_result[block_idx_i]
                remove_ids = []
                intermediate_ids = []
                intermediate_string_list = []
                for temp_id, temp_string in enumerate(box_dict_i["label_string"]):
                    if ("中间体" in temp_string) or ("中间体" in temp_string) or ("中间体" in temp_string):
                        try:
                            post_fix = extract_zhongjianti(temp_string)[0][1]
                            if len(intermediate_string_list) == 0:
                                intermediate_string_list.append(post_fix)
                                intermediate_ids.append(temp_id)
                            else:
                                if post_fix not in intermediate_string_list:
                                    ## 选择第0个
                                    intermediate_box1 = box_dict_i["label_box"][intermediate_ids[0]]
                                    intermediate_box2 = box_dict_i["label_box"][temp_id]
                                    temp_mol_box = box_dict_i["mol_box"]
                                    # 计算中心点
                                    center1 = calculate_center(intermediate_box1)
                                    center2 = calculate_center(intermediate_box2)
                                    center3 = calculate_center(temp_mol_box)

                                    # 计算距离
                                    distance1 = calculate_distance(center1, center3)
                                    distance2 = calculate_distance(center2, center3)
                                    if distance2<distance1:
                                        remove_ids.extend(intermediate_ids)
                                        intermediate_ids = [temp_id]
                                        intermediate_string_list = [post_fix]
                                    elif distance2==distance1:
                                        if len(intermediate_ids)>1:
                                            remove_ids.append(temp_id)
                                        else:
                                            remove_ids.extend(intermediate_ids)
                                            intermediate_ids = [temp_id]
                                            intermediate_string_list = [post_fix]
                                    else:
                                        remove_ids.append(temp_id)
                        except Exception as e:
                            print(e)

                if len(remove_ids)>0:
                    temp_label_box = []
                    temp_label_string = []
                    temp_label_latex_string = []
                    for temp_id in range(len(box_dict_i["label_string"])):
                        if temp_id not in remove_ids:
                            temp_label_box.append(box_dict_i["label_box"][temp_id])
                            temp_label_string.append(box_dict_i["label_string"][temp_id])
                            temp_label_latex_string.append(box_dict_i["label_latex_string"][temp_id])
                        else:
                            self.logger.info(f"remove {box_dict_i['label_string'][temp_id]}")

            ## 去除example
            for block_idx_i in range(len(total_result)):
                box_dict_i = total_result[block_idx_i]
                remove_ids = []
                example_ids = []
                example_string_list = []
                for temp_id, temp_string in enumerate(box_dict_i["label_string"]):
                    if ("example" in temp_string) or ("Example" in temp_string) or ("EXAMPLE" in temp_string):
                        try:
                            post_fix = extract_example(temp_string)[0][1]
                            if len(example_string_list) == 0:
                                example_string_list.append(post_fix)
                                example_ids.append(temp_id)
                            else:
                                if post_fix not in example_string_list:
                                    ## 选择第0个
                                    example_box1 = box_dict_i["label_box"][example_ids[0]]
                                    example_box2 = box_dict_i["label_box"][temp_id]
                                    temp_mol_box = box_dict_i["mol_box"]
                                    # 计算中心点
                                    center1 = calculate_center(example_box1)
                                    center2 = calculate_center(example_box2)
                                    center3 = calculate_center(temp_mol_box)

                                    # 计算距离
                                    distance1 = calculate_distance(center1, center3)
                                    distance2 = calculate_distance(center2, center3)
                                    if distance2<distance1:
                                        remove_ids.extend(example_ids)
                                        example_ids = [temp_id]
                                        example_string_list = [post_fix]
                                    elif distance2==distance1:
                                        if len(example_ids)>1:
                                            remove_ids.append(temp_id)
                                        else:
                                            remove_ids.extend(example_ids)
                                            example_ids = [temp_id]
                                            example_string_list = [post_fix]
                                    else:
                                        remove_ids.append(temp_id)
                        except Exception as e:
                            print(e)

                if len(remove_ids)>0:
                    temp_label_box = []
                    temp_label_string = []
                    temp_label_latex_string = []
                    for temp_id in range(len(box_dict_i["label_string"])):
                        if temp_id not in remove_ids:
                            temp_label_box.append(box_dict_i["label_box"][temp_id])
                            temp_label_string.append(box_dict_i["label_string"][temp_id])
                            temp_label_latex_string.append(box_dict_i["label_latex_string"][temp_id])
                        else:
                            self.logger.info(f"remove {box_dict_i['label_string'][temp_id]}")
                    box_dict_i["label_box"] = temp_label_box
                    box_dict_i["label_string"] = temp_label_string
                    box_dict_i["label_latex_string"] = temp_label_latex_string                

                ## 为索引增加空格
                for block_idx_i in range(len(total_result)):
                    box_dict_i = total_result[block_idx_i]
                    for temp_id, temp_string in enumerate(box_dict_i["label_string"]):
                        # print("before",box_dict_i["label_string"][temp_id])
                        box_dict_i["label_string"][temp_id] = add_space_in_text_fn(box_dict_i["label_string"][temp_id])
                        # print("after",box_dict_i["label_string"][temp_id])
            
              
        if with_html:
            self.logger.info("======get html======")
            start = time.time()

            if self.num_workers <= 1 or len(page_idx_list)==1:
                molecule_html_result = [single_page_molecule_result_to_html(image_list[i], page_idx_list[i], total_result_dict[page_idx_list[i]]) for i in range(len(image_list))]
                
            else:
                with mp.Pool(min(self.num_workers, max(1, len(page_idx_list)))) as p:
                    molecule_html_result = p.starmap(single_page_molecule_result_to_html, zip(image_list,
                                                                                            page_idx_list,
                                                                                            [total_result_dict[page_idx_list[i]] for i in range(len(image_list))],
                                                                                            ), chunksize=128)
                    
            return_page_idx_list, molecule_html_list, molecule_csv_list = list(zip(*molecule_html_result))

            ordered_idx = np.argsort(return_page_idx_list)
            molecule_html_list = [molecule_html_list[_] for _ in ordered_idx]
            molecule_csv_list = [molecule_csv_list[_] for _ in ordered_idx]

            for _ in range(len(page_idx_list)):
                ## 去除默认的
                if molecule_html_list[_] != '</div></div></div><hr class="separator"><hr class="separator">':
                    mol_html = mol_html + molecule_html_list[_]
                if len(molecule_csv_list[_])>0:
                    mol_csv = pd.concat([mol_csv, molecule_csv_list[_]])
            
            mol_csv = mol_csv.reset_index(drop=True)
            if mol_html != "":
                mol_html = get_border_html(mol_html)

            if with_table:
                if self.num_workers <= 1 or len(page_idx_list)==1:
                    table_html_result = [single_page_table_result_to_html(image_list[i], page_idx_list[i], total_table_result_dict[page_idx_list[i]]) for i in range(len(image_list))]
                    
                else:
                    with mp.Pool(min(self.num_workers, max(1, len(page_idx_list)))) as p:
                        table_html_result = p.starmap(single_page_table_result_to_html, zip(image_list,
                                                                                                page_idx_list,
                                                                                                [total_table_result_dict[page_idx_list[i]] for i in range(len(image_list))],
                                                                                                ), chunksize=128)
                
                return_page_idx_list, table_html_list = list(zip(*table_html_result))
                ordered_idx = np.argsort(return_page_idx_list)
                table_html_list = [table_html_list[_] for _ in ordered_idx]

                for _ in range(len(page_idx_list)):
                    ## 去除默认的
                    if table_html_list[_] != '</div></div></div><hr class="separator"><hr class="separator">':
                        table_html += table_html_list[_]
                
                if table_html != "":
                    table_html = get_border_html(table_html)
                
                self.logger.info(f"get html consumed:{time.time()-start:.3f}")
                self.logger.info("=========================")
        
        ## find core
        if with_table:
            self.logger.info("=======start finding core in table=======")
            start = time.time()
            for page_idx in page_idx_list:
                total_table_result = total_table_result_dict.get(page_idx, [])
                total_result = total_result_dict.get(page_idx, [])
                ## ensure must have data in `total_table_result` and `total_result`
                if len(total_table_result)>0 and len(total_result)>0:
                    for table_id, table_result in enumerate(total_table_result):
                        
                        table_box = (table_result.bbox.x1, table_result.bbox.y1, \
                                    table_result.bbox.x2, table_result.bbox.y2,)

                        candidates_list = []
                        for block_idx, box_dict in enumerate(total_result):
                            mol_box = box_dict["mol_box"]
                            ## 分子在下方
                            if mol_box[1]>table_box[3]:
                                continue

                            ## 分子在右侧
                            elif mol_box[0]>table_box[2]:
                                continue

                            ## 分子在左侧
                            elif mol_box[2]<table_box[0]:
                                continue

                            ## 分子在表格中
                            elif mol_box[2]<=table_box[2] and mol_box[3]<=table_box[3] and mol_box[1]>=table_box[1] and mol_box[0]>=table_box[0]:
                                continue

                            ## 分子在上方，并且在x方向上有交集
                            elif mol_box[1]<=table_box[1] and (table_box[2]-mol_box[0])*(mol_box[2]-table_box[0])>0:
                                dist = table_box[1]-mol_box[3]
                                if dist<=0.25*(mol_box[3]-mol_box[1]):
                                    candidates_list.append((block_idx, dist))
                        
                        core_list = []
                        for (block_idx, dist) in candidates_list:
                            core_list.append(total_result[block_idx])
                            ## in-place
                            total_result[block_idx]["table_state"] = "core"
                            
                        setattr(table_result, "core_list", core_list)
            self.logger.info(f"finding core in table consumed:{time.time()-start:.3f}")
            self.logger.info("=========================")


        table_uuid_dict = {}
        temp_total_table_result_dict = {}
        pre_df_header_page = None
        pre_df_header = None
        pre_df_tail_type = None
        if add_prefix:
            if "pre_info" in self.prepage:
                if "pre_df_header_page" in self.prepage["pre_info"]:
                    pre_df_header_page = self.prepage["pre_info"]["pre_df_header_page"]
                if "pre_df_header" in self.prepage["pre_info"]:
                    pre_df_header = self.prepage["pre_info"]["pre_df_header"]
                if "pre_df_tail_type" in self.prepage["pre_info"]:
                    pre_df_tail_type = self.prepage["pre_info"]["pre_df_tail_type"]

        for page_idx, total_table_result in total_table_result_dict.items():
            temp_list = []
            image = image_list[page_idx_list.index(page_idx)]
            for table_id, table_result in enumerate(total_table_result):
                core_list = getattr(table_result, "core_list", [])
                table_type = getattr(table_result, "table", "border_table")

                if f"{page_idx}_{table_id}" not in table_uuid_dict.keys():
                    table_uuid_dict[f"{page_idx}_{table_id}"] = uuid.uuid4().hex
                
                temp_image_box = (table_result.bbox.x1, table_result.bbox.y1, table_result.bbox.x2, table_result.bbox.y2)
                temp_table_image = image.crop(temp_image_box)

                try:
                    image_base64 = image_to_base64(temp_table_image)
                except:
                    image_base64 = ""

                ## 合并表头
                new_table_result = merge_header_and_get_new_table(table_result)
                new_table_result = merge_header_and_get_new_table_v2(new_table_result)

                print({
                    "pre_info":{
                            "pre_df_header_page":pre_df_header_page,
                            "pre_df_header":pre_df_header,
                            "pre_df_tail_type":pre_df_tail_type,
                        }
                })
                
                temp_list.append(
                    {
                        "dataframe":new_table_result.df,
                        # "html":new_table_result.df.to_html(index=False).replace("&lt;","<").replace("&gt;",">"),
                        "box":(table_result.bbox.x1, table_result.bbox.y1, table_result.bbox.x2, table_result.bbox.y2),
                        "core_list":core_list,
                        "type":table_type,
                        "src":table_result,
                        "src_modified":new_table_result,
                        "page_idx":f"{page_idx}",
                        "table_id":f"{table_id}",
                        "pngs":image_base64,
                        "has_rgroup":False,
                        "table_uuid":table_uuid_dict[f"{page_idx}_{table_id}"],
                        "pre_info":{
                            "pre_df_header_page":pre_df_header_page,
                            "pre_df_header":pre_df_header,
                            "pre_df_tail_type":pre_df_tail_type,
                        }
                    }
                )

                ## 
                num_rows, num_columns = new_table_result.df.shape
                pre_df_header_list = []
                pre_df_tail_type_list = []
                for i, row in enumerate(new_table_result.content.values()):
                    if i == 0:
                        for j, cell in enumerate(row):
                            temp_cell_content = cell.value
                            if isinstance(temp_cell_content, dict):
                                pre_df_header_list = []
                                ## 直接进行覆盖
                                pre_df_header_page = page_idx
                                break
                            else:
                                pre_df_header_list.append(temp_cell_content)
                        
                        if len(pre_df_header_list) == 0:
                            break
                        else:
                            pre_df_header = pre_df_header_list
                            pre_df_header_page = page_idx

                    elif i == num_rows -1:
                        for j, cell in enumerate(row):
                            temp_cell_content = cell.value
                            pre_df_tail_type_list.append(type(temp_cell_content))
                        
                        pre_df_tail_type = pre_df_tail_type_list

            temp_total_table_result_dict[page_idx] = temp_list
        total_table_result_dict = temp_total_table_result_dict

        if return_realative_coordinates:
            self.logger.info("======converting coordinates======")
            start = time.time()
            for i in range(len(page_idx_list)):
                page_idx = page_idx_list[i]
                image:Image = image_list[i]
                width, height = image.size
                if page_idx in total_result_dict:
                    total_result = total_result_dict[page_idx_list[i]]
                    for block_idx, box_dict in enumerate(total_result):
                        box_dict["mol_box"] = [
                            box_dict["mol_box"][0]/width, box_dict["mol_box"][1]/height, \
                            box_dict["mol_box"][2]/width, box_dict["mol_box"][3]/height
                        ]

                        label_box_list = box_dict.get('label_box', [])
                        
                        ## TODO 做加法
                        temp_label_box = []
                        for label_box in label_box_list:
                            label_box = [
                                label_box[0]/width, label_box[1]/height, \
                                label_box[2]/width, label_box[3]/height
                            ]
                            temp_label_box.append(label_box)
                        
                        box_dict["label_box"] = temp_label_box
                        
                if page_idx in page_idx_list:
                    if page_idx in total_table_result_dict.keys():
                        ## 获取结果
                        total_table_result = total_table_result_dict[page_idx]
                        for table_result in total_table_result:
                            table_result["box"] = [
                                table_result["box"][0]/width, table_result["box"][1]/height, \
                                table_result["box"][2]/width, table_result["box"][3]/height
                            ]
                    else:
                        total_table_result_dict[page_idx] = []

            # self.logger.info("======finined converting absolute coordinates to relative coordinates======")
            self.logger.info(f"converting coordinates consumed:{time.time()-start:.3f}")
            self.logger.info("=========================")
        
        if with_html is False:
            if with_table:
                post_process = True
                if post_process:
                    new_total_table_result_dict = {}

                    for page_idx, total_table_results in total_table_result_dict.items():
                        temp_table_list = []

                        total_result = total_result_dict.get(page_idx)

                        for table_id, total_table_result in enumerate(total_table_results):

                            ## 对原始数据进行操作
                            table = total_table_result["src_modified"]

                            ##  TODO Problem
                            ## 表格的问题
                            result = []
                            mol_idx_lists = []
                            for i, row in enumerate(table.content.values()):
                                row_result = []
                                mol_idx_list = []
                                for j, cell in enumerate(row):
                                    temp_cell_content = cell.value
                                    if isinstance(temp_cell_content, dict):
                                        row_result.append("<Cano_SMILES>"+temp_cell_content["Cano_SMILES"]+"</Cano_SMILES>")
                                        temp_cell_content["table_uuid"] = total_table_result["table_uuid"]
                                        if "*" in temp_cell_content["Cano_SMILES"]:
                                            mol_idx_list.append(1)
                                        else:
                                            mol_idx_list.append(0)
                                    else:
                                        row_result.append(temp_cell_content)
                                        mol_idx_list.append(0)

                                result.append(row_result)
                                mol_idx_lists.append(mol_idx_list)
                            

                            df0 = pd.DataFrame(result)
                            if len(df0) == 0:
                                pass
                            else:
                                try:
                                    ## 先确认表头有分子
                                    Flag = False
                                    for temp_string in df0.iloc[0].tolist():
                                        if temp_string is not None and "<Cano_SMILES>" in temp_string and "</Cano_SMILES>" in temp_string:
                                            Flag = True
                                            break
                                    
                                    ## 如果首行有分子
                                    if Flag:
                                        pre_info = total_table_result["pre_info"]
                                        pre_df_header = pre_info["pre_df_header"]
                                        pre_df_header_page = pre_info["pre_df_header_page"]
                                        pre_df_tail_type = pre_info["pre_df_tail_type"]

                                        if pre_df_header_page in [page_idx-1, page_idx]:
                                            if pre_df_header is not None:
                                                ## 长度一致的
                                                if len(pre_df_header) == len(df0.columns):
                                                    right_mol = 0
                                                    error = 0
                                                    count = 0
                                                    for local_i in df0.index:
                                                        for local_j in df0.columns:
                                                            temp_string = df0.loc[local_i, local_j]
                                                            ## 如果这个cell是分子
                                                            if (temp_string is not None) and "<Cano_SMILES>" in temp_string and "</Cano_SMILES>" in temp_string:
                                                                count = count + 1
                                                                if pre_df_tail_type[local_j] != dict:
                                                                    error = error + 1
                                                                else:
                                                                    right_mol = right_mol + 1
                                                    
                                                    if error == 0 and right_mol/count>=0.5:
                                                        df0 = pd.concat([pd.DataFrame(pre_df_header).T, df0])
                                                        df0 = df0.reset_index(drop=True)
                                                
                                                ## 长度更长的
                                                elif len(pre_df_header) > len(df0.columns):

                                                    ## 如果后面几列是分子
                                                    add_token = True
                                                    for local_j in range(len(df0.columns), len(pre_df_header)):
                                                        if pre_df_tail_type[local_j] == dict:
                                                            add_token = False
                                                            break
                                                    
                                                    if add_token:
                                                        right_mol = 0
                                                        error = 0
                                                        count = 0
                                                        for local_i in df0.index:
                                                            for local_j in df0.columns:
                                                                temp_string = df0.loc[local_i, local_j]
                                                                ## 如果这个cell是分子
                                                                if "<Cano_SMILES>" in temp_string and "</Cano_SMILES>" in temp_string:
                                                                    count = count + 1
                                                                    if pre_df_tail_type[local_j] != dict:
                                                                        error = error + 1
                                                                    else:
                                                                        right_mol = right_mol + 1
                                                        
                                                        if error == 0 and right_mol/count>=0.5:
                                                            df0 = pd.concat([pd.DataFrame(pre_df_header[:len(df0.columns)]).T, df0])
                                                            df0 = df0.reset_index(drop=True)
                                                            pre_length = len(df0.columns)
                                                            
                                                            for local_j, new_column in enumerate(pre_df_header[pre_length:]):
                                                                df0.loc[0, local_j+pre_length] = new_column
                                                            ## 用空值填充
                                                            df0 = df0.fillna('')


                                    ## 先确认表头有分子
                                    Flag = False
                                    for temp_string in df0.iloc[0].tolist():
                                        if temp_string is not None and "<Cano_SMILES>" in temp_string and "</Cano_SMILES>" in temp_string:
                                            Flag = True

                                    if Flag is True:
                                        df0 = pd.concat([pd.DataFrame(df0.columns.tolist()).T, df0])
                                        df0 = df0.reset_index(drop=True)
                                    if len(df0)>0:
                                        print("df0",df0.iloc[0])
                                    total_table_result["dataframe"] = df0
                                
                                except Exception as e:
                                    print(e)
                            
                            ## 使用默认值
                            total_table_result["has_Rgroup"] = False
                            try:
                                star_array = np.array(mol_idx_lists)
                                star_array_columns = star_array.sum(axis=1)/len(star_array)

                                if (star_array_columns>=1/3).sum()>0:
                                    total_table_result["has_Rgroup"] = True
                            
                            except Exception as e:
                                print(e)
                                total_table_result["has_Rgroup"] = False

                            temp_table_list.append(total_table_result)

                        new_total_table_result_dict[page_idx] = {}
                        new_total_table_result_dict[page_idx] = temp_table_list #List

                    new_total_result_dict = OrderedDict()
                    for page_idx, total_results in total_result_dict.items():
                        temp_list = []
                        for total_result in total_results:
                            # total_result["is_add"] = True
                            temp_list.append(total_result)
                        new_total_result_dict[page_idx] = temp_list
                    
                    self.logger.info(f"all time consumed:{time.time()-all_start:.3f}")
                    self.logger.info("========seperator==========")

                    self.logger.info("========add pre page==========")
                    self.prepage = {
                        'file_name': file_path, 
                        'page_idx': page_idx_list[-1], 
                        'image': image_list[-1], 
                        "pre_info":{
                            "pre_df_header_page":pre_df_header_page,
                            "pre_df_header":pre_df_header,
                            "pre_df_tail_type":pre_df_tail_type,
                        }
                    }
                    self.logger.info("========add pre page==========")
                    self.logger.info("\n")
                    return new_total_result_dict, new_total_table_result_dict
            ## TODO
            else:
                return new_total_result_dict
        else:
            if with_table:
                if with_html:
                    self.logger.info(f"all time consumed:{time.time()-all_start:.3f}")
                    self.logger.info("========seperator==========")
                    self.logger.info("\n")
                    self.logger.info("========add pre page==========")
                    self.prepage = {
                        'file_name': file_path, 
                        'page_idx': page_idx_list[-1], 
                        'image': image_list[-1], 
                        "pre_info":{
                            "pre_df_header_page":pre_df_header_page,
                            "pre_df_header":pre_df_header,
                            "pre_df_tail_type":pre_df_tail_type,
                        }
                    }

                    self.logger.info("========add pre page==========")
                    return total_result_dict, total_table_result_dict, mol_html, table_html, mol_csv
                else:
                    self.logger.info(f"all time consumed:{time.time()-all_start:.3f}")
                    self.logger.info("========seperator==========")
                    self.logger.info("\n")
                    self.logger.info("========add pre page==========")
                    self.prepage = {
                        'file_name': file_path, 
                        'page_idx': page_idx_list[-1], 
                        'image': image_list[-1], 
                        "pre_info":{
                            "pre_df_header_page":pre_df_header_page,
                            "pre_df_header":pre_df_header,
                            "pre_df_tail_type":pre_df_tail_type,
                        }
                    }

                    self.logger.info("========add pre page==========")
                    return total_result_dict, total_table_result_dict
            else:
                if with_html:
                    self.logger.info(f"all time consumed:{time.time()-all_start:.3f}")
                    self.logger.info("========seperator==========")
                    self.logger.info("\n")
                    self.logger.info("========add pre page==========")
                    self.prepage = {
                        'file_name': file_path, 
                        'page_idx': page_idx_list[-1], 
                        'image': image_list[-1], 
                        "pre_info":{
                            "pre_df_header_page":pre_df_header_page,
                            "pre_df_header":pre_df_header,
                            "pre_df_tail_type":pre_df_tail_type,
                        }
                    }

                    self.logger.info("========add pre page==========")
                    return total_result_dict, mol_html, table_html, mol_csv
                else:
                    self.logger.info(f"all time consumed:{time.time()-all_start:.3f}")
                    self.logger.info("========seperator==========")
                    self.logger.info("========add pre page==========")
                    self.prepage = {
                        'file_name': file_path, 
                        'page_idx': page_idx_list[-1], 
                        'image': image_list[-1], 
                        "pre_info":{
                            "pre_df_header_page":pre_df_header_page,
                            "pre_df_header":pre_df_header,
                            "pre_df_tail_type":pre_df_tail_type,
                        }
                    }
                    self.logger.info("========add pre page==========")
                    self.logger.info("\n")
                    return total_result_dict



if __name__ == "__main__":
    pass
    # from torch.multiprocessing import Pool, Process, set_start_method
    # set_start_method('spawn')
    # parser = Parser_Processer(num_workers=4)
    
    # ## 测试多页pdf
    # pdf_path = "acs.jmedchem.0c00002.pdf"
    # start = time.time()
    # result = parser._prediction_from_pdf(file_path=pdf_path, page_idx_list=list(range(1, 13)))
    # # while True:
    # #     try:
    # #         result = next(generator)
    # #         # 处理生成器函数返回的结果
    # #         if len(result) > 0:
    # #             print(result.keys())
    # #     except StopIteration:
    # #         # 生成器对象耗尽，退出循环
    # #         break
    # end = time.time()
    # print(f"time elapsed:{(end-start):.3f}")
    # start = time.time()
    # for page_idx in range(1, 13):
    #     result = parser._prediction_from_pdf(file_path=pdf_path, page_idx_list=[page_idx])
    # end = time.time()
    # print(f"time elapsed:{(end-start):.3f}")

    
    # pdf_path = "acs.jmedchem.0c00002.pdf"
    # generator = parser.prediction_from_page(file_path=pdf_path, page_idx_list=[1], box=[-100, 1000, 2606, 3410])
    # while True:
    #     try:
    #         result = next(generator)
    #         # 处理生成器函数返回的结果
    #         if len(result) > 0:
    #             print(result.keys())
    #     except StopIteration:
    #         # 生成器对象耗尽，退出循环
    #         break
    
    # file_path = "test_moldetect.png"
    # generator = parser.prediction_from_page(file_path=file_path, box=[-100, 500, 1306, 1774])
    # while True:
    #     try:
    #         result = next(generator)
    #         # 处理生成器函数返回的结果
    #         if len(result) > 0:
    #             print(result.keys())
    #     except StopIteration:
    #         # 生成器对象耗尽，退出循环
    #         break

    # # file_path = "US2018044344A1.pdf"
    # # result = parser._prediction_from_pdf(file_path=file_path,page_idx_list=list(range(30,80)), with_html=True)
    # # import ipdb
    # # ipdb.set_trace()